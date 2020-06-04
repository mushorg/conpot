# Copyright (C) 2017  Patrick Reichenberger (University of Passau) <patrick.reichenberger@t-online.de>
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

from scapy.all import *
from datetime import datetime


# Structure of control field formats
class i_frame(Packet):
    name = "i_frame"
    fields_desc = [
        XByteField("Start", 0x68),
        ByteField("LenAPDU", None),
        LEShortField("SendSeq", 0x0),
        LEShortField("RecvSeq", 0x0),
    ]

    # Compute length
    def post_build(self, p, pay):
        if self.LenAPDU is None:
            length = len(pay) + 4
            p = p[:1] + struct.pack("!B", length) + p[2:]
        return p + pay


class u_frame(Packet):
    name = "u_frame"
    fields_desc = [
        XByteField("Start", 0x68),
        ByteField("LenAPDU", 0x04),
        XByteField("Type", 0x07),
        X3BytesField("Default", 0x000000),
    ]


class s_frame(Packet):
    name = "s_frame"
    fields_desc = [
        XByteField("Start", 0x68),
        ByteField("LenAPDU", 0x04),
        XByteField("Type", 0x01),
        XByteField("Default", 0x00),
        LEShortField("RecvSeq", 0x0),
    ]  # 0001 is in packet 01 00 and that's true, bec 1 is LSB


TypeIdentification = {
    # Single point information
    "M_SP_NA_1": 1,
    # Single point information with time tag
    "M_SP_TA_1": 2,
    # Double point information
    "M_DP_NA_1": 3,
    # Double point information with time tag
    "M_DP_TA_1": 4,
    # Step position information
    # "M_ST_NA_1": 5,
    # Step position information with time tag
    # "M_ST_TA_1": 6,
    # Bit string of 32 bit
    # "M_BO_NA_1": 7,
    # Bit string of 32 bit with time tag
    # "M_BO_TA_1": 8,
    # Measured value, normalized value
    # "M_ME_NA_1": 9,
    # Measured value, normalized value with time tag
    # "M_ME_TA_1": 10,
    # Measured value, scaled value
    "M_ME_NB_1": 11,
    # Measured value, scaled value with time tag
    "M_ME_TB_1": 12,
    # Measured value, short floating point value
    "M_ME_NC_1": 13,
    # Measured value, short floating point value with time tag
    "M_ME_TC_1": 14,
    # Integrated totals
    # "M_IT_NA_1": 15,
    # Integrated totals with time tag
    # "M_IT_TA_1": 16,
    # Event of protection equipment with time tag
    # "M_EP_TA_1": 17,
    # Packed start events of protection equipment with time tag
    # "M_EP_TB_1": 18,
    # Packed output circuit information of protection equipment with time tag
    # "M_EP_TC_1": 19,
    # Packed single-point information with status change detection
    # "M_PS_NA_1": 20,
    # Measured value, normalized value without quality descriptor
    # "M_ME_ND_1": 21,
    # Process telegrams with long time tag ( 7 octets ) :
    # Single point information with time tag CP56Time2a
    "M_SP_TB_1": 30,
    # Double point information with time tag CP56Time2a
    "M_DP_TB_1": 31,
    # Step position information with time tag CP56Time2a
    # "M_ST_TB_1": 32,
    # Bit string of 32 bit with time tag CP56Time2a
    # "M_BO_TB_1": 33,
    # Measured value, normalized value with time tag CP56Time2a
    # "M_ME_TD_1": 34,
    # Measured value, scaled value with time tag CP56Time2a
    "M_ME_TE_1": 35,
    # Measured value, short floating point value with time tag CP56Time2a
    "M_ME_TF_1": 36,
    # Integrated totals with time tag CP56Time2a
    # "M_IT_TB_1": 37,
    # Event of protection equipment with time tag CP56Time2a
    # "M_EP_TD_1": 38,
    # Packed start events of protection equipment with time tag CP56time2a
    # "M_EP_TE_1": 39,
    # Packed output circuit information of protection equipment with time tag CP56Time2a
    # "M_EP_TF_1": 40,
    # Process information in control direction:
    # Single command
    "C_SC_NA_1": 45,
    # Double command
    "C_DC_NA_1": 46,
    # Regulating step command
    # "C_RC_NA_1": 47,
    # Setpoint command, normalized value
    # "C_SE_NA_1": 48,
    # Setpoint command, scaled value
    "C_SE_NB_1": 49,
    # Setpoint command, short floating point value
    "C_SE_NC_1": 50,
    # Bit string  32 bit
    # "C_BO_NA_1": 51,
    # Command telegrams with long time tag ( 7 octets ):
    # Single command with time tag CP56Time2a
    # "C_SC_TA_1": 58,
    # Double command with time tag CP56Time2a
    # "C_DC_TA_1": 59,
    # Regulating step command with time tag CP56Time2a
    # "C_RC_TA_1": 60,
    # Setpoint command, normalized value with time tag CP56Time2a
    # "C_SE_TA_1": 61,
    # Setpoint command, scaled value with time tag CP56Time2a
    # "C_SE_TB_1": 62,
    # Setpoint command, short floating point value with time tag CP56Time2a
    # "C_SE_TC_1": 63,
    # Bit string 32 bit with time tag CP56Time2a
    # "C_BO_TA_1": 64,
    # System information  in monitoring direction :
    # End of initialization
    # "M_EI_NA_1": 70,
    # System information in control direction :
    # (General-) Interrogation command
    "C_IC_NA_1": 100,
    # Counter interrogation command
    # "C_CI_NA_1": 101,
    # Read command
    # "C_RD_NA_1": 102,
    # Clock synchronization command
    # "C_CS_NA_1": 103,
    # ( IEC 101 ) Test command
    # "C_TS_NB_1": 104,
    # Reset process command
    # "C_RP_NC_1": 105,
    # ( IEC 101 ) Delay acquisition command
    # "C_CD_NA_1": 106,
    # Test command with time tag CP56Time2a
    # "C_TS_TA_1": 107,
    #  Parameter in control direction :
    # Parameter of measured value, normalized value
    # "P_ME_NA_1": 110,
    # Parameter of measured value, scaled value
    # "P_ME_NB_1": 111,
    # Parameter of measured value, short floating point value
    # "P_ME_NC_1": 112,
    # Parameter activation
    # "P_AC_NA_1": 113,
    # File transfer:
    # File ready
    # "F_FR_NA_1": 120,
    # Section ready
    # "F_SR_NA_1": 121,
    # Call directory, select file, call file, call section
    # "F_SC_NA_1": 122,
    # Last section, last segment
    # "F_LS_NA_1": 123,
    # Ack file, Ack section
    # "F_AF_NA_1": 124,
    # Segment
    # "F_SG_NA_1": 125,
    # Directory
    # "F_DR_TA_1": 126,
    # QueryLog - Request archive file
    # "F_SC_NB_1": 127
}


