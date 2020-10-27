# References: S7_300-400_full_reference_handbook_ENGLISH.pdf
#             http://www.bj-ig.de/147.html
#             https://code.google.com/p/plcscan/source/browse/trunk/s7.py


from struct import pack, unpack

import struct
import conpot.core as conpot_core
from conpot.helpers import str_to_bytes
from conpot.protocols.s7comm.exceptions import AssembleException, ParseException
import logging

logger = logging.getLogger(__name__)


# S7 packet
class S7(object):
    ssl_lists = {}

    def __init__(
        self,
        pdu_type=0,
        reserved=0,
        request_id=0,
        result_info=0,
        parameters="",
        data="",
    ):
        self.magic = 0x32
        self.pdu_type = pdu_type
        self.reserved = reserved
        self.request_id = request_id
        # sometimes "parameters" happen to be of type int, and not a byte string
        self.param_length = (
            len(parameters) if isinstance(parameters, bytes) else len(str(parameters))
        )
        self.data_length = len(data)
        self.result_info = result_info
        self.parameters = parameters
        self.data = data

        # param codes (http://www.bj-ig.de/147.html):
        # maps request types to methods
        self.param_mapping = {
            0x00: ("diagnostics", self.request_diagnostics),
            0x04: ("read", self.request_not_implemented),
            0x05: ("write", self.request_not_implemented),
            0x1A: ("request_download", self.request_not_implemented),
            0x1B: ("download_block", self.request_not_implemented),
            0x1C: ("end_download", self.request_not_implemented),
            0x1D: ("start_upload", self.request_not_implemented),
            0x1E: ("upload", self.request_not_implemented),
            0x1F: ("end_upload", self.request_not_implemented),
            0x28: ("insert_block", self.request_not_implemented),
            0x29: ("plc_stop", self.plc_stop_signal),
        }

        # maps valid pdu codes to name
        self.pdu_mapping = {
            0x01: set("request_pdu"),
            0x02: set("known_but_unindentified_pdu"),
            0x03: set("response_pdu"),
            0x07: set("system_status_list"),
        }

        self.data_bus = conpot_core.get_databus()

    def __len__(self):
        if self.pdu_type in (2, 3):
            return 12 + int(self.param_length) + int(self.data_length)
        else:
            return 10 + int(self.param_length) + int(self.data_length)

    def handle(self, current_client=None):
        if self.param in self.param_mapping:
            if self.param == 0x29:
                return self.param_mapping[self.param][1](current_client)
            # direct execution to the correct method based on the param
            return self.param_mapping[self.param][1]()

    def request_not_implemented(self):
        raise ParseException("s7comm", "request not implemented in honeypot yet.")

    def pack(self):
        if self.pdu_type not in self.pdu_mapping:
            raise AssembleException("s7comm", "invalid or unsupported pdu type")
        elif self.pdu_type in (2, 3):
            # type 2 and 3 feature an additional RESULT INFORMATION header
            return (
                pack(
                    "!BBHHHHH",
                    self.magic,
                    self.pdu_type,
                    self.reserved,
                    self.request_id,
                    self.param_length,
                    self.data_length,
                    self.result_info,
                )
                + str_to_bytes(self.parameters)
                + str_to_bytes(self.data)
            )
        else:
            return (
                pack(
                    "!BBHHHH",
                    self.magic,
                    self.pdu_type,
                    self.reserved,
                    self.request_id,
                    self.param_length,
                    self.data_length,
                )
                + str_to_bytes(self.parameters)
                + str_to_bytes(self.data)
            )

    def parse(self, packet):
        # dissect fixed header
        try:
            fixed_header = unpack("!BBHHHH", packet[:10])
        except struct.error:
            raise ParseException("s7comm", "malformed fixed packet header structure")

        self.magic = int(fixed_header[0])

        if self.magic != 0x32:
            raise ParseException(
                "s7comm",
                "bad magic number, expected 0x32 but got {0}.".format(self.magic),
            )

        self.pdu_type = fixed_header[1]
        self.reserved = fixed_header[2]
        self.request_id = fixed_header[3]
        self.param_length = fixed_header[4]
        self.data_length = fixed_header[5]

        # dissect variable header

        if self.pdu_type in (2, 3):
            # type 2 and 3 feature an additional RESULT INFORMATION header
            self.result_info = unpack("!H", packet[10:12])
            header_offset = 2
        else:
            header_offset = 0

        self.parameters = packet[
            10 + header_offset : 10 + header_offset + self.param_length
        ]
        self.data = packet[
            10
            + header_offset
            + self.param_length : 10
            + header_offset
            + self.param_length
            + self.data_length
        ]

        try:
            self.param = unpack("!B", self.parameters[:1])[0]
        except:
            raise ParseException("s7comm", "invalid packet")

        return self

    # SSL/SZL System Status List/Systemzustandsliste
    def plc_stop_signal(self, current_client):
        # This function gets executed after plc stop signal is received the function stops the server for a while and then restarts it
        logger.info("Stop signal recieved from {}".format(current_client))
        return str_to_bytes("0x00"), str_to_bytes("0x29")

    def request_diagnostics(self):
        # semi-check
        try:
            unpack("!BBBBBBBB", self.parameters[:8])
        except struct.error:
            raise ParseException("s7comm", "malformed SSL/SZL parameter structure")

        chunk = self.data
        chunk_id = 0

        while chunk:
            try:
                ssl_chunk_header = unpack("!BBH", chunk[:4])
            except struct.error:
                raise ParseException("s7comm", "malformed SSL/SZL data structure")

            # dissect data blocks

            # data_error_code = ssl_chunk_header[0]
            # data_data_type = ssl_chunk_header[1]
            data_next_bytes = ssl_chunk_header[2]
            data_ssl_id = ""
            data_ssl_index = ""
            # data_ssl_unknown = ""

            if data_next_bytes > 0:
                data_ssl_id = unpack("!H", chunk[4:6])[0]

            if data_next_bytes > 1:
                data_ssl_index = unpack("!H", chunk[6:8])[0]

            if data_next_bytes > 2:
                # data_ssl_unknown = chunk[8 : 4 + data_next_bytes]
                pass

            # map request ssl to method
            if hasattr(self, "request_ssl_{0}".format(data_ssl_id)):
                m = getattr(self, "request_ssl_{0}".format(data_ssl_id))
                _, params, data = m(data_ssl_index)
                return params, data

            chunk = chunk[4 + data_next_bytes :]
            chunk_id += 1

        return 0x00, 0x00

    # W#16#xy11 - module identification
    def request_ssl_17(self, data_ssl_index):
        # just for convenience
        current_ssl = S7.ssl_lists["W#16#xy11"]

        if data_ssl_index == 1:  # 0x0001 - component identification

            ssl_index_description = "Component identification"

            ssl_resp_data = pack(
                "!HHHHH20sHHH",
                17,  # 1  WORD   ( ID )
                data_ssl_index,  # 1  WORD   ( Index )
                28,  # 1  WORD   ( Length of payload after element count )
                0x01,  # 1  WORD   ( 1 element follows )
                data_ssl_index,  # 1  WORD   ( Data Index )
                str_to_bytes(self.data_bus.get_value(current_ssl["W#16#0001"])),
                # 10 WORDS  ( MLFB of component: 20 bytes => 19 chars + 1 blank (0x20) )
                0x0,  # 1  WORD   ( RESERVED )
                0x0,  # 1  WORD   ( Output state of component )
                0x0,
            )  # 1  WORD   ( RESERVED )

            ssl_resp_head = pack(
                "!BBH",
                0xFF,  # 1  BYTE   ( Data Error Code. 0xFF = OK )
                0x09,  # 1  BYTE   ( Data Type. 0x09 = Char/String )
                len(ssl_resp_data),
            )  # 1  WORD   ( Length of following data )

        elif data_ssl_index == 6:  # 0x0006 - hardware identification
            ssl_index_description = "Hardware identification"

            ssl_resp_data = pack(
                "!HHHHH20sHHH",
                17,  # 1  WORD   ( ID )
                data_ssl_index,  # 1  WORD   ( Index )
                28,  # 1  WORD   ( Length of payload after element count )
                0x01,  # 1  WORD   ( 1 element follows )
                data_ssl_index,  # 1  WORD   ( Data Index )
                str_to_bytes(self.data_bus.get_value(current_ssl["W#16#0006"])),
                # 10 WORDS  ( MLFB of component: 20 bytes => 19 chars + 1 blank (0x20) )
                0x0,  # 1  WORD   ( RESERVED )
                "V3",  # 1  WORD   ( 'V' and first digit of version number )
                0x539,
            )  # 1  WORD   ( remaining digits of version number )

            ssl_resp_head = pack(
                "!BBH",
                0xFF,  # 1  BYTE   ( Data Error Code. 0xFF = OK )
                0x09,  # 1  BYTE   ( Data Type. 0x09 = Char/String )
                len(ssl_resp_data),
            )  # 1  WORD   ( Length of following data )

        elif data_ssl_index == 7:  # 0x0007 - firmware identification
            ssl_index_description = "Firmware identification"

            ssl_resp_data = pack(
                "!HHHHH20sHHH",
                17,  # 1  WORD   ( ID )
                data_ssl_index,  # 1  WORD   ( Index )
                28,  # 1  WORD   ( Length of payload after element count )
                0x01,  # 1  WORD   ( 1 element follows )
                data_ssl_index,  # 1  WORD   ( Data Index )
                str_to_bytes(str(0x0)),  # 10 WORDS  ( RESERVED )
                0x0,  # 1  WORD   ( RESERVED )
                "V3",  # 1  WORD   ( 'V' and first digit of version number )
                0x53A,
            )  # 1  WORD   ( remaining digits of version number )

            ssl_resp_head = pack(
                "!BBH",
                0xFF,  # 1  BYTE   ( Data Error Code. 0xFF = OK )
                0x09,  # 1  BYTE   ( Data Type. 0x09 = Char/String )
                len(ssl_resp_data),
            )  # 1  WORD   ( Length of following data )
        else:
            ssl_index_description = "UNKNOWN / UNDEFINED / RESERVED {0}".format(
                hex(data_ssl_index)
            )
            ssl_resp_data = ""
            ssl_resp_head = ""

        ssl_resp_params = pack(
            "!BBBBBBBB",
            0x00,  # SSL DIAG
            0x01,  # unknown
            0x12,  # unknown
            0x08,  # bytes following
            0x12,  # unknown, maybe 0x11 + 1
            0x84,  # function; response to 0x44
            0x01,  # subfunction; readszl
            0x01,
        )  # sequence ( = sequence + 1 )
        return ssl_index_description, ssl_resp_params, ssl_resp_head + ssl_resp_data

    # W#16#011C
    def request_ssl_28(self, data_ssl_index):
        # just for convenience
        current_ssl = S7.ssl_lists["W#16#xy1C"]
        # initiate header for mass component block
        ssl_resp_data = pack(
            "!HHHH",
            28,  # 1  WORD   ( ID )
            data_ssl_index,  # 1  WORD   ( Index )
            34,  # 1  WORD   ( Length of payload after element count )
            0x08,
        )  # 1  WORD   ( 2 elements follow )

        # craft module data 0x0001 - automation system name
        ssl_resp_data += pack(
            "!H24s8s",
            0x01,  # 1  WORD   ( Data Index )
            str_to_bytes(
                self.data_bus.get_value(current_ssl["W#16#0001"])
            ),  # TODO: PADDING
            # 'System Name             ', # 12 WORDS  ( Name of automation system, padded with (0x00) )
            str_to_bytes(""),
        )  # 4  WORDS  ( RESERVED )

        # craft module data 0x0002 - component name
        ssl_resp_data += pack(
            "!H24s8s",
            0x02,  # 1  WORD   ( Data Index )
            str_to_bytes(self.data_bus.get_value(current_ssl["W#16#0002"])),
            # 12 WORDS  ( Name of component, padded with (0x00) )
            str_to_bytes(""),
        )  # 4  WORDS  ( RESERVED )

        # craft module data 0x0003 - plant identification
        ssl_resp_data += pack(
            "!H32s",
            0x03,  # 1  WORD   ( Data Index )
            str_to_bytes(self.data_bus.get_value(current_ssl["W#16#0003"])),
        )
        # 16 WORDS  ( Name of plant, padded with (0x00) )

        # craft module data 0x0004 - copyright
        ssl_resp_data += pack(
            "!H26s6s",
            0x04,  # 1  WORD   ( Data Index )
            str_to_bytes(
                self.data_bus.get_value(current_ssl["W#16#0004"])
            ),  # 13 WORDS  ( CONSTANT )
            str_to_bytes(""),
        )  # 3  WORDS  ( RESERVED )

        # craft module data 0x0005 - module serial number
        ssl_resp_data += pack(
            "!H24s8s",
            0x05,  # 1  WORD   ( Data Index )
            str_to_bytes(self.data_bus.get_value(current_ssl["W#16#0005"])),
            # 12 WORDS  ( Unique Serial Number )
            str_to_bytes(""),
        )  # 4  WORDS  ( RESERVED )

        # craft module data 0x0007 - module type name
        ssl_resp_data += pack(
            "!H32s",
            0x07,  # 1  WORD   ( Data Index )
            str_to_bytes(self.data_bus.get_value(current_ssl["W#16#0007"])),
        )
        # 16 WORDS  ( CPU type name, padded wit (0x00) )

        # craft module data 0x000a - OEM ID of module
        ssl_resp_data += pack(
            "!H20s6s2s4s",
            0x0A,  # 1  WORD   ( Data Index )
            str_to_bytes(self.data_bus.get_value(current_ssl["W#16#000A"])),
            # 10 WORDS  ( OEM-Copyright Text, padded with (0x00) )
            str_to_bytes(
                ""
            ),  # 3  WORDS  ( OEM Copyright Text padding to 26 characters )
            str_to_bytes(""),  # 1  WORD   ( OEM ID provided by Siemens )
            str_to_bytes(""),
        )  # 2  WORDS  ( OEM user defined ID )

        # craft module data 0x000b - location
        ssl_resp_data += pack(
            "!H32s",
            0x0B,  # 1  WORD   ( Data Index )
            str_to_bytes(self.data_bus.get_value(current_ssl["W#16#000B"])),
        )
        # 16 WORDS  ( Location String, padded with (0x00) )

        # craft leading response header
        ssl_resp_head = pack(
            "!BBH",
            0xFF,  # 1  BYTE   ( Data Error Code. 0xFF = OK )
            0x09,  # 1  BYTE   ( Data Type. 0x09 = Char/String )
            len(ssl_resp_data),
        )  # 1  WORD   ( Length of following data )

        ssl_resp_packet = ssl_resp_head + ssl_resp_data
        ssl_resp_params = pack(
            "!BBBBBBBB",
            0x00,  # SSL DIAG
            0x01,  # unknown
            0x12,  # unknown
            0x08,  # bytes following
            0x12,  # unknown, maybe 0x11 + 1
            0x84,  # function; response to 0x44
            0x01,  # subfunction; readszl
            0x01,
        )  # sequence ( = sequence + 1 )

        return "", ssl_resp_params, ssl_resp_packet
