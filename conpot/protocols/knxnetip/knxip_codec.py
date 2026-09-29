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

"""Minimal KNXnet/IP framing for SEARCH and DESCRIPTION services."""

from __future__ import annotations

import socket
import struct

HEADER_SIZE = 6
HEADER_LENGTH = 0x06
PROTOCOL_VERSION = 0x10

SERVICE_SEARCH_REQUEST = 0x0201
SERVICE_SEARCH_RESPONSE = 0x0202
SERVICE_DESCRIPTION_REQUEST = 0x0203
SERVICE_DESCRIPTION_RESPONSE = 0x0204

SERVICE_NAMES = {
    SERVICE_SEARCH_REQUEST: "SEARCH_REQUEST",
    SERVICE_SEARCH_RESPONSE: "SEARCH_RESPONSE",
    SERVICE_DESCRIPTION_REQUEST: "DESCRIPTION_REQUEST",
    SERVICE_DESCRIPTION_RESPONSE: "DESCRIPTION_RESPONSE",
}

HPAI_LENGTH = 0x08
HPAI_IPV4_UDP = 0x01

DIB_DEVICE_INFO = 0x01
DIB_SUPP_SVC_FAMILIES = 0x02

# Service family identifiers (KNXnet/IP Core specification)
FAMILY_CORE = 0x02
FAMILY_DEVICE_MANAGEMENT = 0x03
FAMILY_TUNNELING = 0x04

KNX_MEDIUM_TP1 = 0x02
FRIENDLY_NAME_LEN = 30
DEFAULT_MULTICAST = "224.0.23.12"


class KnxipError(ValueError):
    """Invalid or unsupported KNXnet/IP datagram."""


def parse_individual_address(value: str) -> int:
    """Encode area.line.device into a 16-bit KNX individual address."""
    parts = str(value).strip().split(".")
    if len(parts) != 3:
        raise KnxipError(f"individual_address must be area.line.device, got {value!r}")
    area, line, device = (int(p) for p in parts)
    if not (0 <= area <= 15 and 0 <= line <= 15 and 0 <= device <= 255):
        raise KnxipError(f"individual_address out of range: {value!r}")
    return ((area & 0x0F) << 12) | ((line & 0x0F) << 8) | (device & 0xFF)


def format_individual_address(raw: int) -> str:
    area = (raw >> 12) & 0x0F
    line = (raw >> 8) & 0x0F
    device = raw & 0xFF
    return f"{area}.{line}.{device}"


def parse_hex_bytes(value: str, length: int) -> bytes:
    cleaned = str(value).replace(":", "").replace("-", "").replace(" ", "").strip()
    try:
        data = bytes.fromhex(cleaned)
    except ValueError as exc:
        raise KnxipError(f"invalid hex value: {value!r}") from exc
    if len(data) != length:
        raise KnxipError(f"expected {length} bytes, got {len(data)} from {value!r}")
    return data


def pack_header(service_type: int, total_length: int) -> bytes:
    return struct.pack(
        "!BBHH",
        HEADER_LENGTH,
        PROTOCOL_VERSION,
        service_type & 0xFFFF,
        total_length & 0xFFFF,
    )


def pack_hpai(ip: str, port: int) -> bytes:
    return struct.pack(
        "!BB4sH",
        HPAI_LENGTH,
        HPAI_IPV4_UDP,
        socket.inet_aton(ip),
        port & 0xFFFF,
    )


def unpack_header(data: bytes) -> dict:
    if len(data) < HEADER_SIZE:
        raise KnxipError("datagram shorter than KNXnet/IP header")
    header_len, version, service, total_length = struct.unpack(
        "!BBHH", data[:HEADER_SIZE]
    )
    if header_len != HEADER_LENGTH or version != PROTOCOL_VERSION:
        raise KnxipError("not a KNXnet/IP frame")
    if total_length < HEADER_SIZE or total_length > len(data):
        raise KnxipError("invalid total_length")
    return {
        "service_type": service,
        "service_name": SERVICE_NAMES.get(service, f"0x{service:04X}"),
        "total_length": total_length,
        "body": data[HEADER_SIZE:total_length],
    }


