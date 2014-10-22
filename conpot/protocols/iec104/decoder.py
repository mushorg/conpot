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


Type_ID = {
    1: ['M_SP_NA_1', 'Single point information'],
    2: ['M_SP_TA_1', 'Single point information with time tag'],
    3: ['M_DP_NA_1', 'Double point information'],
    4: ['M_DP_TA_1', 'Double point information with time tag'],
    5: ['M_ST_NA_1', 'Step position information'],
    6: ['M_ST_TA_1', 'Step position information with time tag'],
    7: ['M_BO_NA_1', 'Bit string of 32 bit'],
    8: ['M_BO_TA_1', 'Bit string of 32 bit with time tag'],
    9: ['M_ME_NA_1', 'Measured value, normalized value'],
    10: ['M_ME_TA_1', 'Measured value, normalized value with time tag'],
    11: ['M_ME_NB_1', 'Measured value, scaled value'],
    12: ['M_ME_TB_1', 'Measured value, scaled value with time tag'],
    13: ['M_ME_NC_1', 'Measured value, short floating point value'],
    14: ['M_ME_TC_1', 'Measured value, short floating point value with time tag'],
    15: ['M_IT_NA_1', 'Integrated totals'],
    16: ['M_IT_TA_1', 'Integrated totals with time tag'],
    17: ['M_EP_TA_1', 'Event of protection equipment with time tag'],
    18: ['M_EP_TB_1', 'Packed start events of protection equipment with time tag'],
    19: ['M_EP_TC_1', 'Packed output circuit information of protection equipment with time tag'],
    20: ['M_PS_NA_1', 'Packed single-point information with status change detection'],
    21: ['M_ME_ND_1', 'Measured value, normalized value without quality descriptor'],
    30: ['M_SP_TB_1', 'Single point information with time tag CP56Time2a'],
    31: ['M_DP_TB_1', 'Double point information with time tag CP56Time2a'],
    32: ['M_ST_TB_1', 'Step position information with time tag CP56Time2a'],
    33: ['M_BO_TB_1', 'Bit string of 32 bit with time tag CP56Time2a'],
    34: ['M_ME_TD_1', 'Measured value, normalized value with time tag CP56Time2a'],
    35: ['M_ME_TE_1', 'Measured value, scaled value with time tag CP56Time2a'],
    36: ['M_ME_TF_1', 'Measured value, short floating point value with time tag CP56Time2a'],
    37: ['M_IT_TB_1', 'Integrated totals with time tag CP56Time2a'],
    38: ['M_EP_TD_1', 'Event of protection equipment with time tag CP56Time2a'],
    39: ['M_EP_TE_1', 'Packed start events of protection equipment with time tag CP56time2a'],
    40: ['M_EP_TF_1', 'Packed output circuit information of protection equipment with time tag CP56Time2a'],
    45: ['C_SC_NA_1', 'Single command'],
    46: ['C_DC_NA_1', 'Double command'],
    47: ['C_RC_NA_1', 'Regulating step command'],
    48: ['C_SE_NA_1', 'Setpoint command, normalized value'],
    49: ['C_SE_NB_1', 'Setpoint command, scaled value'],
    50: ['C_SE_NC_1', 'Setpoint command, short floating point value'],
    51: ['C_BO_NA_1', 'Bit string  32 bit'],
    58: ['C_SC_TA_1', 'Single command with time tag CP56Time2a'],
    59: ['C_DC_TA_1', 'Double command with time tag CP56Time2a'],
    60: ['C_RC_TA_1', 'Regulating step command with time tag CP56Time2a'],
    61: ['C_SE_TA_1', 'Setpoint command, normalized value with time tag CP56Time2a'],
    62: ['C_SE_TB_1', 'Setpoint command, scaled value with time tag CP56Time2a'],
    63: ['C_SE_TC_1', 'Setpoint command, short floating point value with time tag CP56Time2a'],
    64: ['C_BO_TA_1', 'Bit string 32 bit with time tag CP56Time2a'],
    70: ['M_EI_NA_1', 'End of initialization'],
    100: ['C_IC_NA_1', '(General-) Interrogation command'],
    101: ['C_CI_NA_1', 'Counter interrogation command'],
    102: ['C_RD_NA_1', 'Read command'],
    103: ['C_CS_NA_1', 'Clock synchronization command'],
    104: ['C_TS_NB_1', '( IEC 101 ) Test command'],
    105: ['C_RP_NC_1', 'Reset process command'],
    106: ['C_CD_NA_1', '( IEC 101 ) Delay acquisition command'],
    107: ['C_TS_TA_1', 'Test command with time tag CP56Time2a'],
    110: ['P_ME_NA_1', 'Parameter of measured value, normalized value'],
    111: ['P_ME_NB_1', 'Parameter of measured value, scaled value'],
    112: ['P_ME_NC_1', 'Parameter of measured value, short floating point value'],
    113: ['P_AC_NA_1', 'Parameter activation'],
    120: ['F_FR_NA_1', 'File ready'],
    121: ['F_SR_NA_1', 'Section ready'],
    122: ['F_SC_NA_1', 'Call directory, select file, call file, call section'],
    123: ['F_LS_NA_1', 'Last section, last segment'],
    124: ['F_AF_NA_1', 'Ack file, Ack section'],
    125: ['F_SG_NA_1', 'Segment'],
    126: ['F_DR_TA_1', 'Directory'],
    127: ['F_SC_NB_1', 'QueryLog - Request archive file']
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
        packed_apci, asdu = data[:6], data[6:]
        apci = namedtuple(
            'unpacked_header', 
            'start_byte, length_apdu, ctrl_1, ctrl_2, ctrl_3, ctrl_4'
        )
        unpacked_apci = apci._make(struct.unpack("bbbbbb", packed_apci))

        if len(asdu) >= 1:
            type_id = int(asdu[0].encode("hex"), 16)
            try:
                print type_id, Type_ID[type_id][1]
            except KeyError:
                print "Unknown type id: {}".format(type_id)
            num_obj = 0
            if len(asdu) >= 2:
                num_obj = struct.unpack("b", asdu[1])[0]
                print "num_objects:", num_obj
            if len(asdu) >= 3:
                cot = struct.unpack("b", asdu[2])[0]
                cot_desc = E_IEC870_5_101COTDesc[E_IEC870_5_101COTType[cot]]
                print cot_desc
            if len(asdu) >= 4:
                org_addr = struct.unpack("b", asdu[3])[0]
                print "org_addr:", org_addr
            if len(asdu) >= 6:
                com_addr = struct.unpack("bb", asdu[4:6])
                print "com_addr:", com_addr
            print len(asdu)
            if num_obj > 0 and len(asdu) >= 8:
                objects = dict()
                for i in range(1, num_obj + 1):
                    pos = i * 6
                    objects[i] = asdu[pos:pos + 6]
                    print struct.unpack("b" * len(objects[i]), objects[i])
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
    #in_data = '\x68\x34\x5A\x14\x7C\x00\x0B\x07\x03\x00\x0C\x00\x10\x30\x00\xBE\x09\x00\x11\x30\x00\x90\x09\x00\x0E\x30\x00\x75\x00\x00\x28\x30\x00\x25\x09\x00\x29\x30\x00\x75\x00\x00\x0F\x30\x00\x0F\x0A\x00\x2E\x30\x00\xAE\x05\x00'
    #in_data = '\x68\x0E\x4E\x14\x7C\x00\x65\x01\x0A\x00\x0C\x00\x00\x00\x00\x05'
    in_data = 'h\x19\x04\x00\x04\x00$\x01\x03\x00\x01\x00\x01\x00\x00\xa4pEA\x00`{#\x91\x99\t\x0eh\x15\x06\x00\x04\x00\x1e\x01\x03\x00\x01\x00\x02\x00\x00\x00`{#\x91\x99\t\x0eh\x19\x08\x00\x04\x00%\x01\x03\x00\x01\x00\x03\x00\x00\x07\x87\x00\x00\x00`{#\x91\x99\t\x0e'
    #out_data = '\x05d\nD\x01\x00\n\x00n%\xc9\xc6\x81\x00\x00Q\x8a'
    d = Decoder()
    d.decode_in(in_data)
    #d.decode_out(out_data)