class LESignedShortField(Field):
    def __init__(self, name, default):
        Field.__init__(self, name, default, "<h")


class NormValueField(LESignedShortField):
    def i2repr(self, pkt, x):
        normalized = 2 * ((x + 2 ** 15) / ((2 ** 15 + 2 ** 15.0) - 1)) - 1
        return self.i2h(pkt, normalized)


class CP56Time(Packet):
    name = "CP56Time"
    fields_desc = [
        ShortField("Ms", 0x0000),
        ByteField("Min", 0x00),
        ByteField("Hour", 0x0),
        ByteField("Day", 0x01),
        ByteField("Month", 0x01),
        ByteField("Year", 0x5B),
    ]


class CP24Time(Packet):
    name = "CP24Time"
    fields_desc = [ShortField("Ms", 0x0000), ByteField("Min", 0x00)]

    def extract_padding(self, p):
        return "", p


class CP16Time(Packet):
    name = "CP24Time"
    fields_desc = [ShortField("Ms", 0x0000)]

    def extract_padding(self, p):
        return "", p


# Info Elements


class IOA(Packet):
    name = "IOA"
    fields_desc = [LEX3BytesField("IOA", 0x010000)]


class QOS(Packet):
    #  Quality of set-point command
    name = "QOS"
    fields_desc = [XBitField("S/E", 0, 1), XBitField("QL", 0, 7)]


class QDS(Packet):
    #  Quality descriptor
    name = "QDS"
    fields_desc = [
        XBitField("IV", 0, 1),
        XBitField("NT", 0, 1),
        XBitField("SB", 0, 1),
        XBitField("BL", 0, 1),
        XBitField("Padding", 0, 3),
        XBitField("OV", 0, 1),
    ]

    def extract_padding(self, p):
        return "", p


class QDP(Packet):
    name = "QDP"
    fields_desc = [
        XBitField("IV", 0, 1),
        XBitField("NT", 0, 1),
        XBitField("SB", 0, 1),
        XBitField("BL", 0, 1),
        XBitField("EI", 0, 1),
        XBitField("Padding", 0, 3),
    ]

    def extract_padding(self, p):
        return "", p


class SIQ(Packet):
    name = "SIQ"
    fields_desc = [
        #  XByteField("SIQ", 0x00)]
        #  Exacter representation for SIQ:
        XBitField("IV", 0, 1),
        XBitField("NT", 0, 1),
        XBitField("SB", 0, 1),
        XBitField("BL", 0, 1),
        XBitField("Padding", 0, 3),
        XBitField("SPI", 0, 1),
    ]


