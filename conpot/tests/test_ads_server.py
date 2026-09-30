# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Beckhoff ADS/AMS TCP protocol server tests."""

from __future__ import annotations

import socket
import struct
import time
import unittest

import pytest

from conpot.protocols.ads import ads_codec as ads
from conpot.protocols.ads.ads_server import AdsServer
from conpot.utils.server_tasks import (
    drain_log_queue,
    get_log_event,
    spawn_test_server,
    teardown_test_server,
)

TARGET_NET_ID = ads.parse_ams_net_id("192.168.1.1.1.1")
SOURCE_NET_ID = ads.parse_ams_net_id("10.0.0.1.1.1")
TARGET_PORT = 851
SOURCE_PORT = 32905


def _recv_frame(sock: socket.socket) -> bytes:
    header = sock.recv(ads.AMS_TCP_HEADER_LENGTH)
    assert len(header) == ads.AMS_TCP_HEADER_LENGTH
    _reserved, length = struct.unpack_from("<HI", header, 0)
    rest = b""
    while len(rest) < length:
        chunk = sock.recv(length - len(rest))
        assert chunk
        rest += chunk
    return header + rest


def _read_device_info_req(invoke_id: int = 1) -> bytes:
    return ads.build_request(
        target_net_id=TARGET_NET_ID,
        target_port=TARGET_PORT,
        source_net_id=SOURCE_NET_ID,
        source_port=SOURCE_PORT,
        command_id=ads.CMD_READ_DEVICE_INFO,
        invoke_id=invoke_id,
    )


def _read_req(
    index_group: int, index_offset: int, length: int, invoke_id: int = 2
) -> bytes:
    payload = struct.pack("<III", index_group, index_offset, length)
    return ads.build_request(
        target_net_id=TARGET_NET_ID,
        target_port=TARGET_PORT,
        source_net_id=SOURCE_NET_ID,
        source_port=SOURCE_PORT,
        command_id=ads.CMD_READ,
        invoke_id=invoke_id,
        payload=payload,
    )


@pytest.fixture(scope="class")
def ads_server(request):
    server, handle = spawn_test_server(AdsServer, "ads", "ads")
    request.cls.ads_server = server
    request.cls.server_handle = handle
    yield
    teardown_test_server(server, handle)


class TestAdsCodec(unittest.TestCase):
    def test_read_device_info_round_trip(self):
        device = {
            "device_name": "Conpot TwinCAT",
            "version_major": 3,
            "version_minor": 1,
            "version_build": 0,
            "symbols": [],
        }
        req = _read_device_info_req()
        resp = ads.handle_request(req, device)
        parsed = ads.unpack_ams_tcp_frame(resp)
        self.assertEqual(parsed["command_id"], ads.CMD_READ_DEVICE_INFO)
        self.assertEqual(parsed["state_flags"], ads.STATE_RESPONSE)
        self.assertEqual(parsed["invoke_id"], 1)
        self.assertEqual(parsed["source_net_id"], TARGET_NET_ID)
        self.assertEqual(parsed["target_net_id"], SOURCE_NET_ID)
        result, major, minor, build = struct.unpack_from("<IBBH", parsed["payload"], 0)
        self.assertEqual(result, 0)
        self.assertEqual(major, 3)
        self.assertEqual(minor, 1)
        self.assertEqual(build, 0)
        name = parsed["payload"][8:24].split(b"\x00", 1)[0]
        self.assertEqual(name, b"Conpot TwinCAT")

    def test_read_symbol_by_index(self):
        device = {
            "device_name": "x",
            "symbols": [
                {
                    "name": "MAIN.bRunning",
                    "index_group": 16448,
                    "index_offset": 0,
                    "value": bytearray(b"\x01"),
                }
            ],
        }
        req = _read_req(16448, 0, 1)
        resp = ads.handle_request(req, device)
        parsed = ads.unpack_ams_tcp_frame(resp)
        result, length = struct.unpack_from("<II", parsed["payload"], 0)
        self.assertEqual(result, 0)
        self.assertEqual(length, 1)
        self.assertEqual(parsed["payload"][8:9], b"\x01")


@pytest.mark.usefixtures("ads_server")
class TestAdsServer(unittest.TestCase):
    def _port(self):
        return self.ads_server.server.server_port

    def test_connect_close_logs_session_events(self):
        drain_log_queue(self.server_handle)
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=2)
        sock.close()
        time.sleep(0.2)
        new_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual("NEW_CONNECTION", new_event["event_type"])
        lost_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual("CONNECTION_LOST", lost_event["event_type"])

    def test_read_device_info_from_template(self):
        drain_log_queue(self.server_handle)
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=2)
        try:
            sock.settimeout(2)
            sock.sendall(_read_device_info_req())
            resp = _recv_frame(sock)
            parsed = ads.unpack_ams_tcp_frame(resp)
            self.assertEqual(parsed["command_id"], ads.CMD_READ_DEVICE_INFO)
            name = parsed["payload"][8:24].split(b"\x00", 1)[0]
            self.assertEqual(name, b"Conpot TwinCAT")
            major, minor = parsed["payload"][4], parsed["payload"][5]
            self.assertEqual(major, 3)
            self.assertEqual(minor, 1)
        finally:
            sock.close()

        time.sleep(0.2)
        events = []
        for _ in range(8):
            try:
                events.append(get_log_event(self.server_handle, timeout=1))
            except Exception:
                break
        types = [e["event_type"] for e in events]
        self.assertIn("NEW_CONNECTION", types)
        self.assertIn("REQUEST", types)
        self.assertIn("CONNECTION_LOST", types)

    def test_read_symbol_from_template(self):
        drain_log_queue(self.server_handle)
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=2)
        try:
            sock.settimeout(2)
            sock.sendall(_read_req(16448, 0, 1))
            resp = _recv_frame(sock)
            parsed = ads.unpack_ams_tcp_frame(resp)
            result, length = struct.unpack_from("<II", parsed["payload"], 0)
            self.assertEqual(result, 0)
            self.assertEqual(length, 1)
            self.assertEqual(parsed["payload"][8:9], b"\x01")
        finally:
            sock.close()

    def test_idle_timeout_logs_connection_lost(self):
        drain_log_queue(self.server_handle)
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=2)
        try:
            time.sleep(5.5)
        finally:
            sock.close()
        time.sleep(0.3)
        new_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual("NEW_CONNECTION", new_event["event_type"])
        lost_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual("CONNECTION_LOST", lost_event["event_type"])

    def test_rst_peer_logs_connection_events(self):
        drain_log_queue(self.server_handle)
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=2)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        sock.close()
        time.sleep(0.3)
        new_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual("NEW_CONNECTION", new_event["event_type"])
        lost_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual("CONNECTION_LOST", lost_event["event_type"])
