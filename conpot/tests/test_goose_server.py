# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""R-GOOSE (IEC 61850-90-5) UDP protocol server tests."""

from __future__ import annotations

import socket
import time
import unittest

import pytest

from conpot.protocols.goose.goose_apdu import decode_goose_apdu, encode_goose_apdu
from conpot.protocols.goose.goose_server import GooseServer
from conpot.protocols.goose.session90_5 import pack_rgoose, unpack_rgoose
from conpot.utils.greenlet import (
    drain_log_queue,
    get_log_event,
    spawn_test_server,
    teardown_test_server,
)


def _sample_packet(**overrides):
    fields = {
        "gocb_ref": "IED1/LLN0$GO$gcb01",
        "time_allowed_to_live": 10000,
        "dat_set": "IED1/LLN0$dataset1",
        "go_id": "GOOSE1",
        "st_num": 1,
        "sq_num": 3,
        "conf_rev": 1,
        "all_data": [True, 7],
    }
    fields.update(overrides)
    apdu = encode_goose_apdu(**fields)
    return pack_rgoose(apdu, appid=1, spdu_number=9)


@pytest.fixture(scope="class")
def goose_server(request):
    server, greenlet = spawn_test_server(GooseServer, "goose", "goose")
    request.cls.goose_server = server
    request.cls.server_greenlet = greenlet
    yield
    teardown_test_server(server, greenlet)


class TestGooseCodec(unittest.TestCase):
    def test_apdu_and_session_round_trip(self):
        apdu = encode_goose_apdu(
            gocb_ref="IED1/LLN0$GO$gcb01",
            time_allowed_to_live=5000,
            dat_set="IED1/LLN0$dataset1",
            go_id="GOOSE1",
            st_num=2,
            sq_num=4,
            conf_rev=3,
            all_data=[False, 99],
        )
        decoded = decode_goose_apdu(apdu)
        self.assertEqual(decoded["gocb_ref"], "IED1/LLN0$GO$gcb01")
        self.assertEqual(decoded["st_num"], 2)
        self.assertEqual(decoded["sq_num"], 4)
        self.assertEqual(decoded["all_data"], [False, 99])

        packet = pack_rgoose(apdu, appid=0x1234, spdu_number=11)
        framed = unpack_rgoose(packet)
        self.assertEqual(framed["appid"], 0x1234)
        self.assertEqual(framed["spdu_number"], 11)
        self.assertEqual(decode_goose_apdu(framed["goose_apdu"])["go_id"], "GOOSE1")


@pytest.mark.usefixtures("goose_server")
class TestGooseServer(unittest.TestCase):
    def _port(self):
        return self.goose_server.server.server_port

    def test_rx_logs_connection_and_request(self):
        drain_log_queue(self.server_greenlet)
        packet = _sample_packet()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(packet, ("127.0.0.1", self._port()))
        finally:
            sock.close()

        new_event = get_log_event(self.server_greenlet, timeout=2)
        self.assertEqual(new_event["event_type"], "NEW_CONNECTION")
        request_event = get_log_event(self.server_greenlet, timeout=2)
        self.assertEqual(request_event["event_type"], "REQUEST")
        request = request_event["request"]
        self.assertEqual(request["appid"], 1)
        self.assertEqual(request["gocb_ref"], "IED1/LLN0$GO$gcb01")
        self.assertEqual(request["st_num"], 1)
        self.assertEqual(request["sq_num"], 3)
        lost_event = get_log_event(self.server_greenlet, timeout=2)
        self.assertEqual(lost_event["event_type"], "CONNECTION_LOST")

    def test_tx_publishes_template_identity(self):
        # Publisher should be advancing sequence numbers on its interval.
        before = self.goose_server.sq_num
        deadline = time.time() + 2.0
        while time.time() < deadline and self.goose_server.sq_num == before:
            time.sleep(0.05)
        self.assertGreater(
            self.goose_server.sq_num,
            before,
            "publish loop did not advance sq_num",
        )

        packet = self.goose_server._build_publish_packet()
        framed = unpack_rgoose(packet)
        apdu = decode_goose_apdu(framed["goose_apdu"])
        self.assertEqual(framed["appid"], 1)
        self.assertEqual(apdu["gocb_ref"], "IED1/LLN0$GO$gcb01")
        self.assertEqual(apdu["go_id"], "GOOSE1")
        self.assertEqual(apdu["all_data"], [False, 42])

        # Deliver one published datagram to a local capture socket.
        capture = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            capture.bind(("127.0.0.1", 0))
            capture.settimeout(2.0)
            cap_port = capture.getsockname()[1]
            loop = self.server_greenlet._loop
            loop.call_soon_threadsafe(
                self.goose_server.server.sendto,
                packet,
                ("127.0.0.1", cap_port),
            )
            data, _addr = capture.recvfrom(65535)
        finally:
            capture.close()

        framed_rx = unpack_rgoose(data)
        self.assertEqual(framed_rx["appid"], 1)
        self.assertEqual(
            decode_goose_apdu(framed_rx["goose_apdu"])["gocb_ref"],
            "IED1/LLN0$GO$gcb01",
        )

    def test_garbage_udp_does_not_traceback(self):
        drain_log_queue(self.server_greenlet)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(b"", ("127.0.0.1", self._port()))
            sock.sendto(b"\x00\x01\x02", ("127.0.0.1", self._port()))
            sock.sendto(b"\xa1\x01", ("127.0.0.1", self._port()))
        finally:
            sock.close()
        time.sleep(0.2)
        # No crash; ignore may produce no events or a decode-error session.
        drain_log_queue(self.server_greenlet)
