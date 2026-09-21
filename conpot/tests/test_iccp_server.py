# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""ICCP / TASE.2 protocol server tests."""

from __future__ import annotations

import socket
import struct
import time
import unittest

import pytest

from conpot.protocols.iccp.ber import (
    decode_tlv,
    encode_integer,
    encode_null,
    encode_sequence,
    encode_tag_length_value,
    encode_visible_string,
)
from conpot.protocols.iccp.cotp import TPDU_CC, TPDU_CR, TPDU_DT, pack_dt_tpkt
from conpot.protocols.iccp.iccp_server import ICCPServer
from conpot.protocols.iccp.iso_upper import (
    extract_mms_pdu,
    wrap_presentation_user,
    wrap_session_data,
)
from conpot.protocols.iccp.mms import (
    TAG_CONFIRMED_RESPONSE,
    extract_mms_from_presentation,
)
from conpot.protocols.iccp.tpkt import TPKT
from conpot.utils.server_tasks import (
    drain_log_queue,
    get_log_event,
    spawn_test_server,
    teardown_test_server,
)

# Minimal COTP CR (ISO-on-TCP) without TSAPs — sufficient for association.
CR_TPKT = bytes.fromhex("0300000b06e00000000100")

# Session CONNECT + Presentation + ACSE AARQ + MMS Initiate (from public probes).
MMS_INITIATE = bytes(
    [
        0x03,
        0x00,
        0x00,
        0xC5,
        0x02,
        0xF0,
        0x80,
        0x0D,
        0xBC,
        0x05,
        0x06,
        0x13,
        0x01,
        0x00,
        0x16,
        0x01,
        0x02,
        0x14,
        0x02,
        0x00,
        0x02,
        0x33,
        0x02,
        0x00,
        0x01,
        0x34,
        0x02,
        0x00,
        0x02,
        0xC1,
        0xA6,
        0x31,
        0x81,
        0xA3,
        0xA0,
        0x03,
        0x80,
        0x01,
        0x01,
        0xA2,
        0x81,
        0x9B,
        0x80,
        0x02,
        0x07,
        0x80,
        0x81,
        0x04,
        0x00,
        0x00,
        0x00,
        0x01,
        0x82,
        0x04,
        0x00,
        0x00,
        0x00,
        0x02,
        0xA4,
        0x23,
        0x30,
        0x0F,
        0x02,
        0x01,
        0x01,
        0x06,
        0x04,
        0x52,
        0x01,
        0x00,
        0x01,
        0x30,
        0x04,
        0x06,
        0x02,
        0x51,
        0x01,
        0x30,
        0x10,
        0x02,
        0x01,
        0x03,
        0x06,
        0x05,
        0x28,
        0xCA,
        0x22,
        0x02,
        0x01,
        0x30,
        0x04,
        0x06,
        0x02,
        0x51,
        0x01,
        0x88,
        0x02,
        0x06,
        0x00,
        0x61,
        0x60,
        0x30,
        0x5E,
        0x02,
        0x01,
        0x01,
        0xA0,
        0x59,
        0x60,
        0x57,
        0x80,
        0x02,
        0x07,
        0x80,
        0xA1,
        0x07,
        0x06,
        0x05,
        0x28,
        0xCA,
        0x22,
        0x01,
        0x01,
        0xA2,
        0x04,
        0x06,
        0x02,
        0x29,
        0x02,
        0xA3,
        0x03,
        0x02,
        0x01,
        0x02,
        0xA6,
        0x04,
        0x06,
        0x02,
        0x29,
        0x01,
        0xA7,
        0x03,
        0x02,
        0x01,
        0x01,
        0xBE,
        0x32,
        0x28,
        0x30,
        0x06,
        0x02,
        0x51,
        0x01,
        0x02,
        0x01,
        0x03,
        0xA0,
        0x27,
        0xA8,
        0x25,
        0x80,
        0x02,
        0x7D,
        0x00,
        0x81,
        0x01,
        0x14,
        0x82,
        0x01,
        0x14,
        0x83,
        0x01,
        0x04,
        0xA4,
        0x16,
        0x80,
        0x01,
        0x01,
        0x81,
        0x03,
        0x05,
        0xFB,
        0x00,
        0x82,
        0x0C,
        0x03,
        0x6E,
        0x1D,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x64,
        0x00,
        0x01,
        0x98,
    ]
)


