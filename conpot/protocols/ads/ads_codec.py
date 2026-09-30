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

"""Minimal AMS/TCP framing for Beckhoff ADS honeypot responses."""

from __future__ import annotations

import struct
from typing import Any

AMS_TCP_HEADER_LENGTH = 6
AMS_HEADER_LENGTH = 32
MAX_FRAME_LENGTH = 4096

# ADS command IDs (request).
CMD_READ_DEVICE_INFO = 1
CMD_READ = 2
CMD_WRITE = 3
CMD_READ_STATE = 4
CMD_WRITE_CONTROL = 5

CMD_NAMES = {
    CMD_READ_DEVICE_INFO: "READ_DEVICE_INFO",
    CMD_READ: "READ",
    CMD_WRITE: "WRITE",
    CMD_READ_STATE: "READ_STATE",
    CMD_WRITE_CONTROL: "WRITE_CONTROL",
}

# State flags: ADS command (bit 2) + response (bit 0).
STATE_ADS_COMMAND = 0x0004
STATE_RESPONSE = 0x0005

# Common ADS result codes.
ADSERR_NOERR = 0
ADSERR_DEVICE_SYMBOLNOTFOUND = 0x710
ADSERR_DEVICE_INVALIDSIZE = 0x705
ADSERR_DEVICE_INVALIDDATA = 0x706

DEVICE_NAME_LEN = 16


class AdsError(ValueError):
    """Invalid or unsupported AMS/TCP frame."""


def parse_ams_net_id(value: str) -> bytes:
    """Parse dotted AMS NetId ``a.b.c.d.e.f`` into 6 bytes."""
    parts = value.strip().split(".")
    if len(parts) != 6:
        raise AdsError(f"invalid AMS NetId {value!r}")
    try:
        octets = [int(p) for p in parts]
    except ValueError as exc:
        raise AdsError(f"invalid AMS NetId {value!r}") from exc
    if any(o < 0 or o > 255 for o in octets):
        raise AdsError(f"invalid AMS NetId {value!r}")
    return bytes(octets)


def format_ams_net_id(raw: bytes) -> str:
    if len(raw) != 6:
        return raw.hex()
    return ".".join(str(b) for b in raw)


def unpack_ams_tcp_frame(data: bytes) -> dict[str, Any]:
    """Decode one AMS/TCP frame (header + AMS header + payload)."""
    if len(data) < AMS_TCP_HEADER_LENGTH + AMS_HEADER_LENGTH:
        raise AdsError("frame too short")

    reserved, length = struct.unpack_from("<HI", data, 0)
    if reserved != 0:
        raise AdsError(f"unexpected AMS/TCP reserved field {reserved}")
    if length < AMS_HEADER_LENGTH or length > MAX_FRAME_LENGTH:
        raise AdsError(f"invalid AMS length {length}")
    if len(data) < AMS_TCP_HEADER_LENGTH + length:
        raise AdsError("incomplete AMS frame")

    ams = data[AMS_TCP_HEADER_LENGTH : AMS_TCP_HEADER_LENGTH + length]
    (
        target_net_id,
        target_port,
        source_net_id,
        source_port,
        command_id,
        state_flags,
        data_length,
        error_code,
        invoke_id,
    ) = struct.unpack_from("<6sH6sHHHIII", ams, 0)

    if data_length != length - AMS_HEADER_LENGTH:
        raise AdsError("AMS data length mismatch")
    payload = ams[AMS_HEADER_LENGTH : AMS_HEADER_LENGTH + data_length]

    return {
        "target_net_id": target_net_id,
        "target_port": target_port,
        "source_net_id": source_net_id,
        "source_port": source_port,
        "command_id": command_id,
        "command_name": CMD_NAMES.get(command_id, f"CMD_{command_id}"),
        "state_flags": state_flags,
        "data_length": data_length,
        "error_code": error_code,
        "invoke_id": invoke_id,
        "payload": payload,
        "raw": data[: AMS_TCP_HEADER_LENGTH + length],
    }


def pack_ams_tcp_frame(
    *,
    target_net_id: bytes,
    target_port: int,
    source_net_id: bytes,
    source_port: int,
    command_id: int,
    state_flags: int,
    invoke_id: int,
    payload: bytes = b"",
    error_code: int = 0,
) -> bytes:
    """Build an AMS/TCP frame."""
    if len(target_net_id) != 6 or len(source_net_id) != 6:
        raise AdsError("AMS NetId must be 6 bytes")
    if len(payload) > MAX_FRAME_LENGTH - AMS_HEADER_LENGTH:
        raise AdsError("payload too large")

    ams_header = struct.pack(
        "<6sH6sHHHIII",
        target_net_id,
        target_port & 0xFFFF,
        source_net_id,
        source_port & 0xFFFF,
        command_id & 0xFFFF,
        state_flags & 0xFFFF,
        len(payload),
        error_code & 0xFFFFFFFF,
        invoke_id & 0xFFFFFFFF,
    )
    ams = ams_header + payload
    tcp_header = struct.pack("<HI", 0, len(ams))
    return tcp_header + ams


