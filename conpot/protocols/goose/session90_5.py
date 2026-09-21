# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""Unsecured IEC 61850-90-5 session framing for Routed-GOOSE (R-GOOSE)."""

from __future__ import annotations

import struct
import time
from typing import Any

# Session / payload identifiers from IEC 61850-90-5.
SI_R_GOOSE = 0xA1
PI_COMMON_HEADER = 0x80
PAYLOAD_TYPE_GOOSE = 0x81

# Unsecured profile: encryption none, HMAC none.
SECURITY_ALG_NONE = 0x00

MAX_DATAGRAM = 65507
# Fixed common-header PV size for the unsecured profile we emit/accept.
# SPDU length(4) + number(4) + version(2) + key time(4) + next key(2)
# + enc(1) + hmac(1) + key id(4) = 22
_UNSECURED_HEADER_PV_LEN = 22


class Session90_5Error(ValueError):
    """Malformed or unsupported 90-5 session datagram."""


def _encode_li(length: int) -> bytes:
    if length < 0:
        raise Session90_5Error("negative LI")
    if length < 128:
        return bytes([length])
    if length <= 255:
        return bytes([0x81, length])
    if length <= 65535:
        return bytes([0x82]) + struct.pack("!H", length)
    raise Session90_5Error("LI too large")


def _decode_li(data: bytes, offset: int) -> tuple[int, int]:
    if offset >= len(data):
        raise Session90_5Error("truncated LI")
    first = data[offset]
    if first < 128:
        return first, offset + 1
    nbytes = first & 0x7F
    if nbytes == 0 or nbytes > 2:
        raise Session90_5Error("unsupported LI form")
    start = offset + 1
    end = start + nbytes
    if end > len(data):
        raise Session90_5Error("truncated LI value")
    length = int.from_bytes(data[start:end], "big")
    return length, end


def pack_rgoose(
    goose_apdu: bytes,
    *,
    appid: int,
    spdu_number: int = 1,
    simulation: bool = False,
    time_of_current_key: int | None = None,
    time_to_next_key: int = 0,
    key_id: int = 0,
) -> bytes:
    """Build an unsecured R-GOOSE UDP payload wrapping ``goose_apdu``."""
    if not goose_apdu:
        raise Session90_5Error("empty GOOSE APDU")
    if len(goose_apdu) > 0xFFFF:
        raise Session90_5Error("GOOSE APDU too large")
    appid = int(appid) & 0xFFFF
    if time_of_current_key is None:
        time_of_current_key = int(time.time()) & 0xFFFFFFFF

    # User data: type, simulation, APPID, APDU length, APDU (no signature).
    user_data = (
        bytes([PAYLOAD_TYPE_GOOSE, 0x01 if simulation else 0x00])
        + struct.pack("!HH", appid, len(goose_apdu))
        + goose_apdu
    )

    # SPDU length covers SPDU number through end of user data (no signature).
    # Fields after SPDU length: number(4)+version(2)+times(6)+algs(2)+key(4)+user
    spdu_length = 4 + 2 + 4 + 2 + 1 + 1 + 4 + len(user_data)
    header_pv = (
        struct.pack("!I", spdu_length)
        + struct.pack("!I", int(spdu_number) & 0xFFFFFFFF)
        + struct.pack("!H", 1)  # version
        + struct.pack("!I", int(time_of_current_key) & 0xFFFFFFFF)
        + struct.pack("!h", int(time_to_next_key))
        + bytes([SECURITY_ALG_NONE, SECURITY_ALG_NONE])
        + struct.pack("!I", int(key_id) & 0xFFFFFFFF)
    )
    assert len(header_pv) == _UNSECURED_HEADER_PV_LEN

    common = bytes([PI_COMMON_HEADER]) + _encode_li(len(header_pv)) + header_pv
    # SI LI covers the common-header TLV (not user data).
    packet = bytes([SI_R_GOOSE]) + _encode_li(len(common)) + common + user_data
    if len(packet) > MAX_DATAGRAM:
        raise Session90_5Error("R-GOOSE datagram too large")
    return packet


def unpack_rgoose(data: bytes) -> dict[str, Any]:
    """Parse an unsecured R-GOOSE UDP payload.

    Returns session fields plus ``goose_apdu`` bytes. Raises Session90_5Error
    on non-R-GOOSE or malformed frames.
    """
    if not data:
        raise Session90_5Error("empty datagram")
    if len(data) > MAX_DATAGRAM:
        raise Session90_5Error("datagram too large")
    if data[0] != SI_R_GOOSE:
        raise Session90_5Error("not an R-GOOSE session (SI != 0xA1)")

    header_len, pos = _decode_li(data, 1)
    header_end = pos + header_len
    if header_end > len(data):
        raise Session90_5Error("truncated session header")
    header = data[pos:header_end]
    user_data = data[header_end:]

    if not header or header[0] != PI_COMMON_HEADER:
        raise Session90_5Error("missing common session header")
    pv_len, pv_pos = _decode_li(header, 1)
    pv_end = pv_pos + pv_len
    if pv_end > len(header):
        raise Session90_5Error("truncated common header PV")
    if pv_end != len(header):
        raise Session90_5Error("unexpected bytes after common header PV")
    pv = header[pv_pos:pv_end]
    if len(pv) < _UNSECURED_HEADER_PV_LEN:
        raise Session90_5Error("common header PV too short")

    spdu_length = struct.unpack_from("!I", pv, 0)[0]
    spdu_number = struct.unpack_from("!I", pv, 4)[0]
    version = struct.unpack_from("!H", pv, 8)[0]
    time_of_current_key = struct.unpack_from("!I", pv, 10)[0]
    time_to_next_key = struct.unpack_from("!h", pv, 14)[0]
    enc_alg = pv[16]
    hmac_alg = pv[17]
    key_id = struct.unpack_from("!I", pv, 18)[0]
    # Remaining PV bytes (if any) are ignored for forward compatibility,
    # but our encoder emits exactly 22 bytes.
    if len(pv) > _UNSECURED_HEADER_PV_LEN:
        # Reject unexpected extensions in the honeypot parser for safety.
        raise Session90_5Error("unsupported common header extensions")

    expected_spdu = (len(pv) - 4) + len(user_data)
    if spdu_length != expected_spdu:
        # Allow signature-less frames that match number..end-of-user-data.
        if spdu_length != 4 + 2 + 4 + 2 + 1 + 1 + 4 + len(user_data):
            raise Session90_5Error("SPDU length mismatch")

    if len(user_data) < 6:
        raise Session90_5Error("truncated user data")
    payload_type = user_data[0]
    if payload_type != PAYLOAD_TYPE_GOOSE:
        raise Session90_5Error(f"unsupported payload type 0x{payload_type:02x}")
    simulation = bool(user_data[1])
    appid, apdu_len = struct.unpack_from("!HH", user_data, 2)
    apdu_start = 6
    apdu_end = apdu_start + apdu_len
    if apdu_end > len(user_data):
        raise Session90_5Error("truncated GOOSE APDU")
    goose_apdu = user_data[apdu_start:apdu_end]
    # Optional trailing signature is ignored (unsecured / honeypot subset).

    return {
        "spdu_number": spdu_number,
        "version": version,
        "time_of_current_key": time_of_current_key,
        "time_to_next_key": time_to_next_key,
        "encryption_algorithm": enc_alg,
        "hmac_algorithm": hmac_alg,
        "key_id": key_id,
        "simulation": simulation,
        "appid": appid,
        "goose_apdu": goose_apdu,
    }
