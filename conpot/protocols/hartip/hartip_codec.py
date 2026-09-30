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

"""Minimal HART-IP v1 framing for session setup and common scanner commands."""

from __future__ import annotations

import struct
from typing import Any

HEADER_LENGTH = 8
HARTIP_VERSION = 1

MSG_TYPE_REQUEST = 0
MSG_TYPE_RESPONSE = 1

MSG_ID_SESSION_INITIATE = 0
MSG_ID_SESSION_CLOSE = 1
MSG_ID_KEEP_ALIVE = 2
MSG_ID_PASS_THROUGH = 3

MSG_ID_NAMES = {
    MSG_ID_SESSION_INITIATE: "SESSION_INITIATE",
    MSG_ID_SESSION_CLOSE: "SESSION_CLOSE",
    MSG_ID_KEEP_ALIVE: "KEEP_ALIVE",
    MSG_ID_PASS_THROUGH: "PASS_THROUGH",
}

# Token-passing delimiters (frame type in low 3 bits; address type in bit 7).
DELIM_STX_SHORT = 0x02
DELIM_ACK_SHORT = 0x06
DELIM_STX_LONG = 0x82
DELIM_ACK_LONG = 0x86

CMD_READ_UNIQUE_ID = 0
CMD_READ_LONG_TAG = 20
CMD_READ_SUBDEVICE_SUMMARY = 84

LONG_TAG_LEN = 32
CMD0_DATA_LEN = 22

# HART response code: Invalid selection / no sub-device (nmap hartip-info).
HART_RC_INVALID_SELECTION = 2


class HartipError(ValueError):
    """Invalid or unsupported HART-IP PDU."""


def xor_checksum(data: bytes) -> int:
    check = 0
    for byte in data:
        check ^= byte
    return check & 0xFF


def pack_header(
    version: int,
    message_type: int,
    message_id: int,
    status: int,
    transaction_id: int,
    length: int,
) -> bytes:
    return struct.pack(
        "!BBBBHH",
        version & 0xFF,
        message_type & 0xFF,
        message_id & 0xFF,
        status & 0xFF,
        transaction_id & 0xFFFF,
        length & 0xFFFF,
    )


def unpack_header(data: bytes) -> dict[str, Any]:
    if len(data) < HEADER_LENGTH:
        raise HartipError(f"PDU shorter than header ({len(data)} bytes)")
    version, message_type, message_id, status, transaction_id, length = struct.unpack(
        "!BBBBHH", data[:HEADER_LENGTH]
    )
    if length < HEADER_LENGTH:
        raise HartipError(f"invalid HART-IP length {length}")
    if len(data) < length:
        raise HartipError(f"truncated PDU: have {len(data)}, declared {length}")
    return {
        "version": version,
        "message_type": message_type,
        "message_id": message_id,
        "message_name": MSG_ID_NAMES.get(message_id, f"UNKNOWN_{message_id}"),
        "status": status,
        "transaction_id": transaction_id,
        "length": length,
        "payload": data[HEADER_LENGTH:length],
        "raw": data[:length],
    }


def build_pdu(
    message_id: int,
    transaction_id: int,
    payload: bytes = b"",
    *,
    version: int = HARTIP_VERSION,
    message_type: int = MSG_TYPE_RESPONSE,
    status: int = 0,
) -> bytes:
    length = HEADER_LENGTH + len(payload)
    return (
        pack_header(version, message_type, message_id, status, transaction_id, length)
        + payload
    )


def build_session_initiate_response(
    transaction_id: int, payload: bytes, *, version: int = HARTIP_VERSION
) -> bytes:
    """Echo session payload (master type + inactivity close time)."""
    if len(payload) < 5:
        # Sensible default: primary master, 20s inactivity (nmap probe value).
        payload = b"\x01\x00\x00\x4e\x20"
    else:
        payload = payload[:5]
    return build_pdu(
        MSG_ID_SESSION_INITIATE,
        transaction_id,
        payload,
        version=version,
        message_type=MSG_TYPE_RESPONSE,
    )


def build_session_close_response(
    transaction_id: int, *, version: int = HARTIP_VERSION
) -> bytes:
    return build_pdu(
        MSG_ID_SESSION_CLOSE,
        transaction_id,
        b"",
        version=version,
        message_type=MSG_TYPE_RESPONSE,
    )


def build_keep_alive_response(
    transaction_id: int, *, version: int = HARTIP_VERSION
) -> bytes:
    return build_pdu(
        MSG_ID_KEEP_ALIVE,
        transaction_id,
        b"",
        version=version,
        message_type=MSG_TYPE_RESPONSE,
    )


def is_long_address(delimiter: int) -> bool:
    return bool(delimiter & 0x80)


def address_length(delimiter: int) -> int:
    return 5 if is_long_address(delimiter) else 1


def parse_token_passing(frame: bytes) -> dict[str, Any]:
    if not frame:
        raise HartipError("empty pass-through payload")
    delimiter = frame[0]
    addr_len = address_length(delimiter)
    # delim + address + command + byte_count + checksum
    min_len = 1 + addr_len + 1 + 1 + 1
    if len(frame) < min_len:
        raise HartipError(f"short token-passing frame ({len(frame)} bytes)")
    address = frame[1 : 1 + addr_len]
    command = frame[1 + addr_len]
    byte_count = frame[2 + addr_len]
    data_start = 3 + addr_len
    data_end = data_start + byte_count
    if len(frame) < data_end + 1:
        raise HartipError("truncated token-passing data")
    data = frame[data_start:data_end]
    checksum = frame[data_end]
    expected = xor_checksum(frame[:data_end])
    if checksum != expected:
        raise HartipError(
            f"checksum mismatch: got 0x{checksum:02x}, expected 0x{expected:02x}"
        )
    return {
        "delimiter": delimiter,
        "address": address,
        "command": command,
        "byte_count": byte_count,
        "data": data,
        "checksum": checksum,
        "long_address": is_long_address(delimiter),
    }


