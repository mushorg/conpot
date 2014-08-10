# Copyright (C) 2014  Lukas Rist <glaslos@gmail.com>
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

import struct
import crc16

from collections import namedtuple


PRIM_FUNC_CODES = {
    0: "Reset of remote link",
    1: "Reset of user process ",
    2: "Test function for link",
    3: "User data",
    4: "Unconfirmed user data",
    9: "Request link status"
}

SEC_FUNC_CODES = {
    0: "ACK - positive acknowledgment",
    1: "NACK - Message not accepted, link busy",
    11: "Status of link (DFC = 0 or 1)",
    14: "Link service not functioning",
    15: "Link service not used or implemented"
}


class Decoder(object):
    def __init__(self):
        pass

    @staticmethod
    def _byte2bit(byte):
        """
        Byte to bit conversion
        """
        return '{:08b}'.format(byte)

    @staticmethod
    def _get_function_code(bits):
        """
        Returns the function code
        """
        return int(bits[4:], 2)

    @staticmethod
    def _is_a2b(bits):
        """
        DIR Direction
        1 = A to B
        0 = B to A
        """
        return bits[0] == "1"

    @staticmethod
    def _is_primary(bits):
        """
        PRM Primary message
        1 = frame from primary (initiating station)
        0 = frame from secondary (responding station)
        """
        return bits[1] == "1"

    @staticmethod
    def unpack(data):
        header, data = data[:10], data[10:]
        Header = namedtuple(
            'unpacked_header', 'start_bytes, user_data_length, byte_string, dest_addr, source_addr, header_crc'
        )
        unpacked_header = Header._make(struct.unpack("2s2BHHH", header))
        for block in (data[i:i+18] for i in xrange(0, len(data), 18)):
            user_data = block[:-2]
            block_crc = struct.unpack("H", block[-2:])
        # TODO: Check CRC sum
        #print header_crc, crc16.crc16xmodem(data[:8])
        return unpacked_header

    def decode_in(self, data):
        unpacked_header = self.unpack(data)
        control_bits = self._byte2bit(unpacked_header.byte_string)
        #print control_bits
        func_code = PRIM_FUNC_CODES[self._get_function_code(control_bits)]
        print "in: {0}".format(func_code), repr(data)

    def decode_out(self, data):
        unpacked_header = self.unpack(data)
        control_bits = self._byte2bit(unpacked_header.byte_string)
        #print control_bits
        func_code = PRIM_FUNC_CODES[self._get_function_code(control_bits)]
        print "out: {0}".format(func_code), repr(data)


if __name__ == "__main__":
    in_data = '\x05d\x0b\xc4\n\x00\x01\x00\xac\xd1\xc7\xc6\x01<\x02\x06~\xf4'
    out_data = '\x05d\nD\x01\x00\n\x00n%\xc9\xc6\x81\x00\x00Q\x8a'
    d = Decoder()
    d.decode_in(in_data)
    d.decode_out(out_data)