def pack_device_info_dib(
    *,
    medium: int,
    device_status: int,
    individual_address: int,
    project_installation_id: int,
    serial_number: bytes,
    multicast_ip: str,
    mac_address: bytes,
    friendly_name: str,
) -> bytes:
    name_bytes = friendly_name.encode("latin-1", errors="replace")[:FRIENDLY_NAME_LEN]
    name_bytes = name_bytes.ljust(FRIENDLY_NAME_LEN, b"\x00")
    # length(1) + type(1) + medium(1) + status(1) + IA(2) + project(2)
    # + serial(6) + multicast(4) + mac(6) + name(30) = 54
    return struct.pack(
        "!BBBBHH6s4s6s30s",
        54,
        DIB_DEVICE_INFO,
        medium & 0xFF,
        device_status & 0xFF,
        individual_address & 0xFFFF,
        project_installation_id & 0xFFFF,
        serial_number,
        socket.inet_aton(multicast_ip),
        mac_address,
        name_bytes,
    )


def pack_service_families_dib(
    families: list[tuple[int, int]] | None = None,
) -> bytes:
    if families is None:
        families = [
            (FAMILY_CORE, 1),
            (FAMILY_DEVICE_MANAGEMENT, 1),
            (FAMILY_TUNNELING, 1),
        ]
    pairs = b"".join(
        struct.pack("!BB", fid & 0xFF, ver & 0xFF) for fid, ver in families
    )
    structure = bytes([DIB_SUPP_SVC_FAMILIES]) + pairs
    return bytes([len(structure) + 1]) + structure


def build_device_dibs(identity: dict) -> bytes:
    return (
        pack_device_info_dib(
            medium=int(identity.get("medium", KNX_MEDIUM_TP1)),
            device_status=int(identity.get("device_status", 0)),
            individual_address=parse_individual_address(
                identity.get("individual_address", "1.1.1")
            ),
            project_installation_id=int(identity.get("project_installation_id", 0)),
            serial_number=parse_hex_bytes(
                identity.get("serial_number", "00fa00000001"), 6
            ),
            multicast_ip=str(identity.get("multicast_group", DEFAULT_MULTICAST)),
            mac_address=parse_hex_bytes(
                identity.get("mac_address", "00:fa:00:00:00:01"), 6
            ),
            friendly_name=str(identity.get("friendly_name", "Conpot KNX IP")),
        )
        + pack_service_families_dib()
    )


def build_search_response(control_ip: str, control_port: int, identity: dict) -> bytes:
    body = pack_hpai(control_ip, control_port) + build_device_dibs(identity)
    total = HEADER_SIZE + len(body)
    return pack_header(SERVICE_SEARCH_RESPONSE, total) + body


def build_description_response(identity: dict) -> bytes:
    body = build_device_dibs(identity)
    total = HEADER_SIZE + len(body)
    return pack_header(SERVICE_DESCRIPTION_RESPONSE, total) + body


def extract_friendly_name(frame: bytes) -> str | None:
    """Best-effort pull of Device Info friendly name from a response frame."""
    try:
        parsed = unpack_header(frame)
    except KnxipError:
        return None
    body = parsed["body"]
    # SEARCH_RESPONSE starts with HPAI (8 bytes); DESCRIPTION_RESPONSE is DIBs only.
    offset = HPAI_LENGTH if parsed["service_type"] == SERVICE_SEARCH_RESPONSE else 0
    if len(body) < offset + 2:
        return None
    dib_len = body[offset]
    dib_type = body[offset + 1]
    if dib_type != DIB_DEVICE_INFO or dib_len < 54:
        return None
    name = body[offset + 24 : offset + 54]
    return name.split(b"\x00", 1)[0].decode("latin-1", errors="replace")


def extract_individual_address(frame: bytes) -> str | None:
    try:
        parsed = unpack_header(frame)
    except KnxipError:
        return None
    body = parsed["body"]
    offset = HPAI_LENGTH if parsed["service_type"] == SERVICE_SEARCH_RESPONSE else 0
    if len(body) < offset + 8:
        return None
    if body[offset + 1] != DIB_DEVICE_INFO:
        return None
    raw = struct.unpack_from("!H", body, offset + 4)[0]
    return format_individual_address(raw)