def pack_token_passing_response(
    request: dict[str, Any],
    response_code: int,
    device_status: int,
    data: bytes,
) -> bytes:
    """Build ACK token-passing frame mirroring request address form."""
    if request["long_address"]:
        delimiter = DELIM_ACK_LONG
    else:
        delimiter = DELIM_ACK_SHORT
    address = request["address"]
    body_without_check = (
        bytes([delimiter])
        + address
        + bytes(
            [
                request["command"],
                2 + len(data),
                response_code & 0xFF,
                device_status & 0xFF,
            ]
        )
        + data
    )
    return body_without_check + bytes([xor_checksum(body_without_check)])


def parse_device_id(value: str | int) -> bytes:
    if isinstance(value, int):
        if not (0 <= value <= 0xFFFFFF):
            raise HartipError(f"device_id out of range: {value}")
        return value.to_bytes(3, "big")
    cleaned = str(value).replace(":", "").replace("-", "").replace(" ", "").strip()
    try:
        data = bytes.fromhex(cleaned)
    except ValueError as exc:
        raise HartipError(f"invalid device_id hex: {value!r}") from exc
    if len(data) != 3:
        raise HartipError(f"device_id must be 3 bytes, got {len(data)} from {value!r}")
    return data


def format_long_tag(value: str) -> bytes:
    raw = str(value).encode("latin-1", errors="replace")[:LONG_TAG_LEN]
    return raw.ljust(LONG_TAG_LEN, b"\x00")


def build_cmd0_data(identity: dict[str, Any]) -> bytes:
    device_id = parse_device_id(identity.get("device_id", "000001"))
    expanded = int(identity.get("expanded_device_type", 45075)) & 0xFFFF
    manufacturer = int(identity.get("manufacturer_id", 176)) & 0xFFFF
    private_label = (
        int(identity.get("private_label_distributor", manufacturer)) & 0xFFFF
    )
    return struct.pack(
        "!BHBBBBBB3sBBHBHHB",
        0xFE,
        expanded,
        int(identity.get("min_preambles", 5)) & 0xFF,
        int(identity.get("hart_revision", 7)) & 0xFF,
        int(identity.get("device_revision", 1)) & 0xFF,
        int(identity.get("software_revision", 1)) & 0xFF,
        int(identity.get("hardware_revision", 1)) & 0xFF,
        int(identity.get("flags", 0)) & 0xFF,
        device_id,
        int(identity.get("min_preambles_slave", 5)) & 0xFF,
        int(identity.get("max_device_variables", 1)) & 0xFF,
        int(identity.get("config_change_counter", 0)) & 0xFFFF,
        int(identity.get("extended_device_status", 0)) & 0xFF,
        manufacturer,
        private_label,
        int(identity.get("device_profile", 1)) & 0xFF,
    )


def build_pass_through_response(
    transaction_id: int,
    request_frame: dict[str, Any],
    identity: dict[str, Any],
    *,
    version: int = HARTIP_VERSION,
) -> bytes:
    command = request_frame["command"]
    if command == CMD_READ_UNIQUE_ID:
        data = build_cmd0_data(identity)
        tp = pack_token_passing_response(request_frame, 0, 0, data)
    elif command == CMD_READ_LONG_TAG:
        data = format_long_tag(identity.get("long_tag", "Conpot HART-IP Gateway"))
        tp = pack_token_passing_response(request_frame, 0, 0, data)
    elif command == CMD_READ_SUBDEVICE_SUMMARY:
        # No sub-device — response code 2, empty data (nmap hartip-info path).
        tp = pack_token_passing_response(
            request_frame, HART_RC_INVALID_SELECTION, 0, b""
        )
    else:
        # Command not implemented.
        tp = pack_token_passing_response(
            request_frame, HART_RC_INVALID_SELECTION, 0, b""
        )

    return build_pdu(
        MSG_ID_PASS_THROUGH,
        transaction_id,
        tp,
        version=version,
        message_type=MSG_TYPE_RESPONSE,
    )


def handle_request(pdu: bytes, identity: dict[str, Any]) -> bytes | None:
    """Return a response PDU for a complete HART-IP request, or None to ignore."""
    parsed = unpack_header(pdu)
    if parsed["message_type"] != MSG_TYPE_REQUEST:
        return None

    version = parsed["version"] or HARTIP_VERSION
    txn = parsed["transaction_id"]
    msg_id = parsed["message_id"]

    if msg_id == MSG_ID_SESSION_INITIATE:
        return build_session_initiate_response(txn, parsed["payload"], version=version)
    if msg_id == MSG_ID_SESSION_CLOSE:
        return build_session_close_response(txn, version=version)
    if msg_id == MSG_ID_KEEP_ALIVE:
        return build_keep_alive_response(txn, version=version)
    if msg_id == MSG_ID_PASS_THROUGH:
        frame = parse_token_passing(parsed["payload"])
        return build_pass_through_response(txn, frame, identity, version=version)
    return None
