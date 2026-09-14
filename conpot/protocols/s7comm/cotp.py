# This implementation of the S7 protocol is highly inspired
# by the amazing plcscan work by the ScadaStrangeLove group.
# https://code.google.com/p/plcscan/source/browse/trunk/s7.py

from struct import pack, unpack
import struct
from conpot.protocols.s7comm.exceptions import ParseException
from conpot.utils.networking import str_to_bytes


class COTP(object):
    def __init__(self, tpdu_type=0, opt_field=0, payload="", trailer=""):
        self.tpdu_type = tpdu_type
        self.opt_field = opt_field
        self.payload = payload
        self.trailer = trailer

        if self.tpdu_type == 240:
            self.packet_length = 2
        else:
            self.packet_length = 1 + len(self.payload)

            # COTP BASE PACKET FORMAT:
            # -------------------------------------
            #           1 byte      LENGTH (=n + 1)
            #           1 byte      TPDU TYPE
            #           1 byte      OPT FIELD (optional!), bitmask!
            #           n bytes     TPDU PAYLOAD
            #           x bytes     TRAILER (optional!), most probably containing S7.

    def pack(self):
        if self.tpdu_type == 0xF0:
            return (
                pack("!BBB", self.packet_length, self.tpdu_type, self.opt_field)
                + str_to_bytes(self.payload)
                + str_to_bytes(self.trailer)
            )
        else:
            return (
                pack("!BB", self.packet_length, self.tpdu_type)
                + str_to_bytes(self.payload)
                + str_to_bytes(self.trailer)
            )

    def parse(self, packet):
        try:
            header = unpack("!BBB", packet[:3])
        except struct.error:
            raise ParseException("s7comm", "malformed packet header structure")

        self.packet_length = header[0]
        self.tpdu_type = int(header[1])
        self.trailer = packet[1 + self.packet_length :]

        if self.tpdu_type == 0xF0:
            # the DT DATA TPDU features another header byte that shifts our structure
            self.opt_field = header[2]
            self.payload = packet[3 : 1 + self.packet_length]
        else:
            self.payload = packet[2 : 1 + self.packet_length]

        return self


# COTP Connection Request or Connection Confirm packet (ISO on TCP). RFC 1006
class COTPConnectionPacket:
    def __init__(
        self, dst_ref=0, src_ref=0, opt_field=0, src_tsap=0, dst_tsap=0, tpdu_size=0
    ):
        self.dst_ref = dst_ref
        self.src_ref = src_ref
        self.opt_field = opt_field
        self.src_tsap = src_tsap
        self.dst_tsap = dst_tsap
        self.tpdu_size = tpdu_size

        # COTP CR PACKET FORMAT:
        # -------------------------------------
        #           2 bytes     DST REFERENCE
        #           2 bytes     SRC REFERENCE
        #           1 byte      OPTION FIELD (bitmask!)
        #          ---------------------------------------
        #           n bytes     1 byte  PARAM CODE
        #                       1 byte  PARAM LENGTH (n)
        #                       n bytes PARAM DATA
        #          ---------------------------------------
        #           "n" Block repeats until end of packet

    @staticmethod
    def _decode_tsap(data):
        # ISO 8073 TSAPs are opaque; classic S7 uses 1-2 byte numeric IDs.
        if len(data) == 1:
            return data[0]
        if len(data) == 2:
            return unpack("!H", data)[0]
        return data

    @staticmethod
    def _pack_tsap_param(code, value):
        if isinstance(value, (bytes, bytearray)):
            data = bytes(value)
            return pack("!BB", code, len(data)) + data
        # Preserve historical 2-byte encoding for numeric TSAPs.
        return pack("!BBH", code, 2, value)

    def dissect(self, packet):
        # dissect fixed header
        try:
            fixed_header = unpack("!HHB", packet[:5])
        except struct.error:
            raise ParseException("s7comm", "malformed fixed header structure")

        self.dst_ref = fixed_header[0]
        self.src_ref = fixed_header[1]
        self.opt_field = fixed_header[2]

        # dissect variable header — param lengths are not limited to 1/2 bytes
        # (issue #452: tools such as S7-1200 PLC Control send longer TSAPs).
        chunk = packet[5:]
        while len(chunk) > 0:
            if len(chunk) < 2:
                raise ParseException("s7comm", "malformed variable header structure")

            chunk_param_code = chunk[0]
            chunk_param_length = chunk[1]
            if len(chunk) < 2 + chunk_param_length:
                raise ParseException("s7comm", "malformed variable header structure")

            chunk_param_data = chunk[2 : 2 + chunk_param_length]

            if chunk_param_code == 0xC1:
                self.src_tsap = self._decode_tsap(chunk_param_data)
            elif chunk_param_code == 0xC2:
                self.dst_tsap = self._decode_tsap(chunk_param_data)
            elif chunk_param_code == 0xC0:
                if chunk_param_length < 1:
                    raise ParseException(
                        "s7comm", "malformed variable header structure"
                    )
                self.tpdu_size = chunk_param_data[0]
            # Unknown ISO 8073 options: skip so the honeypot stays resilient.

            chunk = chunk[2 + chunk_param_length :]

        return self


class COTP_ConnectionConfirm(COTPConnectionPacket):
    def __init__(
        self, dst_ref=0, src_ref=0, opt_field=0, src_tsap=0, dst_tsap=0, tpdu_size=0
    ):
        super().__init__(dst_ref, src_ref, opt_field, src_tsap, dst_tsap, tpdu_size)

    def assemble(self):
        return (
            pack("!HHB", self.dst_ref, self.src_ref, self.opt_field)
            + self._pack_tsap_param(0xC1, self.src_tsap)
            + self._pack_tsap_param(0xC2, self.dst_tsap)
        )


class COTP_ConnectionRequest(COTPConnectionPacket):
    def __init__(
        self, dst_ref=0, src_ref=0, opt_field=0, src_tsap=0, dst_tsap=0, tpdu_size=0
    ):
        super().__init__(dst_ref, src_ref, opt_field, src_tsap, dst_tsap, tpdu_size)

    def assemble(self):
        return (
            pack("!HHB", self.dst_ref, self.src_ref, self.opt_field)
            + self._pack_tsap_param(0xC1, self.src_tsap)
            + self._pack_tsap_param(0xC2, self.dst_tsap)
            + pack("!BBB", 0xC0, 1, self.tpdu_size)
        )