class BSI(Packet):
    name = "BSI"
    fields_desc = [LEIntField("BSI", 0)]


class DIQ(Packet):
    name = "DIQ"
    fields_desc = [
        #  XByteField("DIQ", 0x00)]
        #  Exacter representation for DIQ:
        XBitField("IV", 0, 1),
        XBitField("NT", 0, 1),
        XBitField("SB", 0, 1),
        XBitField("BL", 0, 1),
        XBitField("Padding", 0, 2),
        XBitField("DPI", 0, 2),
    ]


class VTI(Packet):
    name = "VTI"
    fields_desc = [XBitField("T", 0, 1), XBitField("Value", 0, 7)]


class NVA(Packet):
    # Normalized value
    name = "NVA"
    fields_desc = [NormValueField("NVA", 0x5000)]


class SVA(Packet):
    # Scaled value
    name = "SVA"
    fields_desc = [LESignedShortField("SVA", 0x50)]


class BCR(Packet):
    #  Binary Counter Reading
    name = "BCR"
    fields_desc = [
        LESignedIntField("Value", 0x0),
        XBitField("IV", 0, 1),
        XBitField("CA", 0, 1),
        XBitField("CY", 0, 1),
        XBitField("SeqNr", 0, 5),
    ]


class SEP(Packet):
    name = "SEP"
    fields_desc = [
        XBitField("IV", 0, 1),
        XBitField("NT", 0, 1),
        XBitField("SB", 0, 1),
        XBitField("BL", 0, 1),
        XBitField("EI", 0, 1),
        XBitField("Padding", 0, 1),
        XBitField("ES", 0, 2),
    ]

    def extract_padding(self, p):
        return "", p


class SPE(Packet):
    name = "SPE"
    fields_desc = [
        XBitField("Padding", 0, 2),
        XBitField("SRD", 0, 1),
        XBitField("SIE", 0, 1),
        XBitField("SL3", 0, 1),
        XBitField("SL2", 0, 1),
        XBitField("SL2", 0, 1),
        XBitField("GS", 0, 1),
    ]

    def extract_padding(self, p):
        return "", p


class OCI(Packet):
    name = "OCI"
    fields_desc = [
        XBitField("Padding", 0, 4),
        XBitField("CL3", 0, 1),
        XBitField("CL2", 0, 1),
        XBitField("CL1", 0, 1),
        XBitField("GC", 0, 1),
    ]


class SCD(Packet):
    name = "SCD"
    fields_desc = [
        LEShortField("Status", 0x0),  # LE?
        LEShortField("StatChaDet", 0x0),
    ]  # LE?


class FloatField(Field):
    def __init__(self, name, default):
        Field.__init__(self, name, default, "<f")


# ASDU packets
class asdu_infobj_1(Packet):
    name = "M_SP_NA_1"
    fields_desc = [
        IOA,
        # SIQ]
        PacketField("SIQ", SIQ(), SIQ),
    ]


class asdu_infobj_2(Packet):
    name = "M_SP_TA_1"
    fields_desc = [
        IOA,
        PacketField("SIQ", SIQ(), SIQ),
        PacketField("CP24Time", CP24Time(), CP24Time),
    ]


class asdu_infobj_3(Packet):
    name = "M_DP_NA_1"
    fields_desc = [IOA, PacketField("DIQ", DIQ(), DIQ)]


class asdu_infobj_4(Packet):
    name = "M_DP_TA_1"
    fields_desc = [
        IOA,
        PacketField("DIQ", DIQ(), DIQ),
        PacketField("CP24Time", CP24Time(), CP24Time),
    ]


class asdu_infobj_5(Packet):
    name = "M_ST_NA_1"
    fields_desc = [IOA, PacketField("VTI", VTI(), VTI), PacketField("QDS", QDS(), QDS)]


class asdu_infobj_6(Packet):
    name = "M_ST_TA_1"
    fields_desc = [
        IOA,
        PacketField("VTI", VTI(), VTI),
        PacketField("QDS", QDS(), QDS),
        PacketField("CP24Time", CP24Time(), CP24Time),
    ]


class asdu_infobj_7(Packet):
    name = "M_BO_NA_1"
    fields_desc = [IOA, BSI, PacketField("QDS", QDS(), QDS)]


class asdu_infobj_8(Packet):
    name = "M_BO_TA_1"
    fields_desc = [
        IOA,
        BSI,
        PacketField("QDS", QDS(), QDS),
        PacketField("CP24Time", CP24Time(), CP24Time),
    ]


class asdu_infobj_9(Packet):
    name = "M_ME_NA_1"
    fields_desc = [IOA, NVA, PacketField("QDS", QDS(), QDS)]


