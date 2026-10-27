# References: S7_300-400_full_reference_handbook_ENGLISH.pdf
#             http://www.bj-ig.de/147.html
#             https://code.google.com/p/plcscan/source/browse/trunk/s7.py


from struct import pack, unpack

import struct
import conpot.core as conpot_core
from conpot.protocols.s7comm.exceptions import AssembleException, ParseException
from conpot.protocols.s7comm.s7_memory_map import S7AddressError, S7MemoryMap
from conpot.utils.networking import str_to_bytes
import logging

logger = logging.getLogger(__name__)

# PI-Service object for CPU control, and the start modes accepted in the data.
_CPU_CONTROL_OBJECT = b"P_PROGRAM"
_CPU_START_MODES = frozenset(
    {
        b"WARM",
        b"COLD",
        b"HOT",
        b"WARM_START",
        b"COLD_START",
        b"HOT_START",
    }
)
S7_ITEM_OK = 0xFF
S7_ITEM_ADDRESS_ERROR = 0x05
S7_ITEM_NOT_AVAILABLE = 0x0A

# Request-item word lengths (any-type) → bytes per element
_WORD_LEN_BYTES = {
    0x01: 0,  # BIT — handled specially
    0x02: 1,  # BYTE
    0x03: 1,  # CHAR
    0x04: 2,  # WORD
    0x05: 2,  # INT
    0x06: 4,  # DWORD
    0x07: 4,  # DINT
    0x08: 4,  # REAL
}


def _item_byte_length(word_len, count):
    if word_len == 0x01:
        return (count + 7) // 8
    unit = _WORD_LEN_BYTES.get(word_len)
    if unit is None:
        return count
    return count * unit


# SZL 0x0011 returns these records: module, basic hardware, basic firmware,
# and the boot loader record (0x0081) when the template configures one.
_MODULE_IDENTIFICATION_INDEXES = (1, 6, 7, 0x81)

# BGTyp (module type class) reported by S7-300 CPUs for records 1, 6 and 7.
_CPU_MODULE_TYPE_CLASS = 0x00C0


def _szl_response_params(sequence=0x01):
    """Userdata parameter block for a Read SZL response (12 bytes).

    The length byte announces 8 trailing bytes, so the data unit reference,
    last-data-unit flag and error code must be present; clients such as
    nmap's s7-info read the SZL data at offsets that assume them.
    """
    return pack(
        "!BBBBBBBBBBH",
        0x00,  # parameter head
        0x01,
        0x12,
        0x08,  # length of the parameters that follow
        0x12,  # method: response
        0x84,  # type 8 (response) | function group 4 (SZL)
        0x01,  # subfunction: read SZL
        sequence,  # sequence number
        0x00,  # data unit reference number
        0x00,  # last data unit (0x00 = yes)
        0x0000,  # error code
    )


def _blank_padded(value, size):
    """Pad or truncate to a fixed-width field using blanks, as Siemens does."""
    return value[:size].ljust(size, b" ")


def _version_numbers(text, count):
    """Pull ``count`` dotted numbers (0-255) from text such as '3.2.8'."""
    parts = text.split(".")
    numbers = []
    for part in parts[:count]:
        try:
            numbers.append(max(0, min(255, int(part))))
        except ValueError:
            numbers.append(0)
    numbers += [0] * (count - len(numbers))
    return numbers


def _parse_firmware_version(text, default_prefix="V"):
    """Turn 'V3.2.8' into (ord('V'), 3, 2, 8).

    The leading letter (e.g. 'V' for firmware, 'A' for the boot loader)
    goes in the high byte of Ausbg1; the numbers are binary. A missing
    letter falls back to ``default_prefix``.
    """
    if isinstance(text, bytes):
        text = text.decode("ascii", "ignore")
    text = str(text).strip()
    prefix = default_prefix
    if text and text[0].isalpha():
        prefix, text = text[0], text[1:]
    return (ord(prefix), *_version_numbers(text, 3))


