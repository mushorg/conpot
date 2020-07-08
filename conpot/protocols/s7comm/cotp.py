# This implementation of the S7 protocol is highly inspired
# by the amazing plcscan work by the ScadaStrangeLove group.
# https://code.google.com/p/plcscan/source/browse/trunk/s7.py

from struct import pack, unpack
import struct
from conpot.helpers import str_to_bytes
from conpot.protocols.s7comm.exceptions import ParseException


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

    def dissect(self, packet):

        # dissect fixed header
        try:
            fixed_header = unpack("!HHB", packet[:5])
        except struct.error:
            raise ParseException("s7comm", "malformed fixed header structure")

        self.dst_ref = fixed_header[0]
        self.src_ref = fixed_header[1]
        self.opt_field = fixed_header[2]

        # dissect variable header
        chunk = packet[5:]
        while len(chunk) > 0:
            chunk_param_header = unpack("!BB", chunk[:2])
            chunk_param_code = int(chunk_param_header[0])
            chunk_param_length = chunk_param_header[1]

            if chunk_param_length == 1:
                param_unpack_structure = "!B"
            elif chunk_param_length == 2:
                param_unpack_structure = "!H"
            else:
                raise ParseException("s7comm", "malformed variable header structure")

            chunk_param_data = unpack(
                param_unpack_structure, chunk[2 : 2 + chunk_param_length]
            )

            if chunk_param_code == 0xC1:
                self.src_tsap = chunk_param_data[0]
            elif chunk_param_code == 0xC2:
                self.dst_tsap = chunk_param_data[0]
            elif chunk_param_code == 0xC0:
                self.tpdu_size = chunk_param_data[0]
            else:
                raise ParseException("s7comm", "unknown parameter code")

            # remove this part of the chunk
            chunk = chunk[2 + chunk_param_length :]

        return self


class COTP_ConnectionConfirm(COTPConnectionPacket):
    def __init__(
        self, dst_ref=0, src_ref=0, opt_field=0, src_tsap=0, dst_tsap=0, tpdu_size=0
    ):
        self.dst_ref = dst_ref
        self.src_ref = src_ref
        self.opt_field = opt_field
        self.src_tsap = src_tsap
        self.dst_tsap = dst_tsap
        self.tpdu_size = tpdu_size
        super().__init__()

    def assemble(self):
        return pack(
            "!HHBBBHBBH",
            self.dst_ref,
            self.src_ref,
            self.opt_field,
            0xC1,  # param code:   src-tsap
            0x02,  # param length: 2 bytes
            self.src_tsap,
            0xC2,  # param code:   dst-tsap
            0x02,  # param length: 2 bytes
            self.dst_tsap,
        )


class COTP_ConnectionRequest(COTPConnectionPacket):
    def __init__(
        self, dst_ref=0, src_ref=0, opt_field=0, src_tsap=0, dst_tsap=0, tpdu_size=0
    ):
        self.dst_ref = dst_ref
        self.src_ref = src_ref
        self.opt_field = opt_field
        self.src_tsap = src_tsap
        self.dst_tsap = dst_tsap
        self.tpdu_size = tpdu_size
        super().__init__()

    def assemble(self):
        return pack(
            "!HHBBBHBBHBBB",
            self.dst_ref,
            self.src_ref,
            self.opt_field,
            0xC1,  # param code:   src-tsap
            0x02,  # param length: 2 bytes
            self.src_tsap,
            0xC2,  # param code:   dst-tsap
            0x02,  # param length: 2 bytes
            self.dst_tsap,
            0xC0,  # param code:   tpdu-size
            0x01,  # param length: 1 byte
            self.tpdu_size,
        )
