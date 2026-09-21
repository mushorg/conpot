# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""ISO 8073 COTP (TP0) over TPKT — CR/CC/DT for MMS/ICCP."""

from __future__ import annotations

from struct import pack, unpack


class COTPError(ValueError):
    pass


TPDU_CR = 0xE0
TPDU_CC = 0xD0
TPDU_DT = 0xF0
TPDU_DR = 0x80


class COTP:
    def __init__(
        self,
        tpdu_type: int = 0,
        opt_field: int = 0,
        payload: bytes = b"",
        trailer: bytes = b"",
    ):
        self.tpdu_type = tpdu_type
        self.opt_field = opt_field
        self.payload = payload
        self.trailer = trailer
        if self.tpdu_type == TPDU_DT:
            self.packet_length = 2
        else:
            self.packet_length = 1 + len(self.payload)

    def pack(self) -> bytes:
        if self.tpdu_type == TPDU_DT:
            return pack("!BBB", self.packet_length, self.tpdu_type, self.opt_field) + (
                self.payload + self.trailer
            )
        return (
            pack("!BB", self.packet_length, self.tpdu_type)
            + self.payload
            + self.trailer
        )

    def parse(self, packet: bytes) -> "COTP":
        if len(packet) < 2:
            raise COTPError("COTP header too short")
        self.packet_length = packet[0]
        self.tpdu_type = packet[1]
        if self.packet_length < 1 or 1 + self.packet_length > len(packet):
            raise COTPError("invalid COTP length")
        self.trailer = packet[1 + self.packet_length :]
        if self.tpdu_type == TPDU_DT:
            if self.packet_length < 2:
                raise COTPError("DT TPDU too short")
            self.opt_field = packet[2]
            self.payload = packet[3 : 1 + self.packet_length]
        else:
            self.opt_field = 0
            self.payload = packet[2 : 1 + self.packet_length]
        return self


class COTPConnection:
    def __init__(
        self,
        dst_ref: int = 0,
        src_ref: int = 0,
        opt_field: int = 0,
        src_tsap: int | bytes = 0,
        dst_tsap: int | bytes = 0,
        tpdu_size: int = 0x0A,
    ):
        self.dst_ref = dst_ref
        self.src_ref = src_ref
        self.opt_field = opt_field
        self.src_tsap = src_tsap
        self.dst_tsap = dst_tsap
        self.tpdu_size = tpdu_size

    @staticmethod
    def _decode_tsap(data: bytes):
        if len(data) == 1:
            return data[0]
        if len(data) == 2:
            return unpack("!H", data)[0]
        return data

    @staticmethod
    def _pack_tsap(code: int, value: int | bytes) -> bytes:
        if isinstance(value, (bytes, bytearray)):
            data = bytes(value)
            return pack("!BB", code, len(data)) + data
        return pack("!BBH", code, 2, value)

    def dissect(self, packet: bytes) -> "COTPConnection":
        if len(packet) < 5:
            raise COTPError("COTP connection header too short")
        self.dst_ref, self.src_ref, self.opt_field = unpack("!HHB", packet[:5])
        chunk = packet[5:]
        while chunk:
            if len(chunk) < 2:
                raise COTPError("malformed COTP parameter")
            code, length = chunk[0], chunk[1]
            if len(chunk) < 2 + length:
                raise COTPError("truncated COTP parameter")
            data = chunk[2 : 2 + length]
            if code == 0xC1:
                self.src_tsap = self._decode_tsap(data)
            elif code == 0xC2:
                self.dst_tsap = self._decode_tsap(data)
            elif code == 0xC0 and length >= 1:
                self.tpdu_size = data[0]
            chunk = chunk[2 + length :]
        return self

    def assemble_cc(self) -> bytes:
        return (
            pack("!HHB", self.dst_ref, self.src_ref, self.opt_field)
            + self._pack_tsap(0xC1, self.src_tsap)
            + self._pack_tsap(0xC2, self.dst_tsap)
        )

    def assemble_cr(self) -> bytes:
        return self.assemble_cc() + pack("!BBB", 0xC0, 1, self.tpdu_size)


def pack_dt_tpkt(user_data: bytes, eot: bool = True) -> bytes:
    """Wrap Session/Presentation user data in COTP DT + TPKT."""
    from conpot.protocols.iccp.tpkt import TPKT

    header = pack("!BBB", 2, TPDU_DT, 0x80 if eot else 0x00)
    return TPKT(payload=header + user_data).pack()
