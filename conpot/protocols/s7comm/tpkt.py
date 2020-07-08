from struct import pack, unpack
import struct
from conpot.helpers import str_to_bytes
from conpot.protocols.s7comm.exceptions import ParseException


class TPKT:
    # References: rfc2126 section-4.3, rfc1006# section-6
    # Packet format:
    # +--------+--------+----------------+-----------....---------------+
    # |version |reserved| packet length  |             TPDU             |
    # +----------------------------------------------....---------------+
    # <8 bits> <8 bits> <   16 bits    > <       variable length       >

    def __init__(self, version=3, payload=""):
        self.payload = payload
        self.version = version
        self.reserved = 0
        self.packet_length = len(payload) + 4

    def pack(self):
        return pack(
            "!BBH", self.version, self.reserved, self.packet_length
        ) + str_to_bytes(self.payload)

    def parse(self, packet):
        # packet = cleanse_byte_string(packet)
        try:
            # try to extract the header by pattern to find malformed header data
            header = unpack("!BBH", packet[:4])
        except struct.error:
            raise ParseException("s7comm", "malformed packet header structure")

        # extract header data and payload
        self.version = header[0]
        self.reserved = header[1]
        self.packet_length = header[2]
        self.payload = packet[4 : 4 + header[2]]
        return self
