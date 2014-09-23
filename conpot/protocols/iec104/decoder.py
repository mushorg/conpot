# Copyright (C 2014 Lukas Rist <glaslos@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option any later version.
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
import logging

from collections import namedtuple


logger = logging.getLogger(__name__)


ASDU_TYPE_71 = {
    "64": ["C_IC_NA_1", "Interrogation command"],
    "65": ["C_CI_NA_1", "Counter interrogation command"],
    "66": ["C_RD_NA_1", "Read Command"],
    "67": ["C_CS_NA_1", "Clock synchronisation command"],
    "68": ["C_TS_NA_1", "Test command"],
    "69": ["C_RP_NA_1", "Reset process command"],
    "6A": ["C_CD_NA_1", "C_CD_NA_1 Delay acquisition command"],
    "6B": ["C_TS_TA_1", "Test command with time tag CP56Time2a"]
}


class Decoder(object):
    """
    http://infosys.beckhoff.com/english.php?content=../content/1033/tcplclibiec870_5_104/html/tcplclibiec870_5_104_telegrammstructure.htm&id=
    """
    @staticmethod
    def unpack(data):
        print len(data)
        packed_apci, asdu = data[:6], data[6:]
        apci = namedtuple(
            'unpacked_header', 
            'start_byte, length_apdu, ctrl_1, ctrl_2, ctrl_3, ctrl_4'
        )
        unpacked_apci = apci._make(struct.unpack("bbbbbb", packed_apci))

        if len(data) >= 7:
            type_id = data[6].encode("hex")
            try:
                print ASDU_TYPE_71[type_id]
            except KeyError:
                print "Unknown type: ASDU_TYPE_{}".format(type_id)
        return unpacked_apci

    def decode_in(self, data):
        unpacked_apci = self.unpack(data)
        print unpacked_apci
        print repr(data)

    def decode_out(self, data):
        unpacked_apci = self.unpack(data)
        print unpacked_apci
        print repr(data)


if __name__ == "__main__":
    in_data = '\x68\x0E\x4E\x14\x7C\x00\x65\x01\x0A\x00\x0C\x00\x00\x00\x00\x05'
    #out_data = '\x05d\nD\x01\x00\n\x00n%\xc9\xc6\x81\x00\x00Q\x8a'
    d = Decoder()
    d.decode_in(in_data)
    #d.decode_out(out_data)