class asdu_infobj_10(Packet):
    name = "M_ME_TA_1"
    fields_desc = [
        IOA,
        NVA,
        PacketField("QDS", QDS(), QDS),
        PacketField("CP24Time", CP24Time(), CP24Time),
    ]


class asdu_infobj_11(Packet):
    name = "M_ME_NB_1"
    fields_desc = [IOA, SVA, PacketField("QDS", QDS(), QDS)]


class asdu_infobj_12(Packet):
    name = "M_ME_TB_1"
    fields_desc = [
        IOA,
        SVA,
        PacketField("QDS", QDS(), QDS),
        PacketField("CP24Time", CP24Time(), CP24Time),
    ]


class asdu_infobj_13(Packet):
    name = "M_ME_NC_1"
    fields_desc = [IOA, FloatField("FPNumber", 1), PacketField("QDS", QDS(), QDS)]


class asdu_infobj_14(Packet):
    name = "M_ME_TC_1"
    fields_desc = [
        IOA,
        FloatField("FPNumber", 0),
        PacketField("QDS", QDS(), QDS),
        PacketField("CP24Time", CP24Time(), CP24Time),
    ]


class asdu_infobj_15(Packet):
    name = "M_IT_NA_1"
    fields_desc = [IOA, PacketField("BCR", BCR(), BCR)]


class asdu_infobj_16(Packet):
    name = "M_IT_TA_1"
    fields_desc = [
        IOA,
        PacketField("BCR", BCR(), BCR),
        PacketField("CP24Time", CP24Time(), CP24Time),
    ]


class asdu_infobj_17(Packet):
    name = "M_EP_TA_1"
    fields_desc = [
        IOA,
        PacketField("SEP", SEP(), SEP),
        CP16Time,  # elapsed time
        PacketField("CP24Time", CP24Time(), CP24Time),
    ]  # binary time


class asdu_infobj_18(Packet):
    name = "M_EP_TB_1"
    fields_desc = [
        IOA,
        PacketField("SPE", SPE(), SPE),
        PacketField("QDP", QDP(), QDP),
        CP16Time,  # elapsed time
        PacketField("CP24Time", CP24Time(), CP24Time),
    ]  # binary time


class asdu_infobj_19(Packet):
    name = "M_EP_TC_1"
    fields_desc = [
        IOA,
        PacketField("OCI", OCI(), OCI),
        PacketField("QDP", QDP(), QDP),
        CP16Time,  # relay duration time
        PacketField("CP24Time", CP24Time(), CP24Time),
    ]  # binary time


class asdu_infobj_20(Packet):
    name = "M_PS_NA_1"
    fields_desc = [IOA, PacketField("SCD", SCD(), SCD), PacketField("QDS", QDS(), QDS)]


class asdu_infobj_21(Packet):
    name = "M_ME_ND_1"
    fields_desc = [IOA, NVA]


class asdu_infobj_30(Packet):
    name = "M_SP_TB_1"
    fields_desc = [
        IOA,
        PacketField("SIQ", SIQ(), SIQ),
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]


class asdu_infobj_31(Packet):
    name = "M_DP_TB_1"
    fields_desc = [
        IOA,
        PacketField("DIQ", DIQ(), DIQ),
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]


class asdu_infobj_32(Packet):
    name = "M_ST_TA_1"
    fields_desc = [
        IOA,
        PacketField("VTI", VTI(), VTI),
        PacketField("QDS", QDS(), QDS),
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]


class asdu_infobj_33(Packet):
    name = "M_BO_TB_1"
    fields_desc = [
        IOA,
        PacketField("BSI", BSI(), BSI),
        PacketField("QDS", QDS(), QDS),
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]


class asdu_infobj_34(Packet):
    name = "M_ME_TD_1"
    fields_desc = [
        IOA,
        NVA,
        PacketField("QDS", QDS(), QDS),
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]


class asdu_infobj_35(Packet):
    name = "M_ME_TE_1"
    fields_desc = [
        IOA,
        SVA,
        PacketField("QDS", QDS(), QDS),
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]


class asdu_infobj_36(Packet):
    name = "M_ME_TF_1"
    fields_desc = [
        IOA,
        FloatField("FPNumber", 0),
        PacketField("QDS", QDS(), QDS),
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]


class asdu_infobj_37(Packet):
    name = "M_IT_TB_1"
    fields_desc = [
        IOA,
        PacketField("BCR", BCR(), BCR),
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]


class asdu_infobj_38(Packet):
    name = "M_EP_TD_1"
    fields_desc = [
        IOA,
        PacketField("SEP", SEP(), SEP),
        CP16Time,  # elapsed time
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]  # binary time


