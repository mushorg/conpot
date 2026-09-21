# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""Minimal ASN.1 BER helpers for MMS/ICCP honeypot PDUs."""

from __future__ import annotations


def encode_length(length: int) -> bytes:
    if length < 0x80:
        return bytes([length])
    if length < 0x100:
        return bytes([0x81, length])
    if length < 0x10000:
        return bytes([0x82, (length >> 8) & 0xFF, length & 0xFF])
    raise ValueError(f"length too large for honeypot BER encoder: {length}")


def encode_tag_length_value(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + encode_length(len(value)) + value


def encode_integer(tag: int, value: int) -> bytes:
    if value == 0:
        body = b"\x00"
    elif value > 0:
        length = max(1, (value.bit_length() + 7) // 8)
        body = value.to_bytes(length, "big")
        if body[0] & 0x80:
            body = b"\x00" + body
    else:
        # Two's complement for negatives (unused by our responses).
        length = max(1, ((-value).bit_length() + 8) // 8)
        body = value.to_bytes(length, "big", signed=True)
    return encode_tag_length_value(tag, body)


def encode_boolean(tag: int, value: bool) -> bytes:
    return encode_tag_length_value(tag, b"\xff" if value else b"\x00")


def encode_visible_string(tag: int, text: str) -> bytes:
    return encode_tag_length_value(tag, text.encode("ascii", errors="replace"))


def encode_bitstring(tag: int, unused_bits: int, data: bytes) -> bytes:
    return encode_tag_length_value(tag, bytes([unused_bits]) + data)


def encode_null(tag: int) -> bytes:
    return encode_tag_length_value(tag, b"")


def encode_sequence(tag: int, *parts: bytes) -> bytes:
    return encode_tag_length_value(tag, b"".join(parts))


def decode_length(data: bytes, offset: int = 0) -> tuple[int, int]:
    """Return (length, new_offset)."""
    if offset >= len(data):
        raise ValueError("truncated BER length")
    first = data[offset]
    offset += 1
    if first < 0x80:
        return first, offset
    n = first & 0x7F
    if n == 0 or offset + n > len(data):
        raise ValueError("invalid BER length")
    length = int.from_bytes(data[offset : offset + n], "big")
    return length, offset + n


def decode_tlv(data: bytes, offset: int = 0) -> tuple[int, bytes, int]:
    """Return (tag, value, new_offset)."""
    if offset >= len(data):
        raise ValueError("truncated BER TLV")
    tag = data[offset]
    length, offset = decode_length(data, offset + 1)
    end = offset + length
    if end > len(data):
        raise ValueError("truncated BER value")
    return tag, data[offset:end], end


def find_context_tag(data: bytes, wanted: int) -> bytes | None:
    """Scan a BER SEQUENCE body for an IMPLICIT context tag ``wanted`` (low 5 bits)."""
    offset = 0
    while offset < len(data):
        tag, value, offset = decode_tlv(data, offset)
        if (tag & 0x1F) == wanted:
            return value
    return None
