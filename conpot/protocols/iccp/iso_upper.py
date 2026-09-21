# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""ISO Session / Presentation / ACSE stubs wrapping MMS PDUs."""

from __future__ import annotations

from conpot.protocols.iccp.ber import (
    encode_integer,
    encode_sequence,
    encode_tag_length_value,
)
from conpot.protocols.iccp.mms import (
    build_initiate_response,
    extract_mms_from_presentation,
)

SESSION_CONNECT = 0x0D
SESSION_ACCEPT = 0x0E
SESSION_DATA_GT = 0x01  # Give Tokens
SESSION_DATA_DT = 0x01  # Data Transfer (same SI; distinguished by position)


def is_session_connect(payload: bytes) -> bool:
    return bool(payload) and payload[0] == SESSION_CONNECT


def is_session_data(payload: bytes) -> bool:
    # After association: Give Tokens (01 00) + DT (01 00) + presentation
    return len(payload) >= 4 and payload[0] == 0x01 and payload[2] == 0x01


def wrap_session_data(presentation_user: bytes) -> bytes:
    """Session Give-Tokens + Data-Transfer carrying presentation user data."""
    return b"\x01\x00\x01\x00" + presentation_user


def wrap_presentation_user(mms_pdu: bytes, context_id: int = 3) -> bytes:
    """ISO 8823 fully-encoded-data user-data (APPLICATION 1)."""
    # fully-encoded-data: SEQUENCE OF { context, single-ASN1-type }
    single = encode_tag_length_value(0xA0, mms_pdu)
    pdv = encode_sequence(0x30, encode_integer(0x02, context_id), single)
    return encode_tag_length_value(0x61, pdv)


def _session_param(pi: int, value: bytes) -> bytes:
    """ISO 8327 parameter encoding (not ASN.1 BER length)."""
    if len(value) < 0xFF:
        return bytes([pi, len(value)]) + value
    return bytes([pi, 0xFF, (len(value) >> 8) & 0xFF, len(value) & 0xFF]) + value


def build_initiate_accept() -> bytes:
    """Session ACCEPT + Presentation CPA + ACSE AARE + MMS Initiate-Response."""
    mms = build_initiate_response()

    # ACSE AARE (APPLICATION 1) with user-information carrying MMS.
    # Structure mirrors common IEC 61850 / TASE.2 called-endpoint replies.
    user_info_inner = encode_sequence(
        0x28,  # external
        encode_sequence(
            0x30,
            encode_tag_length_value(0x06, bytes.fromhex("5101")),
            encode_integer(0x02, 3),
            encode_tag_length_value(0xA0, mms),
        ),
    )
    aare = encode_sequence(
        0x61,  # AARE APDU
        encode_tag_length_value(0x80, bytes.fromhex("0780")),
        encode_sequence(
            0xA1,
            encode_tag_length_value(0x06, bytes.fromhex("28ca220101")),
        ),
        encode_sequence(0xA2, encode_integer(0x02, 0)),
        encode_sequence(
            0xA3,
            encode_sequence(0xA1, encode_integer(0x02, 0)),
        ),
        encode_tag_length_value(0xBE, user_info_inner),
    )

    cpa_user = encode_sequence(
        0x30, encode_integer(0x02, 1), encode_tag_length_value(0xA0, aare)
    )
    cpa_user = encode_tag_length_value(0x61, cpa_user)

    cpa_body = (
        encode_tag_length_value(0xA0, encode_tag_length_value(0x80, b"\x01"))
        + encode_sequence(
            0xA2,
            encode_tag_length_value(0x80, bytes.fromhex("0780")),
            encode_integer(0x81, 1),
            encode_integer(0x82, 2),
            encode_sequence(
                0xA4,
                encode_sequence(
                    0x30,
                    encode_integer(0x02, 1),
                    encode_tag_length_value(0x06, bytes.fromhex("52010001")),
                    encode_sequence(
                        0x30, encode_tag_length_value(0x06, bytes.fromhex("5101"))
                    ),
                ),
                encode_sequence(
                    0x30,
                    encode_integer(0x02, 3),
                    encode_tag_length_value(0x06, bytes.fromhex("28ca220201")),
                    encode_sequence(
                        0x30, encode_tag_length_value(0x06, bytes.fromhex("5101"))
                    ),
                ),
            ),
        )
        + cpa_user
    )
    presentation = encode_tag_length_value(0x31, cpa_body)

    session_params = bytes.fromhex("05061301001601021402000234020002")
    session_body = session_params + _session_param(0xC1, presentation)
    if len(session_body) < 0xFF:
        length = bytes([len(session_body)])
    else:
        length = bytes(
            [0xFF, (len(session_body) >> 8) & 0xFF, len(session_body) & 0xFF]
        )
    return bytes([SESSION_ACCEPT]) + length + session_body


def extract_mms_pdu(session_payload: bytes) -> bytes | None:
    """Extract MMS from Session CONNECT user-data or Session Data Transfer."""
    if is_session_connect(session_payload):
        if len(session_payload) < 2:
            return None
        li = session_payload[1]
        if li == 0xFF:
            if len(session_payload) < 4:
                return None
            length = (session_payload[2] << 8) | session_payload[3]
            body = session_payload[4 : 4 + length]
        else:
            body = session_payload[2 : 2 + li]
        offset = 0
        while offset + 2 <= len(body):
            pi = body[offset]
            pli = body[offset + 1]
            if pli == 0xFF:
                if offset + 4 > len(body):
                    break
                plen = (body[offset + 2] << 8) | body[offset + 3]
                value_start = offset + 4
            else:
                plen = pli
                value_start = offset + 2
            if value_start + plen > len(body):
                break
            value = body[value_start : value_start + plen]
            if pi == 0xC1:
                return extract_mms_from_presentation(value)
            offset = value_start + plen
        return extract_mms_from_presentation(body)

    if is_session_data(session_payload):
        return extract_mms_from_presentation(session_payload[4:])

    return extract_mms_from_presentation(session_payload)
