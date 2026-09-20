# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""Minimal blocking EtherNet/IP client for ENIP server tests."""

from __future__ import annotations

import socket
import struct

from ethernetip.cip.cpf import CpfItemType, parse_cpf
from ethernetip.cip.encapsulation import (
    SIZE as HEADER_SIZE,
    EncapsulationCommand,
    EncapsulationHeader,
)
from ethernetip.cip import mr_codec
from ethernetip.cip import standard_services as std
from ethernetip.cip.path_builder import build_path
from ethernetip.protocol.messages import (
    RegisterSessionMessage,
    SendRRDataMessage,
)


def _header(command: int, length: int = 0, session: int = 0, context: int = 0) -> bytes:
    return EncapsulationHeader(
        command=EncapsulationCommand(command),
        length=length,
        session_handle=session,
        sender_context=context,
    ).to_bytes()


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed")
        buf.extend(chunk)
    return bytes(buf)


def _recv_frame(sock: socket.socket) -> bytes:
    header = _recv_exact(sock, HEADER_SIZE)
    length = struct.unpack_from("<H", header, 2)[0]
    payload = _recv_exact(sock, length) if length else b""
    return header + payload


def _parse_list_identity_cpf(cpf_payload: bytes) -> dict:
    items = parse_cpf(cpf_payload)
    assert items, "empty ListIdentity CPF"
    data = items[0].data
    # Skip encap version(2) + sockaddr(16)
    offset = 18
    vendor_id, device_type, product_code = struct.unpack_from("<HHH", data, offset)
    offset += 6
    major, minor = data[offset], data[offset + 1]
    offset += 2
    status = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    serial_number = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    name_len = data[offset]
    offset += 1
    product_name = data[offset : offset + name_len].decode("ascii", errors="replace")
    return {
        "vendor_id": vendor_id,
        "device_type": device_type,
        "product_code": product_code,
        "product_revision": (major << 8) | minor,
        "status": status,
        "serial_number": serial_number,
        "product_name": product_name,
    }


def _parse_list_services_cpf(cpf_payload: bytes) -> str:
    items = parse_cpf(cpf_payload)
    assert items, "empty ListServices CPF"
    name = items[0].data[4:20].split(b"\x00", 1)[0].decode("ascii", errors="replace")
    return name


class EnipClient:
    """TCP or UDP client for List* and Get/Set Attribute Single."""

    def __init__(self, host: str, port: int, udp: bool = False, timeout: float = 4.0):
        self.host = host
        self.port = port
        self.udp = udp
        self.timeout = timeout
        self.session_handle = 0
        self._sock = None

    def __enter__(self):
        if self.udp:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        else:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.connect((self.host, self.port))
        self._sock.settimeout(self.timeout)
        return self

    def __exit__(self, *exc):
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def _transact(self, request: bytes) -> bytes:
        if self.udp:
            self._sock.sendto(request, (self.host, self.port))
            data, _ = self._sock.recvfrom(4096)
            return data
        self._sock.sendall(request)
        return _recv_frame(self._sock)

    def register_session(self) -> int:
        req = RegisterSessionMessage(protocol_version=1, options_flags=0).to_bytes()
        # RegisterSessionMessage defaults session_handle=0
        reply = self._transact(req)
        header = EncapsulationHeader.parse(reply)
        self.session_handle = header.session_handle
        return self.session_handle

    def list_services(self) -> str:
        req = _header(EncapsulationCommand.LIST_SERVICES)
        reply = self._transact(req)
        header = EncapsulationHeader.parse(reply)
        assert header.command == EncapsulationCommand.LIST_SERVICES
        return _parse_list_services_cpf(reply[HEADER_SIZE:])

    def list_identity(self) -> dict:
        req = _header(EncapsulationCommand.LIST_IDENTITY)
        reply = self._transact(req)
        header = EncapsulationHeader.parse(reply)
        assert header.command == EncapsulationCommand.LIST_IDENTITY
        return _parse_list_identity_cpf(reply[HEADER_SIZE:])

    def list_interfaces(self) -> dict:
        req = _header(EncapsulationCommand.LIST_INTERFACES)
        reply = self._transact(req)
        header = EncapsulationHeader.parse(reply)
        assert header.command == EncapsulationCommand.LIST_INTERFACES
        (count,) = struct.unpack_from("<H", reply, HEADER_SIZE)
        return {"count": count}

    def get_attribute_single(
        self, class_id: int, instance_id: int, attribute_id: int
    ) -> bytes:
        if not self.session_handle:
            self.register_session()
        path = build_path(class_id, instance_id, attribute_id)
        mr = mr_codec.encode_request(std.GET_ATTRIBUTE_SINGLE, path, b"")
        msg = SendRRDataMessage(
            session_handle=self.session_handle,
            cip_data=mr,
        )
        reply = self._transact(msg.to_bytes())
        return self._rr_data(reply)

    def set_attribute_single(
        self, class_id: int, instance_id: int, attribute_id: int, data: bytes
    ) -> None:
        if not self.session_handle:
            self.register_session()
        path = build_path(class_id, instance_id, attribute_id)
        mr = mr_codec.encode_request(std.SET_ATTRIBUTE_SINGLE, path, data)
        msg = SendRRDataMessage(
            session_handle=self.session_handle,
            cip_data=mr,
        )
        reply = self._transact(msg.to_bytes())
        payload = self._rr_data(reply)
        # success: empty data after status
        assert payload is not None

    @staticmethod
    def _rr_data(reply: bytes) -> bytes:
        header = EncapsulationHeader.parse(reply)
        assert header.command == EncapsulationCommand.SEND_RR_DATA
        assert header.status == 0
        # InterfaceHandle(4)+Timeout(2)+CPF
        items = parse_cpf(reply[HEADER_SIZE + 6 :])
        for item in items:
            if item.type_id == CpfItemType.UNCONNECTED_DATA:
                parsed = mr_codec.try_parse_response(item.data)
                assert parsed is not None
                _, status, data = parsed
                assert status.is_success, status
                return data
        raise AssertionError("no UnconnectedData in SendRRData reply")