def _recv_tpkt(sock: socket.socket) -> bytes:
    header = sock.recv(4, socket.MSG_WAITALL)
    if len(header) < 4:
        raise AssertionError("short TPKT header")
    length = struct.unpack("!BBH", header)[2]
    rest = sock.recv(length - 4, socket.MSG_WAITALL)
    return header + rest


def _associate(sock: socket.socket) -> bytes:
    sock.sendall(CR_TPKT)
    cc = _recv_tpkt(sock)
    cotp_type = cc[5]
    assert cotp_type == TPDU_CC
    sock.sendall(bytes(MMS_INITIATE))
    accept = _recv_tpkt(sock)
    assert accept[5] == TPDU_DT
    mms = extract_mms_pdu(accept[7:])
    assert mms is not None and mms[0] == 0xA9
    return accept


def _send_mms(sock: socket.socket, mms_pdu: bytes) -> bytes:
    packet = pack_dt_tpkt(wrap_session_data(wrap_presentation_user(mms_pdu)))
    sock.sendall(packet)
    return _recv_tpkt(sock)


def _mms_from_dt(packet: bytes) -> bytes:
    assert packet[5] == TPDU_DT
    mms = extract_mms_pdu(packet[7:])
    if mms is None:
        mms = extract_mms_from_presentation(packet[7:])
    assert mms is not None
    return mms


def _parse_identify(mms: bytes) -> tuple[str, str, str]:
    assert mms[0] == TAG_CONFIRMED_RESPONSE
    _, body, _ = decode_tlv(mms, 0)
    offset = 0
    vendor = model = revision = ""
    while offset < len(body):
        tag, value, offset = decode_tlv(body, offset)
        if (tag & 0x1F) == 2 and (tag & 0xA0) == 0xA0:
            # identify response SEQUENCE
            inner = 0
            while inner < len(value):
                it, iv, inner = decode_tlv(value, inner)
                text = iv.decode("ascii", errors="replace")
                num = it & 0x1F
                if num == 0:
                    vendor = text
                elif num == 1:
                    model = text
                elif num == 2:
                    revision = text
    return vendor, model, revision


def _build_identify(invoke_id: int = 1) -> bytes:
    return encode_sequence(0xA0, encode_integer(0x02, invoke_id), encode_null(0x82))


def _build_get_name_list_domain(invoke_id: int, domain: str) -> bytes:
    scope = encode_tag_length_value(
        0xA1, encode_visible_string(0x81, domain)  # domainSpecific
    )
    obj_class = encode_tag_length_value(0xA0, encode_integer(0x80, 0))  # namedVariable
    return encode_sequence(
        0xA0,
        encode_integer(0x02, invoke_id),
        encode_sequence(0xA1, obj_class, scope),
    )


def _build_read(invoke_id: int, domain: str, item: str) -> bytes:
    object_name = encode_sequence(
        0xA1,  # domain-specific
        encode_visible_string(0x1A, domain),
        encode_visible_string(0x1A, item),
    )
    var_spec = encode_tag_length_value(0xA0, object_name)  # name
    list_of_var = encode_tag_length_value(0xA0, encode_sequence(0x30, var_spec))
    vas = encode_tag_length_value(0xA1, list_of_var)
    return encode_sequence(
        0xA0,
        encode_integer(0x02, invoke_id),
        encode_sequence(0xA4, vas),
    )