def _parse_hardware_version(text):
    """Turn '3.1' into the two Ausbg words (3, 1) of a module record."""
    if isinstance(text, bytes):
        text = text.decode("ascii", "ignore")
    text = str(text).strip().lstrip("Vv")
    if not text:
        return 0, 0
    return tuple(_version_numbers(text, 2))


def _length_prefixed_strings(blob):
    """Pull ASCII strings stored as a length byte plus that many characters."""
    found = []
    index = 0
    while index < len(blob):
        length = blob[index]
        end = index + 1 + length
        if length and end <= len(blob):
            chunk = blob[index + 1 : end]
            if all(32 <= byte <= 126 for byte in chunk):
                found.append(chunk)
                index = end
                continue
        index += 1
    return found


# S7 packet
class S7(object):
    ssl_lists = {}
    # Optional per-item databus keys for version words, keyed like ssl_lists
    ssl_versions = {}
    memory_map = S7MemoryMap()
    # Emulated CPU mode. Never stop the listening task; a stop probe must
    # not take the honeypot down.
    cpu_running = True

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
        # sometimes "parameters"/"data" happen to be of type int, and not a byte string
        self.param_length = (
            len(parameters) if isinstance(parameters, bytes) else len(str(parameters))
        )
        self.data_length = (
            len(data) if isinstance(data, (bytes, str)) else len(str(data))
        )
        self.result_info = result_info
        self.parameters = parameters
        self.data = data
        self._session = None

        # param codes (http://www.bj-ig.de/147.html):
        # maps request types to methods
        self.param_mapping = {
            0x00: ("diagnostics", self.request_diagnostics),
            0x04: ("read", self.request_read_var),
            0x05: ("write", self.request_write_var),
            0x1A: ("request_download", self.request_not_implemented),
            0x1B: ("download_block", self.request_not_implemented),
            0x1C: ("end_download", self.request_not_implemented),
            0x1D: ("start_upload", self.request_not_implemented),
            0x1E: ("upload", self.request_not_implemented),
            0x1F: ("end_upload", self.request_not_implemented),
            0x28: ("plc_control", self.plc_control),
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

    def handle(self, current_client=None, session=None):
        self._session = session
        if self.param in self.param_mapping:
            if self.param == 0x29:
                return self.param_mapping[self.param][1](current_client)
            # direct execution to the correct method based on the param
            return self.param_mapping[self.param][1]()

    def request_not_implemented(self):
        raise ParseException("s7comm", "request not implemented in honeypot yet.")

    def _parse_request_items(self):
        """Parse any-type (0x10) request items from the parameter section."""
        params = self.parameters
        if not isinstance(params, bytes):
            params = str_to_bytes(params)
        if len(params) < 2:
            raise ParseException("s7comm", "truncated read/write parameters")
        item_count = params[1]
        offset = 2
        items = []
        for _ in range(item_count):
            if offset + 2 > len(params):
                raise ParseException("s7comm", "truncated request item")
            spec = params[offset]
            rest_len = params[offset + 1]
            item_end = offset + 2 + rest_len
            if spec != 0x12 or item_end > len(params):
                raise ParseException("s7comm", "malformed request item")
            body = params[offset + 2 : item_end]
            if len(body) < 10 or body[0] != 0x10:
                raise ParseException(
                    "s7comm", "unsupported or malformed addressing mode"
                )
            word_len = body[1]
            count = unpack("!H", body[2:4])[0]
            db_number = unpack("!H", body[4:6])[0]
            area = body[6]
            bit_addr = (body[7] << 16) | (body[8] << 8) | body[9]
            items.append(
                {
                    "word_len": word_len,
                    "count": count,
                    "db_number": db_number,
                    "area": area,
                    "bit_addr": bit_addr,
                    "byte_offset": bit_addr >> 3,
                }
            )
            offset = item_end
        return items

    def _parse_write_data_items(self, item_count):
        """Parse write request data items; lengths are even-padded between items."""
        raw = self.data
        if not isinstance(raw, bytes):
            raw = str_to_bytes(raw)
        offset = 0
        payloads = []
        for i in range(item_count):
            if offset + 4 > len(raw):
                raise ParseException("s7comm", "truncated write data item")
            # return_code (ignored on request), transport_size, length
            transport = raw[offset + 1]
            length_field = unpack("!H", raw[offset + 2 : offset + 4])[0]
            # Transport 0x03 BIT / 0x04 BYTE-oriented → length in bits; 0x09 → bytes
            if transport in (0x03, 0x04, 0x05, 0x06, 0x07):
                byte_len = (length_field + 7) // 8
            else:
                byte_len = length_field
            data_start = offset + 4
            data_end = data_start + byte_len
            if data_end > len(raw):
                raise ParseException("s7comm", "truncated write data payload")
            payloads.append(raw[data_start:data_end])
            offset = data_end
            # Pad to even boundary when another item follows
            if i < item_count - 1 and (byte_len % 2) == 1:
                offset += 1
        return payloads

    def _log_var_event(self, event_type, item, length, success):
        if self._session is None:
            return
        self._session.log_event(
            event_type=event_type,
            area=item["area"],
            db=item["db_number"],
            offset=item["byte_offset"],
            length=length,
            success=success,
        )

    def request_read_var(self):
        """Handle Read VAR (0x04); returns Ack-Data parameters and data."""
        items = self._parse_request_items()
        response_data = b""
        for index, item in enumerate(items):
            byte_len = _item_byte_length(item["word_len"], item["count"])
            try:
                raw = S7.memory_map.read(
                    item["area"], item["db_number"], item["byte_offset"], byte_len
                )
                # BYTE-oriented transport with length in bits (common for BYTE/WORD)
                chunk = pack("!BBH", S7_ITEM_OK, 0x04, byte_len * 8) + raw
                self._log_var_event("READ_VAR", item, byte_len, True)
            except S7AddressError:
                chunk = pack("!B", S7_ITEM_NOT_AVAILABLE)
                self._log_var_event("READ_VAR", item, byte_len, False)
            # Even padding between data items
            if index < len(items) - 1 and (len(chunk) % 2) == 1:
                chunk += b"\x00"
            response_data += chunk
        response_params = pack("!BB", 0x04, len(items))
        return response_params, response_data

    def request_write_var(self):
        """Handle Write VAR (0x05); returns Ack-Data parameters and per-item status."""
        items = self._parse_request_items()
        payloads = self._parse_write_data_items(len(items))
        status = b""
        for item, payload in zip(items, payloads):
            expected = _item_byte_length(item["word_len"], item["count"])
            if expected and len(payload) != expected:
                # Allow payload length from transport header to drive the write size
                pass
            try:
                S7.memory_map.write(
                    item["area"], item["db_number"], item["byte_offset"], payload
                )
                status += pack("!B", S7_ITEM_OK)
                self._log_var_event("WRITE_VAR", item, len(payload), True)
            except S7AddressError:
                status += pack("!B", S7_ITEM_ADDRESS_ERROR)
                self._log_var_event("WRITE_VAR", item, len(payload), False)
        response_params = pack("!BB", 0x05, len(items))
        return response_params, status

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
        logger.info("Stop signal received from %s", current_client)
        S7.cpu_running = False
        if self._session is not None:
            self._session.log_event(event_type="PLC_STOP")
        return b"\x29", b""

    def plc_control(self):
        """PI-Service (0x28). Only warm/cold/hot start is emulated."""
        params = self.parameters
        data = self.data
        if not isinstance(params, bytes):
            params = str_to_bytes(params)
        if not isinstance(data, bytes):
            data = str_to_bytes(data)
        param_strings = _length_prefixed_strings(params)
        data_strings = _length_prefixed_strings(data)
        if _CPU_CONTROL_OBJECT in param_strings and any(
            mode in _CPU_START_MODES for mode in data_strings
        ):
            S7.cpu_running = True
            if self._session is not None:
                self._session.log_event(event_type="PLC_START")
            return b"\x28", b""
        return self.request_not_implemented()

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

        # No matching SSL/SZL handler — return empty byte payloads (not ints).
        # Returning ints used to crash S7.__init__ via len(data).
        return b"", b""

    # W#16#xy11 - module identification
    def _module_identification_record(self, data_ssl_index):
        """Build one 28-byte SZL 0xxy11 record, or None for unsupported indexes.

        Record layout: Index (WORD), MLFB (20 chars, blank padded),
        BGTyp (WORD), Ausbg1 (WORD), Ausbg2 (WORD). Records 1 and 6 carry
        an order number and two hardware version words; records 7 (firmware)
        and 0x81 (boot loader) carry a letter plus binary major/minor/patch.
        Layout and values follow a capture of a CPU 315-2 PN/DP.
        """
        current_ssl = S7.ssl_lists.get("W#16#xy11", {})
        versions = S7.ssl_versions.get("W#16#xy11", {})
        item_id = "W#16#{0:04X}".format(data_ssl_index)

        if data_ssl_index in (1, 6):
            # 1: module identification, 6: basic hardware identification
            mlfb = self._databus_text(current_ssl.get(item_id))
            hw_major, hw_minor = _parse_hardware_version(
                self._databus_text(versions.get(item_id))
            )
            return pack(
                "!H20sHHH",
                data_ssl_index,
                _blank_padded(mlfb, 20),
                _CPU_MODULE_TYPE_CLASS,  # BGTyp
                hw_major,  # Ausbg1
                hw_minor,  # Ausbg2
            )
        if data_ssl_index == 7 or (data_ssl_index == 0x81 and item_id in current_ssl):
            # 7: basic firmware, 0x81: boot loader; version in Ausbg1/2
            if data_ssl_index == 7:
                name, module_class, default_prefix = b"", _CPU_MODULE_TYPE_CLASS, "V"
            else:
                name, module_class, default_prefix = b"Boot Loader", 0x0000, "A"
            prefix, major, minor, patch = _parse_firmware_version(
                self._databus_text(current_ssl.get(item_id)), default_prefix
            )
            return pack(
                "!H20sHBBBB",
                data_ssl_index,
                _blank_padded(name, 20),
                module_class,  # BGTyp
                prefix,
                major,
                minor,
                patch,
            )
        return None

    def _databus_text(self, key):
        if not key:
            return b""
        try:
            return str_to_bytes(self.data_bus.get_value(key))
        except AssertionError, UnicodeEncodeError:
            logger.warning("S7 SZL databus key %r is missing or not ASCII", key)
            return b""

    def _module_identification_response(self, szl_id, data_ssl_index, indexes):
        records = b""
        for index in indexes:
            record = self._module_identification_record(index)
            if record is not None:
                records += record
        ssl_resp_data = (
            pack(
                "!HHHH",
                szl_id,  # SZL-ID as requested
                data_ssl_index,  # Index as requested
                28,  # LENTHDR: bytes per record
                len(records) // 28,  # N_DR: number of records
            )
            + records
        )
        ssl_resp_head = pack(
            "!BBH",
            0xFF,  # Data Error Code. 0xFF = OK
            0x09,  # Transport size. 0x09 = octet string
            len(ssl_resp_data),
        )
        return ssl_resp_head + ssl_resp_data

    # W#16#0011 - all module identification records (index is ignored)
    def request_ssl_17(self, data_ssl_index):
        data = self._module_identification_response(
            0x0011, data_ssl_index, _MODULE_IDENTIFICATION_INDEXES
        )
        return "Module identification", _szl_response_params(), data

    # W#16#0111 - a single module identification record selected by index
    def request_ssl_273(self, data_ssl_index):
        data = self._module_identification_response(
            0x0111, data_ssl_index, (data_ssl_index,)
        )
        return "Module identification", _szl_response_params(), data

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
        ssl_resp_params = _szl_response_params()

        return "", ssl_resp_params, ssl_resp_packet
