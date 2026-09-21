# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""DNP3 protocol server tests."""

from __future__ import annotations

import asyncio
import socket
import struct
import time
import unittest

import pytest
from dnp3.core.enums import LinkFunctionCode
from dnp3.datalink.builder import build_reset_link_state, build_unconfirmed_user_data
from dnp3.datalink.parser import FrameParser
from dnp3.master import Master
from dnp3.master.handler import ResponseInfo, SOEHandler
from dnp3.transport.segment import TransportSegment

from conpot.protocols.dnp3.dnp3_server import DNP3Server
from conpot.utils.greenlet import (
    drain_log_queue,
    get_log_event,
    spawn_test_server,
    teardown_test_server,
)

MASTER_ADDR = 3
OUTSTATION_ADDR = 1
READ_TIMEOUT = 2.0


class RecordingHandler(SOEHandler):
    def __init__(self) -> None:
        self.binary_inputs: dict[int, bool] = {}
        self.analog_inputs: dict[int, float] = {}

    def on_binary_input(self, values, info: ResponseInfo) -> None:
        self.binary_inputs.update({v.index: v.value for v in values})

    def on_analog_input(self, values, info: ResponseInfo) -> None:
        self.analog_inputs.update({v.index: v.value for v in values})


def _frame_request(request_bytes: bytes) -> bytes:
    segment = TransportSegment.build(fir=True, fin=True, seq=0, payload=request_bytes)
    frame = build_unconfirmed_user_data(
        destination=OUTSTATION_ADDR,
        source=MASTER_ADDR,
        dir_from_master=True,
        user_data=segment.to_bytes(),
    )
    return frame.to_bytes()


async def _integrity_poll(host: str, port: int) -> RecordingHandler:
    handler = RecordingHandler()
    master = Master(handler=handler)
    reader, writer = await asyncio.open_connection(host, port)
    parser = FrameParser()
    try:
        writer.write(
            build_reset_link_state(
                destination=OUTSTATION_ADDR,
                source=MASTER_ADDR,
                dir_from_master=True,
            ).to_bytes()
        )
        await writer.drain()
        ack_data = await asyncio.wait_for(reader.read(4096), timeout=READ_TIMEOUT)
        ack_frames = list(parser.feed(ack_data))
        assert ack_frames, "outstation sent no link ACK"
        assert ack_frames[0].header.control.function_code == LinkFunctionCode.SEC_ACK

        writer.write(_frame_request(master.build_integrity_poll().to_bytes()))
        await writer.drain()

        response_data = await asyncio.wait_for(reader.read(4096), timeout=READ_TIMEOUT)
        for frame in parser.feed(response_data):
            if not frame.user_data:
                continue
            segment = TransportSegment.from_bytes(frame.user_data)
            assert master.process_response(segment.payload) is not None
    finally:
        writer.close()
        try:
            await asyncio.wait_for(writer.wait_closed(), timeout=READ_TIMEOUT)
        except Exception:
            pass
    return handler


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(scope="class")
def dnp3_server(request):
    server, greenlet = spawn_test_server(DNP3Server, "dnp3", "dnp3")
    request.cls.dnp3_server = server
    request.cls.server_greenlet = greenlet
    yield
    teardown_test_server(server, greenlet)


@pytest.mark.usefixtures("dnp3_server")
class TestDNP3Server(unittest.TestCase):
    def _port(self):
        return self.dnp3_server.server.server_port

    def test_new_connection_and_lost_events(self):
        drain_log_queue(self.server_greenlet)
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=2)
        sock.close()
        # Give the handler a moment to finish CONNECTION_LOST.
        time.sleep(0.2)
        new_event = get_log_event(self.server_greenlet, timeout=2)
        self.assertEqual("NEW_CONNECTION", new_event["event_type"])
        lost_event = get_log_event(self.server_greenlet, timeout=2)
        self.assertEqual("CONNECTION_LOST", lost_event["event_type"])

    def test_integrity_poll_returns_template_points(self):
        drain_log_queue(self.server_greenlet)
        handler = _run(_integrity_poll("127.0.0.1", self._port()))
        self.assertEqual(handler.binary_inputs, {0: False, 1: True})
        self.assertEqual(handler.analog_inputs, {0: 25.0, 1: 100.0})

        # Session should have logged connection + at least one request.
        events = []
        for _ in range(8):
            try:
                events.append(get_log_event(self.server_greenlet, timeout=1))
            except Exception:
                break
        types = [e["event_type"] for e in events]
        self.assertIn("NEW_CONNECTION", types)
        self.assertIn("REQUEST", types)

    def test_concurrent_connections_stay_alive(self):
        """Regression: Conpot must not drop the first client when a second connects."""
        drain_log_queue(self.server_greenlet)
        port = self._port()

        async def _hold_and_second():
            r1, w1 = await asyncio.open_connection("127.0.0.1", port)
            try:
                # First connection: reset link and keep socket open.
                w1.write(
                    build_reset_link_state(
                        destination=OUTSTATION_ADDR,
                        source=MASTER_ADDR,
                        dir_from_master=True,
                    ).to_bytes()
                )
                await w1.drain()
                ack1 = await asyncio.wait_for(r1.read(4096), timeout=READ_TIMEOUT)
                self.assertTrue(ack1)

                # Second connection while first is still open.
                r2, w2 = await asyncio.open_connection("127.0.0.1", port)
                try:
                    w2.write(
                        build_reset_link_state(
                            destination=OUTSTATION_ADDR,
                            source=MASTER_ADDR + 1,
                            dir_from_master=True,
                        ).to_bytes()
                    )
                    await w2.drain()
                    ack2 = await asyncio.wait_for(r2.read(4096), timeout=READ_TIMEOUT)
                    self.assertTrue(ack2)

                    # First socket must still accept traffic (not reset).
                    w1.write(
                        build_reset_link_state(
                            destination=OUTSTATION_ADDR,
                            source=MASTER_ADDR,
                            dir_from_master=True,
                        ).to_bytes()
                    )
                    await w1.drain()
                    ack1b = await asyncio.wait_for(r1.read(4096), timeout=READ_TIMEOUT)
                    self.assertTrue(ack1b)
                finally:
                    w2.close()
                    await w2.wait_closed()
            finally:
                w1.close()
                await w1.wait_closed()

        _run(_hold_and_second())

    def test_peer_rst_is_not_a_session_crash(self):
        """nmap -sV RSTs after a banner wait; that must not traceback."""
        drain_log_queue(self.server_greenlet)
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=2)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        sock.close()
        time.sleep(0.3)
        new_event = get_log_event(self.server_greenlet, timeout=2)
        self.assertEqual("NEW_CONNECTION", new_event["event_type"])
        lost_event = get_log_event(self.server_greenlet, timeout=2)
        self.assertEqual("CONNECTION_LOST", lost_event["event_type"])
