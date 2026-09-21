# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""OPC UA protocol server tests."""

from __future__ import annotations

import asyncio
import socket
import struct
import time
import unittest

import pytest
from asyncua import Client

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