class asdu_infobj_39(Packet):
    name = "M_EP_TE_1"
    fields_desc = [
        IOA,
        PacketField("SPE", SPE(), SPE),
        PacketField("QDP", QDP(), QDP),
        CP16Time,  # relay duration time
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]  # binary time


class asdu_infobj_40(Packet):
    name = "M_EP_TF_1"
    fields_desc = [
        IOA,
        PacketField("OCI", OCI(), OCI),
        PacketField("QDP", QDP(), QDP),
        CP16Time,  # relay duration time
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]  # binary time


class asdu_infobj_45(Packet):
    name = "C_SC_NA_1"
    fields_desc = [
        IOA,
        #  XByteField("SCO", 0x00)]
        #  Exacter representation(2) for SCO:
        #  XBitField("S/E", 0, 1), XBitField("QU", 0, 5), XBitField("Padding", 0, 1), XBitField("SCS", 0, 1)]
        XBitField("QOC", 0, 6),
        XBitField("Padding", 0, 1),
        BitField("SCS", 0, 1),
    ]


class asdu_infobj_46(Packet):
    name = "C_DC_NA_1"
    fields_desc = [
        IOA,
        #  XByteField("SCO", 0x00)]
        #  Exacter representation(2) for DCO:
        #  XBitField("S/E", 0, 1), XBitField("QU", 0, 5), XBitField("DCS", 0, 2)]
        XBitField("QOC", 0, 6),
        XBitField("DCS", 0, 2),
    ]


class asdu_infobj_47(Packet):
    name = "C_RC_NA_1"
    fields_desc = [
        IOA,
        #  XByteField("SCO", 0x00)]
        #  Exacter representation(2) for RCO:
        #  XBitField("S/E", 0, 1), XBitField("QU", 0, 5), XBitField("RCS", 0, 2)]
        XBitField("QOC", 0, 6),
        XBitField("RCS", 0, 2),
    ]


class asdu_infobj_48(Packet):
    name = "C_SE_NA_1"
    fields_desc = [
        IOA,
        # Normalized value
        NVA,
        PacketField("QOS", QOS(), QOS),
    ]


class asdu_infobj_49(Packet):
    name = "C_SE_NB_1"
    fields_desc = [
        IOA,
        # Scaled value
        SVA,
        PacketField("QOS", QOS(), QOS),
    ]


class asdu_infobj_50(Packet):
    name = "C_SE_NC_1"
    fields_desc = [IOA, FloatField("FPNumber", 0), PacketField("QOS", QOS(), QOS)]


class asdu_infobj_51(Packet):
    name = "C_BO_NA_1"
    fields_desc = [IOA, BSI]


# maybe in handle client
def calctime():
    currenttime = datetime.now()
    milliseconds = currenttime.microsecond / 1000
    seconds = currenttime.second
    ms = seconds * 1000 + milliseconds
    minutes = currenttime.minute
    hour = currenttime.hour
    day = currenttime.day
    month = currenttime.month
    year = currenttime.year
    cp56time = CP56Time()
    cp56time.setfieldval("Ms", ms)
    cp56time.setfieldval("Min", minutes)
    cp56time.setfieldval("Hour", hour)
    cp56time.setfieldval("Day", day)
    cp56time.setfieldval("Month", month)
    cp56time.setfieldval("Year", year)
    return cp56time


class asdu_infobj_58(Packet):
    name = "C_SC_TA_1"
    fields_desc = [
        IOA,
        #  XByteField("SCO", 0x00)]
        #  Exacter representation(2) for SCO:
        #  XBitField("S/E", 0, 1), XBitField("QU", 0, 5), XBitField("Padding", 0, 1), XBitField("SCS", 0, 1)]
        XBitField("QOC", 0, 6),
        XBitField("Padding", 0, 1),
        BitField("SCS", 0, 1),
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]


class asdu_infobj_59(Packet):
    name = "C_DC_TA_1"
    fields_desc = [
        IOA,
        #  XByteField("DCO", 0x00)]
        #  Exacter representation(2) for DCO:
        #  XBitField("S/E", 0, 1), XBitField("QU", 0, 5), XBitField("DCS", 0, 2)]
        XBitField("QOC", 0, 6),
        XBitField("DCS", 0, 2),
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]


class asdu_infobj_60(Packet):
    name = "C_RC_TA_1"
    fields_desc = [
        IOA,
        #  XByteField("RCO", 0x00)]
        #  Exacter representation(2) for RCO:
        #  XBitField("S/E", 0, 1), XBitField("QU", 0, 5), XBitField("RCS", 0, 2)]
        XBitField("QOC", 0, 6),
        XBitField("RCS", 0, 2),
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]


class asdu_infobj_61(Packet):
    name = "C_SE_TA_1"
    fields_desc = [
        IOA,
        # Normalized value
        NVA,
        PacketField("QOS", QOS(), QOS),
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]