@pytest.fixture(scope="class")
def iccp_server(request):
    server, handle = spawn_test_server(ICCPServer, "iccp", "iccp")
    request.cls.iccp_server = server
    request.cls.server_handle = handle
    yield
    teardown_test_server(server, handle)


@pytest.mark.usefixtures("iccp_server")
class TestICCPServer(unittest.TestCase):
    def _port(self):
        return self.iccp_server.server.server_port

    def test_new_connection_and_lost_events(self):
        drain_log_queue(self.server_handle)
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=2)
        sock.close()
        time.sleep(0.2)
        new_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual("NEW_CONNECTION", new_event["event_type"])
        lost_event = get_log_event(self.server_handle, timeout=2)
        self.assertEqual("CONNECTION_LOST", lost_event["event_type"])

    def test_associate_and_identify(self):
        drain_log_queue(self.server_handle)
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=3)
        try:
            _associate(sock)
            resp = _send_mms(sock, _build_identify(1))
            mms = _mms_from_dt(resp)
            vendor, model, revision = _parse_identify(mms)
            self.assertEqual(vendor, "Conpot")
            self.assertEqual(model, "ICCP-TASE2")
            self.assertEqual(revision, "1.0")
        finally:
            sock.close()

        events = []
        for _ in range(12):
            try:
                events.append(get_log_event(self.server_handle, timeout=1))
            except Exception:
                break
        types = [e["event_type"] for e in events]
        self.assertIn("NEW_CONNECTION", types)
        self.assertIn("REQUEST", types)
        self.assertIn("CONNECTION_LOST", types)

    def test_read_template_point(self):
        drain_log_queue(self.server_handle)
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=3)
        try:
            _associate(sock)
            # Domain name list should include configured points.
            gnl = _send_mms(sock, _build_get_name_list_domain(2, "VCC"))
            gnl_mms = _mms_from_dt(gnl)
            self.assertEqual(gnl_mms[0], TAG_CONFIRMED_RESPONSE)
            self.assertIn(b"BreakerStatus", gnl_mms)
            self.assertIn(b"AnalogMW", gnl_mms)

            read = _send_mms(sock, _build_read(3, "VCC", "BreakerStatus"))
            read_mms = _mms_from_dt(read)
            self.assertEqual(read_mms[0], TAG_CONFIRMED_RESPONSE)
            self.assertIn(bytes.fromhex("8301ff"), read_mms)
        finally:
            sock.close()

    def test_idle_timeout_no_traceback(self):
        drain_log_queue(self.server_handle)
        # Temporarily use a short timeout for this connection path by sending CR only.
        sock = socket.create_connection(("127.0.0.1", self._port()), timeout=3)
        try:
            sock.sendall(CR_TPKT)
            _recv_tpkt(sock)
            # Do not send more data; server timeout should end the session cleanly.
            time.sleep(self.iccp_server.timeout + 1.0)
        finally:
            try:
                sock.close()
            except Exception:
                pass
        events = []
        for _ in range(6):
            try:
                events.append(get_log_event(self.server_handle, timeout=2))
            except Exception:
                break
        types = [e["event_type"] for e in events]
        self.assertIn("NEW_CONNECTION", types)
        self.assertIn("CONNECTION_LOST", types)

    def test_rst_peer_no_traceback(self):
        drain_log_queue(self.server_handle)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        sock.settimeout(3)
        sock.connect(("127.0.0.1", self._port()))
        sock.sendall(CR_TPKT)
        try:
            _recv_tpkt(sock)
        except Exception:
            pass
        sock.close()  # RST via SO_LINGER
        time.sleep(0.3)
        events = []
        for _ in range(6):
            try:
                events.append(get_log_event(self.server_handle, timeout=1))
            except Exception:
                break
        types = [e["event_type"] for e in events]
        self.assertIn("NEW_CONNECTION", types)
        self.assertIn("CONNECTION_LOST", types)
