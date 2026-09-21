# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""Minimal MMS (ISO 9506) encode/decode for an ICCP/TASE.2 honeypot subset."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from conpot.protocols.iccp.ber import (
    decode_tlv,
    encode_bitstring,
    encode_boolean,
    encode_integer,
    encode_null,
    encode_sequence,
    encode_tag_length_value,
    encode_visible_string,
)

# MMSpdu CHOICE tags
TAG_CONFIRMED_REQUEST = 0xA0
TAG_CONFIRMED_RESPONSE = 0xA1
TAG_INITIATE_REQUEST = 0xA8
TAG_INITIATE_RESPONSE = 0xA9
TAG_CONCLUDE_REQUEST = 0x8B
TAG_CONCLUDE_RESPONSE = 0x8C

# ConfirmedServiceRequest / Response
SVC_GET_NAME_LIST = 1
SVC_IDENTIFY = 2
SVC_READ = 4


@dataclass
class ConfirmedRequest:
    invoke_id: int
    service: int
    body: bytes


@dataclass
class PointValue:
    name: str
    kind: str  # "boolean" | "integer" | "float"
    value: Any


def build_initiate_response() -> bytes:
    """MMS Initiate-ResponsePDU (context tag 9)."""
    detail = encode_sequence(
        0xA4,
        encode_integer(0x80, 1),
        encode_bitstring(0x81, 5, bytes.fromhex("fb00")),
        encode_bitstring(0x82, 0, bytes.fromhex("03ee1c00000000000000ed18")),
    )
    return encode_sequence(
        TAG_INITIATE_RESPONSE,
        encode_integer(0x80, 32000),
        encode_integer(0x81, 10),
        encode_integer(0x82, 10),
        encode_integer(0x83, 5),
        detail,
    )


def build_identify_response(
    invoke_id: int, vendor: str, model: str, revision: str
) -> bytes:
    identify = encode_sequence(
        0xA2,
        encode_visible_string(0x80, vendor),
        encode_visible_string(0x81, model),
        encode_visible_string(0x82, revision),
    )
    return encode_sequence(
        TAG_CONFIRMED_RESPONSE,
        encode_integer(0x02, invoke_id),
        identify,
    )


def build_get_name_list_response(invoke_id: int, names: list[str]) -> bytes:
    identifiers = b"".join(encode_visible_string(0x1A, name) for name in names)
    service = encode_sequence(
        0xA1,
        encode_tag_length_value(0xA0, identifiers),
        encode_boolean(0x81, False),
    )
    return encode_sequence(
        TAG_CONFIRMED_RESPONSE,
        encode_integer(0x02, invoke_id),
        service,
    )


def _encode_data(point: PointValue) -> bytes:
    if point.kind == "boolean":
        return encode_boolean(0x83, bool(point.value))
    if point.kind == "integer":
        return encode_integer(0x85, int(point.value))
    if point.kind == "float":
        # MMS floating-point: exponent-width octet + IEEE float octets.
        import struct

        return encode_tag_length_value(
            0x87, b"\x08" + struct.pack("!f", float(point.value))
        )
    return encode_visible_string(0x8A, str(point.value))


def build_read_response(invoke_id: int, points: list[PointValue | None]) -> bytes:
    results = []
    for point in points:
        if point is None:
            results.append(encode_integer(0x80, 10))  # object-non-existent
        else:
            # AccessResult success is the Data CHOICE itself (untagged in CHOICE).
            results.append(_encode_data(point))
    service = encode_sequence(
        0xA4,
        encode_tag_length_value(0xA1, b"".join(results)),
    )
    return encode_sequence(
        TAG_CONFIRMED_RESPONSE,
        encode_integer(0x02, invoke_id),
        service,
    )


def build_conclude_response() -> bytes:
    return encode_null(TAG_CONCLUDE_RESPONSE)


def build_confirmed_error(
    invoke_id: int, error_class: int = 1, error_code: int = 1
) -> bytes:
    # confirmed-ErrorPDU [2] — keep minimal for unknown services.
    body = encode_sequence(
        0xA2,
        encode_integer(0x02, invoke_id),
        encode_sequence(
            0xA0,
            encode_integer(0x80, error_class),
            encode_integer(0x81, error_code),
        ),
    )
    return body


def parse_mms_pdu(data: bytes) -> tuple[str, Any]:
    """Classify an MMS PDU. Returns (kind, payload)."""
    if not data:
        raise ValueError("empty MMS PDU")
    tag = data[0]
    if tag == TAG_INITIATE_REQUEST:
        return "initiate_request", data
    if tag == TAG_CONCLUDE_REQUEST:
        return "conclude_request", data
    if tag == TAG_CONFIRMED_REQUEST:
        return "confirmed_request", parse_confirmed_request(data)
    return "unknown", data