class asdu_infobj_62(Packet):
    name = "C_SE_TB_1"
    fields_desc = [
        IOA,
        # Scaled value
        SVA,
        PacketField("QOS", QOS(), QOS),
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]


class asdu_infobj_63(Packet):
    name = "C_SE_TC_1"
    fields_desc = [
        IOA,
        FloatField("FPNumber", 0),
        PacketField("QOS", QOS(), QOS),
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]


class asdu_infobj_64(Packet):
    name = "C_BO_TA_1"
    fields_desc = [
        IOA,
        BSI,
        PacketField("QOS", QOS(), QOS),
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]


class asdu_infobj_100(Packet):
    name = "C_IC_NA_1"
    fields_desc = [LEX3BytesField("IOA", 0x0), ByteField("QOI", 0x14)]


class asdu_infobj_101(Packet):
    name = "C_CI_NA_1"
    fields_desc = [LEX3BytesField("IOA", 0x0), ByteField("QCC", 0x05)]


class asdu_infobj_102(Packet):
    name = "C_RD_NA_1"
    fields_desc = [LEX3BytesField("IOA", 0x0)]


class asdu_infobj_103(Packet):
    name = "C_CS_NA_1"
    fields_desc = [
        LEX3BytesField("IOA", 0x0),
        PacketField("CP56Time", CP56Time(), CP56Time),
    ]


# IEC104 asdu head
class asdu_head(Packet):
    name = "asdu_head"
    fields_desc = [
        ByteField("TypeID", 0x05),  # Command Type
        #  Exacter representation for variable structure qualifier
        BitField("SQ", 0b0, 1),
        BitField("NoO", 1, 7),  # SQ and Number of Object
        #  XByteField("NoO", 0x01),
        #  Exacter representation for Cause of Transmission:
        BitField("T", 0, 1),
        BitField("PN", 0, 1),
        BitField("COT", 6, 6),
        # XByteField("COT", 0x06),
        XByteField("OrigAddr", 0x00),
        LEShortField("COA", 0),
    ]

    def __str__(self):
        asdu_infobj = self.payload
        infobj_repr = []

        while not isinstance(asdu_infobj, NoPayload):
            infobj_repr.append(str(asdu_infobj.fields))
            asdu_infobj = asdu_infobj.payload

        return "{} with {} Objects=[{}]".format(
            self.payload.name, self.fields, ", ".join(infobj_repr)
        )

    def guess_payload_class(self, payload):
        if self.TypeID == 1:
            if self.SQ == 0:
                # List--bind_layers(asdu_infobj_1, asdu_infobj_1)  # if SQ = 0
                # List--bind_layers(SIQ, asdu_infobj_1)  # if SQ = 0
                bind_layers(asdu_infobj_1, asdu_infobj_1)  # if SQ = 0
                bind_layers(SIQ, Padding)  # if SQ = 0
            else:
                # List--bind_layers(SIQ, Padding)  # if SQ = 1
                bind_layers(SIQ, SIQ)  # if SQ = 1
            return asdu_infobj_1
        elif self.TypeID == 2:
            return asdu_infobj_2
        elif self.TypeID == 3:
            if self.SQ == 0:
                bind_layers(asdu_infobj_3, asdu_infobj_3)  # if SQ = 0
                bind_layers(DIQ, Padding)  # if SQ = 0
            else:
                bind_layers(DIQ, DIQ)  # if SQ = 1
            return asdu_infobj_3
        elif self.TypeID == 4:
            return asdu_infobj_4
        elif self.TypeID == 5:
            if self.SQ == 0:
                bind_layers(asdu_infobj_5, asdu_infobj_5)  # if SQ = 0
                bind_layers(QDS, Padding)  # if SQ = 0
            else:
                bind_layers(QDS, VTI)  # if SQ = 1
            return asdu_infobj_5
        elif self.TypeID == 6:
            return asdu_infobj_6
        elif self.TypeID == 7:
            if self.SQ == 0:
                bind_layers(asdu_infobj_7, asdu_infobj_7)  # if SQ = 0
                bind_layers(QDS, Padding)  # if SQ = 0
            else:
                bind_layers(QDS, BSI)  # if SQ = 1
            return asdu_infobj_7
        elif self.TypeID == 8:
            return asdu_infobj_8
        elif self.TypeID == 9:
            if self.SQ == 0:
                bind_layers(asdu_infobj_9, asdu_infobj_9)  # if SQ = 0
                bind_layers(QDS, Padding)  # if SQ = 0
            else:
                bind_layers(QDS, NVA)  # if SQ = 1
            return asdu_infobj_9
        elif self.TypeID == 10:
            return asdu_infobj_10
        elif self.TypeID == 11:
            if self.SQ == 0:
                bind_layers(asdu_infobj_11, asdu_infobj_11)  # if SQ = 0
                bind_layers(QDS, Padding)  # if SQ = 0
            else:
                bind_layers(QDS, SVA)  # if SQ = 1
            return asdu_infobj_11
        elif self.TypeID == 12:
            return asdu_infobj_12
        elif self.TypeID == 13:
            if self.SQ == 0:
                bind_layers(asdu_infobj_13, asdu_infobj_13)  # if SQ = 0
                bind_layers(QDS, Padding)  # if SQ = 0
            else:
                bind_layers(QDS, FloatField)  # if SQ = 1
            return asdu_infobj_13
        elif self.TypeID == 14:
            return asdu_infobj_14
        elif self.TypeID == 15:
            return asdu_infobj_15
        elif self.TypeID == 16:
            return asdu_infobj_16
        elif self.TypeID == 17:
            return asdu_infobj_17
        elif self.TypeID == 18:
            return asdu_infobj_18
        elif self.TypeID == 19:
            return asdu_infobj_19
        elif self.TypeID == 20:
            return asdu_infobj_20
        elif self.TypeID == 21:
            return asdu_infobj_21
        elif self.TypeID == 30:
            return asdu_infobj_30
        elif self.TypeID == 31:
            return asdu_infobj_31
        elif self.TypeID == 32:
            return asdu_infobj_32
        elif self.TypeID == 33:
            return asdu_infobj_33
        elif self.TypeID == 34:
            return asdu_infobj_34
        elif self.TypeID == 35:
            return asdu_infobj_35
        elif self.TypeID == 36:
            return asdu_infobj_36
        elif self.TypeID == 37:
            return asdu_infobj_37
        elif self.TypeID == 38:
            return asdu_infobj_38
        elif self.TypeID == 39:
            return asdu_infobj_39
        elif self.TypeID == 40:
            return asdu_infobj_40
        elif self.TypeID == 45:
            return asdu_infobj_45
        elif self.TypeID == 46:
            return asdu_infobj_46
        elif self.TypeID == 47:
            return asdu_infobj_47
        elif self.TypeID == 48:
            return asdu_infobj_48
        elif self.TypeID == 49:
            return asdu_infobj_49
        elif self.TypeID == 50:
            return asdu_infobj_50
        elif self.TypeID == 51:
            return asdu_infobj_51
        elif self.TypeID == 58:
            return asdu_infobj_58
        elif self.TypeID == 59:
            return asdu_infobj_59
        elif self.TypeID == 60:
            return asdu_infobj_60
        elif self.TypeID == 61:
            return asdu_infobj_61
        elif self.TypeID == 62:
            return asdu_infobj_62
        elif self.TypeID == 63:
            return asdu_infobj_63
        elif self.TypeID == 64:
            return asdu_infobj_64
        elif self.TypeID == 100:
            return asdu_infobj_100
        elif self.TypeID == 101:
            return asdu_infobj_101
        elif self.TypeID == 102:
            return asdu_infobj_102
        elif self.TypeID == 103:
            return asdu_infobj_103


