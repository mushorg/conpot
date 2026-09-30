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

"""HART-IP TCP protocol server tests."""

from __future__ import annotations

import socket
import struct
import time
import unittest

import pytest

from conpot.protocols.hartip import hartip_codec as hartip
from conpot.protocols.hartip.hartip_server import HartipServer
from conpot.utils.server_tasks import (
    drain_log_queue,
    get_log_event,
    spawn_test_server,
    teardown_test_server,
)

# nmap / dark_k3y Session Initiate probe
SESS_INIT = bytes.fromhex("010000000001000D0100004E20")
# nmap hartip-info Command 0 short-frame request
CMD0_REQ = bytes.fromhex("010003000002000D0280000082")


def _recv_pdu(sock: socket.socket) -> bytes:
    header = sock.recv(hartip.HEADER_LENGTH)
    assert len(header) == hartip.HEADER_LENGTH
    length = struct.unpack("!H", header[6:8])[0]
    rest = b""
    while len(rest) < length - hartip.HEADER_LENGTH:
        chunk = sock.recv(length - hartip.HEADER_LENGTH - len(rest))
        assert chunk
        rest += chunk
    return header + rest


@pytest.fixture(scope="class")
def hartip_server(request):
    server, handle = spawn_test_server(HartipServer, "hartip", "hartip")
    request.cls.hartip_server = server
    request.cls.server_handle = handle
    yield
    teardown_test_server(server, handle)


class TestHartipCodec(unittest.TestCase):
    def test_session_initiate_response_matches_nmap_checks(self):
        parsed = hartip.unpack_header(SESS_INIT)
        resp = hartip.handle_request(SESS_INIT, {})
        self.assertIsNotNone(resp)
        out = hartip.unpack_header(resp)
        self.assertEqual(out["version"], 1)
        self.assertEqual(out["message_type"], hartip.MSG_TYPE_RESPONSE)
        self.assertEqual(out["message_id"], hartip.MSG_ID_SESSION_INITIATE)
        self.assertEqual(out["transaction_id"], parsed["transaction_id"])
        self.assertEqual(out["payload"], parsed["payload"])

    def test_cmd0_data_length_and_identity(self):
        identity = {
            "manufacturer_id": 176,
            "expanded_device_type": 45075,
            "device_id": "aabbcc",
            "hart_revision": 7,
            "device_revision": 2,
            "software_revision": 3,
        }
        data = hartip.build_cmd0_data(identity)
        self.assertEqual(len(data), hartip.CMD0_DATA_LEN)
        self.assertEqual(data[0], 0xFE)
        self.assertEqual(struct.unpack("!H", data[1:3])[0], 45075)
        self.assertEqual(data[4], 7)
        self.assertEqual(data[5], 2)
        self.assertEqual(data[6], 3)
        self.assertEqual(data[9:12], bytes.fromhex("aabbcc"))
        self.assertEqual(struct.unpack("!H", data[17:19])[0], 176)

    def test_cmd0_pass_through_round_trip(self):
        identity = {
            "manufacturer_id": 176,
            "expanded_device_type": 45075,
            "device_id": "000001",
            "long_tag": "Conpot HART-IP Gateway",
        }
        resp = hartip.handle_request(CMD0_REQ, identity)
        out = hartip.unpack_header(resp)
        self.assertEqual(out["message_id"], hartip.MSG_ID_PASS_THROUGH)
        # nmap reads expanded device type at Lua offset 16 (1-based) => index 15
        self.assertEqual(struct.unpack("!H", resp[15:17])[0], 45075)
        frame = hartip.parse_token_passing(out["payload"])
        self.assertEqual(frame["command"], 0)
        # ACK payload: response_code, device_status, then Command 0 data.
        self.assertEqual(frame["data"][0], 0)
        self.assertEqual(frame["data"][1], 0)
        self.assertEqual(frame["data"][2], 0xFE)


@pytest.mark.usefixtures("hartip_server")
class TestHartipServer(unittest.TestCase):
    def _port(self):
        return self.hartip_server.server.server_port

    def test_connect_close_logs_session_events(self):
        drain_log_queue(self.server_handle)
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=2)
        sock.close()
        time.sleep(0.2)
        new_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual("NEW_CONNECTION", new_event["event_type"])
        lost_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual("CONNECTION_LOST", lost_event["event_type"])

    def test_session_initiate_and_cmd0_from_template(self):
        drain_log_queue(self.server_handle)
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=2)
        try:
            sock.settimeout(2)
            sock.sendall(SESS_INIT)
            init_resp = _recv_pdu(sock)
            init = hartip.unpack_header(init_resp)
            self.assertEqual(init["version"], 1)
            self.assertEqual(init["message_type"], 1)
            self.assertEqual(init["transaction_id"], 1)

            sock.sendall(CMD0_REQ)
            cmd0_resp = _recv_pdu(sock)
            self.assertEqual(struct.unpack("!H", cmd0_resp[15:17])[0], 45075)
            # manufacturer id at bytes 17-18 of Cmd0 data; short-frame layout:
            # header(8)+delim+addr+cmd+bc+rc+status+FE+type(2)+... = offset 8+6+1+2+14 = 31
            # data starts at index 14; manufacturer at data[17:19] => absolute 31:33
            self.assertEqual(struct.unpack("!H", cmd0_resp[31:33])[0], 176)
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

    def test_cmd20_returns_long_tag(self):
        drain_log_queue(self.server_handle)
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=2)
        try:
            sock.settimeout(2)
            sock.sendall(SESS_INIT)
            _recv_pdu(sock)
            sock.sendall(CMD0_REQ)
            cmd0_resp = _recv_pdu(sock)
            exp_type = struct.unpack("!H", cmd0_resp[15:17])[0]
            device_id = cmd0_resp[23:26]
            long_addr = struct.pack("!H", exp_type) + device_id
            # STX long-frame Command 20, empty data
            body = bytes([hartip.DELIM_STX_LONG]) + long_addr + bytes([20, 0])
            body += bytes([hartip.xor_checksum(body)])
            req = hartip.build_pdu(
                hartip.MSG_ID_PASS_THROUGH,
                3,
                body,
                message_type=hartip.MSG_TYPE_REQUEST,
            )
            sock.sendall(req)
            resp = _recv_pdu(sock)
            # long tag at Lua offset 19 => index 18 for long-frame ACK
            tag = resp[18 : 18 + hartip.LONG_TAG_LEN].split(b"\x00", 1)[0]
            self.assertEqual(tag.decode("latin-1"), "Conpot HART-IP Gateway")
        finally:
            sock.close()

    def test_idle_timeout_logs_connection_lost(self):
        drain_log_queue(self.server_handle)
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=2)
        try:
            # Server timeout is 5s; wait slightly longer without sending.
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
