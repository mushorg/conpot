# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""RFC 1006 / RFC 2126 TPKT framing for ISO-on-TCP."""

from __future__ import annotations

from struct import pack, unpack

from conpot.utils.networking import str_to_bytes


class TPKTError(ValueError):
    pass


class TPKT:
    def __init__(self, version: int = 3, payload: bytes | str = b""):
        self.version = version
        self.reserved = 0
        self.payload = str_to_bytes(payload)
        self.packet_length = len(self.payload) + 4

    def pack(self) -> bytes:
        return (
            pack("!BBH", self.version, self.reserved, self.packet_length) + self.payload
        )

    def parse(self, packet: bytes) -> "TPKT":
        if len(packet) < 4:
            raise TPKTError("TPKT header too short")
        version, reserved, length = unpack("!BBH", packet[:4])
        if version != 3:
            raise TPKTError(f"unsupported TPKT version {version}")
        if length < 4 or length > len(packet):
            raise TPKTError(f"invalid TPKT length {length}")
        self.version = version
        self.reserved = reserved
        self.packet_length = length
        self.payload = packet[4:length]
        return self