bind_layers(i_frame, asdu_head)
bind_layers(asdu_head, asdu_infobj_1, {"TypeID": 1})
bind_layers(asdu_head, asdu_infobj_2, {"TypeID": 2})
bind_layers(asdu_head, asdu_infobj_3, {"TypeID": 3})
bind_layers(asdu_head, asdu_infobj_4, {"TypeID": 4})
bind_layers(asdu_head, asdu_infobj_5, {"TypeID": 5})
bind_layers(asdu_head, asdu_infobj_6, {"TypeID": 6})
bind_layers(asdu_head, asdu_infobj_7, {"TypeID": 7})
bind_layers(asdu_head, asdu_infobj_8, {"TypeID": 8})
bind_layers(asdu_head, asdu_infobj_9, {"TypeID": 9})
bind_layers(asdu_head, asdu_infobj_10, {"TypeID": 10})
bind_layers(asdu_head, asdu_infobj_11, {"TypeID": 11})
bind_layers(asdu_head, asdu_infobj_12, {"TypeID": 12})
bind_layers(asdu_head, asdu_infobj_13, {"TypeID": 13})
bind_layers(asdu_head, asdu_infobj_14, {"TypeID": 14})
bind_layers(asdu_head, asdu_infobj_15, {"TypeID": 15})
bind_layers(asdu_head, asdu_infobj_16, {"TypeID": 16})
bind_layers(asdu_head, asdu_infobj_17, {"TypeID": 17})
bind_layers(asdu_head, asdu_infobj_18, {"TypeID": 18})
bind_layers(asdu_head, asdu_infobj_19, {"TypeID": 19})
bind_layers(asdu_head, asdu_infobj_20, {"TypeID": 20})
bind_layers(asdu_head, asdu_infobj_21, {"TypeID": 21})

