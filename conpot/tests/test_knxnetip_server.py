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

"""KNXnet/IP UDP protocol server tests."""

from __future__ import annotations

import socket
import struct
import unittest

import pytest

from conpot.protocols.knxnetip import knxip_codec as knxip
from conpot.protocols.knxnetip.knxnetip_server import KnxnetipServer
from conpot.utils.server_tasks import (
    drain_log_queue,
    get_log_event,
    spawn_test_server,
    teardown_test_server,
)


def _description_request(ip="127.0.0.1", port=3671) -> bytes:
    body = knxip.pack_hpai(ip, port)
    total = knxip.HEADER_SIZE + len(body)
    return knxip.pack_header(knxip.SERVICE_DESCRIPTION_REQUEST, total) + body


def _search_request(ip="127.0.0.1", port=3671) -> bytes:
    body = knxip.pack_hpai(ip, port)
    total = knxip.HEADER_SIZE + len(body)
    return knxip.pack_header(knxip.SERVICE_SEARCH_REQUEST, total) + body


@pytest.fixture(scope="class")
def knxnetip_server(request):
    server, handle = spawn_test_server(KnxnetipServer, "knxnetip", "knxnetip")
    request.cls.knxnetip_server = server
    request.cls.server_handle = handle
    yield
    teardown_test_server(server, handle)


class TestKnxipCodec(unittest.TestCase):
    def test_individual_address_round_trip(self):
        raw = knxip.parse_individual_address("1.1.15")
        self.assertEqual(knxip.format_individual_address(raw), "1.1.15")

    def test_description_response_contains_identity(self):
        identity = {
            "friendly_name": "Conpot KNX IP",
            "individual_address": "1.1.1",
            "serial_number": "00fa00000001",
            "mac_address": "00:fa:00:00:00:01",
            "medium": 2,
            "multicast_group": "224.0.23.12",
        }
        frame = knxip.build_description_response(identity)
        parsed = knxip.unpack_header(frame)
        self.assertEqual(parsed["service_type"], knxip.SERVICE_DESCRIPTION_RESPONSE)
        self.assertEqual(knxip.extract_friendly_name(frame), "Conpot KNX IP")
        self.assertEqual(knxip.extract_individual_address(frame), "1.1.1")

    def test_search_response_starts_with_hpai(self):
        identity = {
            "friendly_name": "Lab Gateway",
            "individual_address": "2.3.4",
            "serial_number": "aabbccddeeff",
            "mac_address": "aa:bb:cc:dd:ee:ff",
        }
        frame = knxip.build_search_response("10.0.0.5", 3671, identity)
        parsed = knxip.unpack_header(frame)
        self.assertEqual(parsed["service_type"], knxip.SERVICE_SEARCH_RESPONSE)
        hpai = parsed["body"][:8]
        self.assertEqual(hpai[0], knxip.HPAI_LENGTH)
        self.assertEqual(socket.inet_ntoa(hpai[2:6]), "10.0.0.5")
        self.assertEqual(struct.unpack("!H", hpai[6:8])[0], 3671)
        self.assertEqual(knxip.extract_friendly_name(frame), "Lab Gateway")
        self.assertEqual(knxip.extract_individual_address(frame), "2.3.4")


@pytest.mark.usefixtures("knxnetip_server")
class TestKnxnetipServer(unittest.TestCase):
    def _port(self):
        return self.knxnetip_server.server.server_port

    def _exchange(self, request: bytes) -> bytes:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        try:
            sock.sendto(request, ("127.0.0.1", self._port()))
            response, _addr = sock.recvfrom(1024)
            return response
        finally:
            sock.close()

    def test_description_request_logs_and_responds(self):
        drain_log_queue(self.server_handle)
        response = self._exchange(_description_request(port=self._port()))

        parsed = knxip.unpack_header(response)
        self.assertEqual(parsed["service_type"], knxip.SERVICE_DESCRIPTION_RESPONSE)
        self.assertEqual(knxip.extract_friendly_name(response), "Conpot KNX IP")
        self.assertEqual(knxip.extract_individual_address(response), "1.1.1")

        new_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual(new_event["event_type"], "NEW_CONNECTION")
        request_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual(request_event["event_type"], "REQUEST")
        self.assertEqual(request_event["request"]["service"], "DESCRIPTION_REQUEST")
        lost_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual(lost_event["event_type"], "CONNECTION_LOST")

    def test_search_request_returns_template_identity(self):
        drain_log_queue(self.server_handle)
        response = self._exchange(_search_request(port=self._port()))

        parsed = knxip.unpack_header(response)
        self.assertEqual(parsed["service_type"], knxip.SERVICE_SEARCH_RESPONSE)
        self.assertEqual(knxip.extract_friendly_name(response), "Conpot KNX IP")
        self.assertEqual(knxip.extract_individual_address(response), "1.1.1")

        new_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual(new_event["event_type"], "NEW_CONNECTION")
        request_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual(request_event["event_type"], "REQUEST")
        self.assertEqual(request_event["request"]["service"], "SEARCH_REQUEST")
        lost_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual(lost_event["event_type"], "CONNECTION_LOST")

    def test_garbage_datagram_ignored(self):
        drain_log_queue(self.server_handle)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.3)
        try:
            sock.sendto(b"\x00\x00not-knx", ("127.0.0.1", self._port()))
            with self.assertRaises(socket.timeout):
                sock.recvfrom(1024)
        finally:
            sock.close()
        # No session events for non-KNXnet/IP traffic.
        with self.assertRaises(Exception):
            get_log_event(self.server_handle, timeout=0.5)
