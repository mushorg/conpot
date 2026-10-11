# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""OPC UA protocol server tests."""

from __future__ import annotations

import asyncio
import hashlib
import os
import socket
import struct
import time
import unittest

import pytest
from asyncua import Client, Server, ua

import conpot.core as conpot_core
from conpot.protocols.opcua.file_type import FileTypeHandler, OPCUAFileManager
from conpot.protocols.opcua.opcua_server import OPCUAServer
from conpot.utils.server_tasks import (
    drain_log_queue,
    get_log_event,
    spawn_test_server,
    teardown_test_server,
)

READ_TIMEOUT = 5.0
NAMESPACE_URI = "http://conpot.org/OPCUA/"
ENDPOINT_PATH = "/conpot/server/"


def _endpoint(host: str, port: int) -> str:
    return f"opc.tcp://{host}:{port}{ENDPOINT_PATH}"


async def _read_plant_variables(host: str, port: int) -> dict:
    client = Client(url=_endpoint(host, port), timeout=READ_TIMEOUT)
    await client.connect()
    try:
        idx = await client.get_namespace_index(NAMESPACE_URI)
        plant = await client.nodes.objects.get_child([f"{idx}:Plant"])
        values = {}
        for name in ("Temperature", "Pressure", "PumpRunning", "BatchId"):
            node = await plant.get_child([f"{idx}:{name}"])
            values[name] = await node.read_value()
        return values
    finally:
        await client.disconnect()


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(scope="class")
def opcua_server(request):
    conpot_core.initialize_vfs()
    server, handle = spawn_test_server(OPCUAServer, "opcua", "opcua")
    request.cls.opcua_server = server
    request.cls.server_handle = handle
    yield
    teardown_test_server(server, handle)