def parse_confirmed_request(data: bytes) -> ConfirmedRequest:
    tag, body, _ = decode_tlv(data, 0)
    if tag != TAG_CONFIRMED_REQUEST:
        raise ValueError("not a confirmed-RequestPDU")
    offset = 0
    invoke_id = 1
    service = -1
    service_body = b""
    while offset < len(body):
        t, v, offset = decode_tlv(body, offset)
        if t == 0x02:
            invoke_id = int.from_bytes(v, "big") if v else 0
        elif (t & 0xE0) == 0x80 or (t & 0xE0) == 0xA0:
            # Context-specific service tag (primitive or constructed).
            service = t & 0x1F
            service_body = v
            break
    return ConfirmedRequest(invoke_id=invoke_id, service=service, body=service_body)


def parse_get_name_list_scope(body: bytes) -> tuple[str, str | None]:
    """Return (scope_kind, domain_id_or_None)."""
    offset = 0
    scope_kind = "vmd"
    domain_id = None
    while offset < len(body):
        tag, value, offset = decode_tlv(body, offset)
        if (tag & 0x1F) == 1:
            # objectScope CHOICE
            if not value:
                continue
            inner_tag = value[0]
            if (inner_tag & 0x1F) == 0:
                scope_kind = "vmd"
            elif (inner_tag & 0x1F) == 1:
                scope_kind = "domain"
                _, domain_bytes, _ = decode_tlv(value, 0)
                domain_id = domain_bytes.decode("ascii", errors="replace")
            elif (inner_tag & 0x1F) == 2:
                scope_kind = "aa"
    return scope_kind, domain_id


def parse_read_variable_names(body: bytes) -> list[tuple[str | None, str]]:
    """Extract (domain_or_None, item) pairs from a Read-Request body."""
    names: list[tuple[str | None, str]] = []
    offset = 0
    while offset < len(body):
        tag, value, offset = decode_tlv(body, offset)
        if (tag & 0x1F) != 1:
            continue
        # variableAccessSpecification
        if not value:
            continue
        vas_tag, vas_val, _ = decode_tlv(value, 0)
        if (vas_tag & 0x1F) == 0:
            # listOfVariable
            inner = 0
            while inner < len(vas_val):
                _, var_spec, inner = decode_tlv(vas_val, inner)
                # SEQUENCE { variableSpecification, alternateAccess OPTIONAL }
                vs_off = 0
                if not var_spec:
                    continue
                # Often: variableSpecification CHOICE name [0]
                t0 = var_spec[0]
                if (t0 & 0x1F) == 0 or t0 in (0xA0, 0x80):
                    # name CHOICE
                    _, name_body, _ = decode_tlv(var_spec, 0)
                    names.append(
                        _parse_object_name(name_body if name_body else var_spec)
                    )
                else:
                    names.append(_parse_object_name(var_spec))
        elif (vas_tag & 0x1F) == 1:
            names.append(_parse_object_name(vas_val))
    return names


def _parse_object_name(data: bytes) -> tuple[str | None, str]:
    """Parse ObjectName CHOICE content (possibly including outer tag)."""
    if not data:
        return None, ""
    # If already a TLV for domain-specific / vmd-specific:
    tag = data[0]
    if (tag & 0xE0) in (0x80, 0xA0) or tag in (0x80, 0xA0, 0xA1, 0x81):
        t, value, _ = decode_tlv(data, 0)
        num = t & 0x1F
        if num == 0:
            return None, value.decode("ascii", errors="replace")
        if num == 1:
            # SEQUENCE { domainId, itemId }
            off = 0
            domain = ""
            item = ""
            while off < len(value):
                it, iv, off = decode_tlv(value, off)
                text = iv.decode("ascii", errors="replace")
                if not domain:
                    domain = text
                else:
                    item = text
            return domain or None, item
        if num == 2:
            return None, value.decode("ascii", errors="replace")
    # Bare VisibleString
    if tag == 0x1A:
        _, value, _ = decode_tlv(data, 0)
        return None, value.decode("ascii", errors="replace")
    return None, data.decode("ascii", errors="replace")


def extract_mms_from_presentation(user_data: bytes) -> bytes | None:
    """Pull the MMS PDU out of Session/Presentation user data when possible."""
    # Prefer initiate / conclude tags — they are unambiguous MMS CHOICE values.
    for wanted in (
        TAG_INITIATE_RESPONSE,
        TAG_INITIATE_REQUEST,
        TAG_CONCLUDE_REQUEST,
        TAG_CONCLUDE_RESPONSE,
    ):
        for i, byte in enumerate(user_data):
            if byte != wanted:
                continue
            try:
                _, _, end = decode_tlv(user_data, i)
                return user_data[i:end]
            except ValueError:
                continue

    # Confirmed request/response/error: body starts with invokeID INTEGER (0x02).
    for i, byte in enumerate(user_data):
        if byte not in (
            TAG_CONFIRMED_REQUEST,
            TAG_CONFIRMED_RESPONSE,
            0xA2,
        ):
            continue
        try:
            _, value, end = decode_tlv(user_data, i)
            if value and value[0] == 0x02:
                return user_data[i:end]
        except ValueError:
            continue
    return None