def _response_header(request: dict[str, Any], payload: bytes) -> bytes:
    return pack_ams_tcp_frame(
        target_net_id=request["source_net_id"],
        target_port=request["source_port"],
        source_net_id=request["target_net_id"],
        source_port=request["target_port"],
        command_id=request["command_id"],
        state_flags=STATE_RESPONSE,
        invoke_id=request["invoke_id"],
        payload=payload,
        error_code=0,
    )


def _error_response(request: dict[str, Any], result: int) -> bytes:
    """Return a minimal ADS result payload for unknown/failed commands."""
    return _response_header(request, struct.pack("<I", result & 0xFFFFFFFF))


def _pad_device_name(name: str) -> bytes:
    raw = name.encode("ascii", errors="replace")[:DEVICE_NAME_LEN]
    return raw + b"\x00" * (DEVICE_NAME_LEN - len(raw))


def _find_symbol(
    symbols: list[dict[str, Any]], index_group: int, index_offset: int
) -> dict[str, Any] | None:
    for symbol in symbols:
        if (
            int(symbol["index_group"]) == index_group
            and int(symbol["index_offset"]) == index_offset
        ):
            return symbol
    return None


def handle_request(frame: bytes, device: dict[str, Any]) -> bytes:
    """Dispatch one AMS/TCP request and return the response frame."""
    request = unpack_ams_tcp_frame(frame)
    if request["state_flags"] & 0x1:
        raise AdsError("unexpected AMS response frame")

    command = request["command_id"]
    payload = request["payload"]
    symbols = device.get("symbols") or []

    if command == CMD_READ_DEVICE_INFO:
        body = struct.pack(
            "<IBBH",
            ADSERR_NOERR,
            int(device.get("version_major", 3)) & 0xFF,
            int(device.get("version_minor", 1)) & 0xFF,
            int(device.get("version_build", 0)) & 0xFFFF,
        )
        body += _pad_device_name(str(device.get("device_name", "Conpot TwinCAT")))
        return _response_header(request, body)

    if command == CMD_READ_STATE:
        body = struct.pack(
            "<IHH",
            ADSERR_NOERR,
            int(device.get("ads_state", 5)) & 0xFFFF,
            int(device.get("device_state", 0)) & 0xFFFF,
        )
        return _response_header(request, body)

    if command == CMD_READ:
        if len(payload) < 12:
            raise AdsError("READ request too short")
        index_group, index_offset, length = struct.unpack_from("<III", payload, 0)
        symbol = _find_symbol(symbols, index_group, index_offset)
        if symbol is None:
            return _error_response(request, ADSERR_DEVICE_SYMBOLNOTFOUND)
        data = bytes(symbol.get("value") or b"")
        if length > len(data):
            # Pad with zeros when client asks for more than we store.
            data = data + b"\x00" * (length - len(data))
        else:
            data = data[:length]
        body = struct.pack("<II", ADSERR_NOERR, len(data)) + data
        return _response_header(request, body)

    if command == CMD_WRITE:
        if len(payload) < 12:
            raise AdsError("WRITE request too short")
        index_group, index_offset, length = struct.unpack_from("<III", payload, 0)
        data = payload[12 : 12 + length]
        if len(data) != length:
            raise AdsError("WRITE data truncated")
        symbol = _find_symbol(symbols, index_group, index_offset)
        if symbol is None:
            return _error_response(request, ADSERR_DEVICE_SYMBOLNOTFOUND)
        symbol["value"] = bytearray(data)
        return _response_header(request, struct.pack("<I", ADSERR_NOERR))

    if command == CMD_WRITE_CONTROL:
        # Mock success regardless of requested state transition.
        return _response_header(request, struct.pack("<I", ADSERR_NOERR))

    return _error_response(request, ADSERR_DEVICE_INVALIDDATA)


def build_request(
    *,
    target_net_id: bytes,
    target_port: int,
    source_net_id: bytes,
    source_port: int,
    command_id: int,
    invoke_id: int,
    payload: bytes = b"",
) -> bytes:
    """Helper used by tests to craft AMS/TCP requests."""
    return pack_ams_tcp_frame(
        target_net_id=target_net_id,
        target_port=target_port,
        source_net_id=source_net_id,
        source_port=source_port,
        command_id=command_id,
        state_flags=STATE_ADS_COMMAND,
        invoke_id=invoke_id,
        payload=payload,
    )