@pytest.mark.usefixtures("opcua_server")
class TestOPCUAServer(unittest.TestCase):
    def _port(self):
        return self.opcua_server.server.server_port

    def test_new_connection_and_lost_events(self):
        drain_log_queue(self.server_handle)
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=2)
        sock.close()
        time.sleep(0.2)
        new_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual("NEW_CONNECTION", new_event["event_type"])
        lost_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual("CONNECTION_LOST", lost_event["event_type"])

    def test_read_returns_template_variables(self):
        drain_log_queue(self.server_handle)
        values = _run(_read_plant_variables("127.0.0.1", self._port()))
        self.assertEqual(values["Temperature"], 25.0)
        self.assertEqual(values["Pressure"], 101.3)
        self.assertEqual(values["PumpRunning"], True)
        self.assertEqual(values["BatchId"], 42)

        events = []
        for _ in range(16):
            try:
                events.append(get_log_event(self.server_handle, timeout=1))
            except Exception:
                break
        types = [e["event_type"] for e in events]
        self.assertIn("NEW_CONNECTION", types)
        self.assertIn("REQUEST", types)
        requests = [e.get("request") for e in events if e["event_type"] == "REQUEST"]
        self.assertTrue(
            any(
                r in ("Hello", "OpenSecureChannel", "CreateSession", "Read")
                for r in requests
            ),
            requests,
        )

    def test_concurrent_clients_read(self):
        drain_log_queue(self.server_handle)
        port = self._port()

        async def _both():
            async def one():
                return await _read_plant_variables("127.0.0.1", port)

            return await asyncio.gather(one(), one())

        a, b = _run(_both())
        self.assertEqual(a["Temperature"], 25.0)
        self.assertEqual(b["Temperature"], 25.0)

    def test_peer_rst_is_not_a_session_crash(self):
        """nmap -sV RSTs after a banner wait; that must not traceback."""
        drain_log_queue(self.server_handle)
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=2)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        sock.close()
        time.sleep(0.3)
        new_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual("NEW_CONNECTION", new_event["event_type"])
        lost_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual("CONNECTION_LOST", lost_event["event_type"])

    def test_file_transfer_read_and_seek(self):
        drain_log_queue(self.server_handle)
        port = self._port()

        async def _client_op():
            client = Client(url=_endpoint("127.0.0.1", port), timeout=READ_TIMEOUT)
            await client.connect()
            try:
                idx = await client.get_namespace_index(NAMESPACE_URI)
                files = await client.nodes.objects.get_child([f"{idx}:Files"])
                firmware_node = await files.get_child([f"{idx}:firmware.bin"])

                # Check variables on the FileType node
                size = await (await firmware_node.get_child("0:Size")).read_value()
                self.assertGreater(size, 0)
                writable = await (
                    await firmware_node.get_child("0:Writable")
                ).read_value()
                self.assertTrue(writable)

                # Open for read (mode=1)
                handle = await firmware_node.call_method(
                    "0:Open", ua.Variant(1, ua.VariantType.Byte)
                )
                # Seek to position 7
                await firmware_node.call_method(
                    "0:SetPosition",
                    ua.Variant(handle, ua.VariantType.UInt32),
                    ua.Variant(7, ua.VariantType.UInt64),
                )
                pos = await firmware_node.call_method(
                    "0:GetPosition", ua.Variant(handle, ua.VariantType.UInt32)
                )
                self.assertEqual(pos, 7)

                # Read 6 bytes
                chunk = await firmware_node.call_method(
                    "0:Read",
                    ua.Variant(handle, ua.VariantType.UInt32),
                    ua.Variant(6, ua.VariantType.Int32),
                )
                self.assertEqual(chunk, b"PLC_FW")

                # Close file
                await firmware_node.call_method(
                    "0:Close", ua.Variant(handle, ua.VariantType.UInt32)
                )
            finally:
                await client.disconnect()

        _run(_client_op())

        time.sleep(0.3)
        events = drain_log_queue(self.server_handle)
        types = [e["event_type"] for e in events]
        self.assertIn("OPCUA_FILE_OPEN", types)
        self.assertIn("OPCUA_FILE_READ", types)
        self.assertIn("OPCUA_FILE_CLOSE", types)

    def test_file_transfer_write_payload_capture(self):
        drain_log_queue(self.server_handle)
        port = self._port()
        payload = b"MALICIOUS_FIRMWARE_DROP_BINARY_DATA"
        expected_md5 = hashlib.md5(payload).hexdigest()

        async def _client_op():
            client = Client(url=_endpoint("127.0.0.1", port), timeout=READ_TIMEOUT)
            await client.connect()
            try:
                idx = await client.get_namespace_index(NAMESPACE_URI)
                files = await client.nodes.objects.get_child([f"{idx}:Files"])
                firmware_node = await files.get_child([f"{idx}:firmware.bin"])

                # Open for write + erase (mode = 2 | 4 = 6)
                handle = await firmware_node.call_method(
                    "0:Open", ua.Variant(6, ua.VariantType.Byte)
                )
                # Write payload
                await firmware_node.call_method(
                    "0:Write",
                    ua.Variant(handle, ua.VariantType.UInt32),
                    ua.Variant(payload, ua.VariantType.ByteString),
                )
                # Close file (triggers payload capture and MD5 calculation)
                await firmware_node.call_method(
                    "0:Close", ua.Variant(handle, ua.VariantType.UInt32)
                )

                # Verify new size on node
                new_size = await (await firmware_node.get_child("0:Size")).read_value()
                self.assertEqual(new_size, len(payload))
            finally:
                await client.disconnect()

        _run(_client_op())

        time.sleep(0.3)
        events = drain_log_queue(self.server_handle)
        types = [e["event_type"] for e in events]
        self.assertIn("OPCUA_FILE_OPEN", types)
        self.assertIn("OPCUA_FILE_WRITE", types)
        self.assertIn("OPCUA_FILE_CAPTURED", types)
        self.assertIn("OPCUA_FILE_CLOSE", types)

        captured_event = next(
            e for e in events if e["event_type"] == "OPCUA_FILE_CAPTURED"
        )
        self.assertEqual(captured_event["data"]["file"], "firmware.bin")
        self.assertEqual(captured_event["data"]["md5"], expected_md5)
        self.assertEqual(captured_event["data"]["size"], len(payload))
        self.assertEqual(captured_event["data"]["reason"], "close")

        vfs, data_fs = conpot_core.get_vfs("opcua")
        data_fs_filename = captured_event["data"]["filename"]
        self.assertTrue(data_fs.exists(data_fs_filename))
        self.assertEqual(data_fs.readbytes(data_fs_filename), payload)
        self.assertEqual(vfs.readbytes("firmware.bin"), payload)

    def test_file_transfer_write_abrupt_disconnect_captured(self):
        drain_log_queue(self.server_handle)
        port = self._port()
        payload = b"MALICIOUS_FIRMWARE_DROP_ABRUPT_DISCONNECT"
        expected_md5 = hashlib.md5(payload).hexdigest()

        async def _client_op():
            client = Client(url=_endpoint("127.0.0.1", port), timeout=READ_TIMEOUT)
            await client.connect()
            try:
                idx = await client.get_namespace_index(NAMESPACE_URI)
                files = await client.nodes.objects.get_child([f"{idx}:Files"])
                firmware_node = await files.get_child([f"{idx}:firmware.bin"])

                # Open for write + erase (mode = 2 | 4 = 6)
                handle = await firmware_node.call_method(
                    "0:Open", ua.Variant(6, ua.VariantType.Byte)
                )
                # Write payload
                await firmware_node.call_method(
                    "0:Write",
                    ua.Variant(handle, ua.VariantType.UInt32),
                    ua.Variant(payload, ua.VariantType.ByteString),
                )
                # Deliberately do NOT call Close - drop connection immediately
            finally:
                await client.disconnect()

        _run(_client_op())

        time.sleep(0.3)
        events = drain_log_queue(self.server_handle)
        types = [e["event_type"] for e in events]
        self.assertIn("OPCUA_FILE_OPEN", types)
        self.assertIn("OPCUA_FILE_WRITE", types)
        self.assertIn("OPCUA_FILE_CAPTURED", types)

        captured_event = next(
            e for e in events if e["event_type"] == "OPCUA_FILE_CAPTURED"
        )
        self.assertEqual(captured_event["data"]["file"], "firmware.bin")
        self.assertEqual(captured_event["data"]["md5"], expected_md5)
        self.assertEqual(captured_event["data"]["size"], len(payload))
        self.assertEqual(captured_event["data"]["reason"], "disconnect")

        vfs, data_fs = conpot_core.get_vfs("opcua")
        data_fs_filename = captured_event["data"]["filename"]
        self.assertTrue(data_fs.exists(data_fs_filename))
        self.assertEqual(data_fs.readbytes(data_fs_filename), payload)
        self.assertEqual(vfs.readbytes("firmware.bin"), payload)