bind_layers(asdu_head, asdu_infobj_30, {"TypeID": 30})
bind_layers(asdu_head, asdu_infobj_31, {"TypeID": 31})
bind_layers(asdu_head, asdu_infobj_32, {"TypeID": 32})
bind_layers(asdu_head, asdu_infobj_33, {"TypeID": 33})
bind_layers(asdu_head, asdu_infobj_34, {"TypeID": 34})
bind_layers(asdu_head, asdu_infobj_35, {"TypeID": 35})
bind_layers(asdu_head, asdu_infobj_36, {"TypeID": 36})
bind_layers(asdu_head, asdu_infobj_37, {"TypeID": 37})
bind_layers(asdu_head, asdu_infobj_38, {"TypeID": 38})
bind_layers(asdu_head, asdu_infobj_39, {"TypeID": 39})
bind_layers(asdu_head, asdu_infobj_40, {"TypeID": 40})

bind_layers(asdu_head, asdu_infobj_45, {"TypeID": 45})
bind_layers(asdu_head, asdu_infobj_46, {"TypeID": 46})
bind_layers(asdu_head, asdu_infobj_47, {"TypeID": 47})
bind_layers(asdu_head, asdu_infobj_48, {"TypeID": 48})
bind_layers(asdu_head, asdu_infobj_49, {"TypeID": 49})
bind_layers(asdu_head, asdu_infobj_50, {"TypeID": 50})
bind_layers(asdu_head, asdu_infobj_51, {"TypeID": 51})

bind_layers(asdu_head, asdu_infobj_58, {"TypeID": 58})
bind_layers(asdu_head, asdu_infobj_59, {"TypeID": 59})
bind_layers(asdu_head, asdu_infobj_60, {"TypeID": 60})
bind_layers(asdu_head, asdu_infobj_61, {"TypeID": 61})
bind_layers(asdu_head, asdu_infobj_62, {"TypeID": 62})
bind_layers(asdu_head, asdu_infobj_63, {"TypeID": 63})
bind_layers(asdu_head, asdu_infobj_64, {"TypeID": 64})

bind_layers(asdu_head, asdu_infobj_100, {"TypeID": 100})
bind_layers(asdu_head, asdu_infobj_101, {"TypeID": 101})
bind_layers(asdu_head, asdu_infobj_102, {"TypeID": 102})
bind_layers(asdu_head, asdu_infobj_103, {"TypeID": 103})

# For SQ=1 and SQ=0, experimental..
# bind_layers(asdu_infobj_1, asdu_infobj_1)
# bind_layers(asdu_infobj_1, SIQ)
# bind_layers(SIQ, SIQ)

# bind_layers(asdu_infobj_1, asdu_infobj_1, {'SQ': 0})
# bind_layers(SIQ, asdu_infobj_1, {'SQ': 0})

bind_layers(SIQ, Padding)
bind_layers(DIQ, Padding)
bind_layers(VTI, Padding)
bind_layers(QDS, Padding)
bind_layers(BCR, Padding)
bind_layers(SEP, Padding)
bind_layers(SPE, Padding)
bind_layers(QDP, Padding)
bind_layers(QOS, Padding)

STARTDT_act = u_frame(Type=0x07)
STARTDT_con = u_frame(Type=0x0B)
STOPDT_act = u_frame(Type=0x13)
STOPDT_con = u_frame(Type=0x23)
TESTFR_act = u_frame(Type=0x43)
TESTFR_con = u_frame(Type=0x83)

u_list = {
    "0x7": "STARTDT_ACT",
    "0xB": "STARTDT_CON",
    "0x13": "STOPDT_act",
    "0x23": "STOPDT_con",
    "0x43": "TESTFR_act",
    "0x83": "TESTFR_con",
}

# ==== Timeouts ==== old.....
# Timeout of connection establishment
# T_0 = 30
# Timeout of send or test APDUs (Wartezeit auf Quittung)
# T_1 = 15
# Timeout for acknowledges in case of no data messages T_2 < T_1 (Quittieren nach x sek)
# T_2 = 10
# Timeout for sending test frames in case of a long idle state
# T_3 = 21

# ==== Other parameters ====
# Maximum difference receive sequence number to send state variable (Max. Anzahl unquittierter Telegramme)
# k = 12
# Latest acknowledge after receiving w I-format APDUs (Quittieren nach w Telegrammen)
# w = 8
# Maximum frame size (in bytes)
# MaxFrameSize = 254

# Testing a packet:

# test2 = i_frame() / asdu_head()
#  test2.SIQ = SIQ(IV=1)  #  Change value in PacketField-packet
# hexdump(test2)
# test2.show()
