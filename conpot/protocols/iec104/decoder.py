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

E_IEC870_5_101COTType = {
    0: 'eIEC870_COT_UNUSED',
    1: 'eIEC870_COT_CYCLIC',
    2: 'eIEC870_COT_BACKGROUND',
    3: 'eIEC870_COT_SPONTAN',
    4: 'eIEC870_COT_INIT',
    5: 'eIEC870_COT_REQ',
    6: 'eIEC870_COT_ACT',
    7: 'eIEC870_COT_ACT_CON',
    8: 'eIEC870_COT_DEACT',
    9: 'eIEC870_COT_DEACT_CON',
    10: 'eIEC870_COT_ACT_TERM',
    11: 'eIEC870_COT_RETREM',
    12: 'eIEC870_COT_RETLOC',
    13: 'eIEC870_COT_FILE',
    14: 'eIEC870_COT_14',
    15: 'eIEC870_COT_15',
    16: 'eIEC870_COT_16',
    17: 'eIEC870_COT_17',
    18: 'eIEC870_COT_18',
    19: 'eIEC870_COT_19',
    20: 'eIEC870_COT_INROGEN',
    21: 'eIEC870_COT_INRO1',
    22: 'eIEC870_COT_INRO2',
    23: 'eIEC870_COT_INRO3',
    24: 'eIEC870_COT_INRO4',
    25: 'eIEC870_COT_INRO5',
    26: 'eIEC870_COT_INRO6',
    27: 'eIEC870_COT_INRO7',
    28: 'eIEC870_COT_INRO8',
    29: 'eIEC870_COT_INRO9',
    30: 'eIEC870_COT_INRO10',
    31: 'eIEC870_COT_INRO11',
    32: 'eIEC870_COT_INRO12',
    33: 'eIEC870_COT_INRO13',
    34: 'eIEC870_COT_INRO14',
    35: 'eIEC870_COT_INRO15',
    36: 'eIEC870_COT_INRO16',
    37: 'eIEC870_COT_REQCOGEN',
    38: 'eIEC870_COT_REQCO1',
    39: 'eIEC870_COT_REQCO2',
    40: 'eIEC870_COT_REQCO3',
    41: 'eIEC870_COT_REQCO4',
    42: 'eIEC870_COT_42',
    43: 'eIEC870_COT_43',
    44: 'eIEC870_COT_UNKNOWN_TYPE',
    45: 'eIEC870_COT_UNKNOWN_CAUSE',
    46: 'eIEC870_COT_UNKNOWN_ASDU_ADDRESS',
    47: 'eIEC870_COT_UNKNOWN_OBJECT_ADDRESS',
    48: 'eIEC870_COT_48',
    49: 'eIEC870_COT_49',
    50: 'eIEC870_COT_50',
    51: 'eIEC870_COT_51',
    52: 'eIEC870_COT_52',
    53: 'eIEC870_COT_53',
    54: 'eIEC870_COT_54',
    55: 'eIEC870_COT_55',
    56: 'eIEC870_COT_56',
    57: 'eIEC870_COT_57',
    58: 'eIEC870_COT_58',
    59: 'eIEC870_COT_59',
    60: 'eIEC870_COT_60',
    61: 'eIEC870_COT_61',
    62: 'eIEC870_COT_62',
    63: 'eIEC870_COT_63'
}

E_IEC870_5_101COTDesc = {
    "eIEC870_COT_UNUSED": "Not used",
    "eIEC870_COT_CYCLIC": "Cyclic data",
    "eIEC870_COT_BACKGROUND": "Background request",
    "eIEC870_COT_SPONTAN": "Spontaneous data",
    "eIEC870_COT_INIT": "End of initialisation",
    "eIEC870_COT_REQ": "Read-Request",
    "eIEC870_COT_ACT": "Command activation",
    "eIEC870_COT_ACT_CON": "Acknowledgement of command activation",
    "eIEC870_COT_DEACT": "Command abort",
    "eIEC870_COT_DEACT_CON": "Acknowledgement of command abort",
    "eIEC870_COT_ACT_TERM": "Termination of command activation",
    "eIEC870_COT_RETREM": "Return because of remote command",
    "eIEC870_COT_RETLOC": "Return because local command",
    "eIEC870_COT_FILE": "File access",
    "eIEC870_COT_INROGEN": "Station interrogation (general)",
    "eIEC870_COT_INRO1": "Station interrogation of group 1",
    "eIEC870_COT_INRO2": "Station interrogation of group 2",
    "eIEC870_COT_INRO3": "Station interrogation of group 3",
    "eIEC870_COT_INRO4": "Station interrogation of group 4",
    "eIEC870_COT_INRO5": "Station interrogation of group 5",
    "eIEC870_COT_INRO6": "Station interrogation of group 6",
    "eIEC870_COT_INRO7": "Station interrogation of group 7",
    "eIEC870_COT_INRO8": "Station interrogation of group 8",
    "eIEC870_COT_INRO9": "Station interrogation of group 9",
    "eIEC870_COT_INRO10": "Station interrogation of group 10",
    "eIEC870_COT_INRO11": "Station interrogation of group 11",
    "eIEC870_COT_INRO12": "Station interrogation of group 12",
    "eIEC870_COT_INRO13": "Station interrogation of group 13",
    "eIEC870_COT_INRO14": "Station interrogation of group 14",
    "eIEC870_COT_INRO15": "Station interrogation of group 15",
    "eIEC870_COT_INRO16": "Station interrogation of group 16",
    "eIEC870_COT_REQCOGEN": "Counter request (general)",
    "eIEC870_COT_REQCO1": "Counter request of group 1",
    "eIEC870_COT_REQCO2": "Counter request of group 2",
    "eIEC870_COT_REQCO3": "Counter request of group 3",
    "eIEC870_COT_REQCO4": "Counter request of group 4",
    "eIEC870_COT_UNKNOWN_TYPE": "Unknown type",
    "eIEC870_COT_UNKNOWN_CAUSE": "Unknown transmission cause",
    "eIEC870_COT_UNKNOWN_ASDU_ADDRESS": "Unknown collective ASDU address",
    "eIEC870_COT_UNKNOWN_OBJECT_ADDRESS": "Unknown object address",
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
            if len(data) >= 8:
                num_obj = struct.unpack("b", data[7])[0]
                print "num_objects:", num_obj
            if len(data) >= 9:
                cot = struct.unpack("b", data[8])[0]
                cot_desc = E_IEC870_5_101COTDesc[E_IEC870_5_101COTType[cot]]
                print cot_desc
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