class TestOPCUAFileTypeUnit(unittest.TestCase):
    def setUp(self):
        conpot_core.initialize_vfs()
        base_vfs = conpot_core.get_vfs()
        norm_root = base_vfs.norm_path("/data/opcua/")
        if not (base_vfs.exists(norm_root) and base_vfs.isdir(norm_root)):
            base_vfs.makedir(norm_root)
        self.vfs, self.data_fs = conpot_core.add_protocol(
            "opcua", data_fs_subdir="opcua", vfs_dst_path="/data/opcua/"
        )
        self.vfs.writebytes("firmware.bin", b"CONPOT_PLC_FW_V2.1.0")

    def tearDown(self):
        for f in self.data_fs.listdir("."):
            if self.data_fs.isfile(f):
                self.data_fs.remove(f)

    def test_file_type_lifecycle_and_vfs_data_fs_capture(self):
        async def _test():
            server = Server()
            await server.init()
            try:
                idx = await server.register_namespace(NAMESPACE_URI)
                fm = OPCUAFileManager(
                    server=server,
                    idx=idx,
                    vfs=self.vfs,
                    data_fs=self.data_fs,
                    root_path="/data/opcua/",
                    data_fs_subdir="opcua",
                )
                await fm.setup()

                handler = fm.handlers["firmware.bin"]
                self.assertTrue(self.vfs.exists("firmware.bin"))
                self.assertEqual(
                    self.vfs.readbytes("firmware.bin"), b"CONPOT_PLC_FW_V2.1.0"
                )

                # Child variables
                size = await (await handler.node.get_child("0:Size")).read_value()
                self.assertEqual(size, len(b"CONPOT_PLC_FW_V2.1.0"))
                writable = await (
                    await handler.node.get_child("0:Writable")
                ).read_value()
                self.assertTrue(writable)

                # Open for read (mode=1)
                handle_v = await handler.open(None, ua.Variant(1, ua.VariantType.Byte))
                handle = handle_v[0].Value
                self.assertEqual(handle, 1)

                # Seek and Read
                await handler.set_position(
                    None,
                    ua.Variant(handle, ua.VariantType.UInt32),
                    ua.Variant(7, ua.VariantType.UInt64),
                )
                pos = (
                    await handler.get_position(
                        None, ua.Variant(handle, ua.VariantType.UInt32)
                    )
                )[0].Value
                self.assertEqual(pos, 7)

                chunk = (
                    await handler.read(
                        None,
                        ua.Variant(handle, ua.VariantType.UInt32),
                        ua.Variant(6, ua.VariantType.Int32),
                    )
                )[0].Value
                self.assertEqual(chunk, b"PLC_FW")

                # Close
                await handler.close(None, ua.Variant(handle, ua.VariantType.UInt32))
                self.assertEqual(len(handler.handles), 0)

                # Open for write + erase (mode=6)
                handle2_v = await handler.open(None, ua.Variant(6, ua.VariantType.Byte))
                handle2 = handle2_v[0].Value
                new_payload = b"OVERWRITTEN_UNIT_PAYLOAD"
                await handler.write(
                    None,
                    ua.Variant(handle2, ua.VariantType.UInt32),
                    ua.Variant(new_payload, ua.VariantType.ByteString),
                )
                await handler.close(None, ua.Variant(handle2, ua.VariantType.UInt32))

                # Verify payload in VFS and data_fs
                self.assertEqual(self.vfs.readbytes("firmware.bin"), new_payload)
                self.assertGreaterEqual(len(self.data_fs.listdir(".")), 1)

                # Test disconnect finalization captures pending writes
                handle3_v = await handler.open(None, ua.Variant(6, ua.VariantType.Byte))
                handle3 = handle3_v[0].Value
                handler.handles[handle3]["session_id"] = "session-test-disconnect"
                disconnect_payload = b"DISCONNECT_UNIT_PAYLOAD"
                await handler.write(
                    None,
                    ua.Variant(handle3, ua.VariantType.UInt32),
                    ua.Variant(disconnect_payload, ua.VariantType.ByteString),
                )

                # Trigger disconnect
                await fm.session_disconnected("session-test-disconnect")
                self.assertEqual(len(handler.handles), 0)
                self.assertEqual(self.vfs.readbytes("firmware.bin"), disconnect_payload)

                # Test bounds: write beyond max size
                handle4_v = await handler.open(None, ua.Variant(2, ua.VariantType.Byte))
                handle4 = handle4_v[0].Value
                handler.max_file_size = 10
                with self.assertRaises(ua.UaStatusCodeError):
                    await handler.write(
                        None,
                        ua.Variant(handle4, ua.VariantType.UInt32),
                        ua.Variant(b"TOO_LONG_PAYLOAD", ua.VariantType.ByteString),
                    )

                # Test write on non-writable
                handler.writable = False
                with self.assertRaises(ua.UaStatusCodeError):
                    await handler.open(None, ua.Variant(2, ua.VariantType.Byte))

            finally:
                await server.stop()

        _run(_test())
