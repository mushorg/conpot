# Copyright (C) 2014  Johnny Vestergaard <jkv@unixcluster.dk>
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

import logging
from conpot.helpers import chr_py3
from crc16.crc16pure import crc16xmodem
from . import kamstrup_constants


logger = logging.getLogger(__name__)


class Decoder382(object):

    REGISTERS = {
        0x01: "Energy in",
        0x02: "Energy out",
        0x0D: "Energy in hi-res",
        0x0E: "Energy out hi-res",
        0x33: "Meter number",  # user configurable
        0x3E9: "Meter serialnumber",  # not user configurable
        0x466: "Meter type",
        0x417: "Time zone",  # how is this represented?
        0x4F7: "KMP address",
        0x4F4: "M-bus address",
        0x041E: "Voltage p1",
        0x041F: "Voltage p2",
        0x0420: "Voltage p3",
        0x0434: "Current p1",
        0x0435: "Current p2",
        0x0436: "Current p3",
        0x0438: "Power p1",
        0x0439: "Power p2",
        0x043A: "Power p3",
        0x178A: "Firmware revision A",  # not too sure on how to parse there.
        0x178F: "Firmware revision B",
    }

    def __init__(self):
        self.in_data = []
        self.in_parsing = False
        self.in_data_escaped = False
        self.out_data = []
        self.out_parsing = False
        self.out_data_escaped = False
        self.request_command_map = {
            0x01: self._decode_cmd_get_type,
            0x10: self._decode_cmd_get_register,
            0x92: self._decode_cmd_login,
        }

        self.response_map = {0x10: self._decode_cmd_return_register}

    def decode_in(self, data):
        for d in data:
            d = ord(d)
            if not self.in_parsing and d != kamstrup_constants.REQUEST_MAGIC:
                logger.info(
                    "No kamstrup_meter request magic received, got: %s",
                    d.encode("hex-codec"),
                )
            else:
                self.in_parsing = True

                escape_escape_byte = False
                if self.in_data_escaped:
                    d ^= 0xFF
                    if d is kamstrup_constants.EOT_MAGIC:
                        escape_escape_byte = True
                    self.in_data_escaped = False
                elif d is kamstrup_constants.ESCAPE:
                    self.in_data_escaped = True
                    continue

                assert self.in_data_escaped is False

                if d is kamstrup_constants.EOT_MAGIC and not escape_escape_byte:
                    if not self.valid_crc(self.in_data[1:]):
                        self.in_parsing = False
                        self.in_data = []
                        # TODO: Log discarded bytes?
                        return "Request discarded due to invalid CRC."
                    # now we expect (0x80, 0x3f, 0x10) =>
                    # (request magic, communication address, command byte)
                    comm_address = self.in_data[1]
                    if self.in_data[2] in self.request_command_map:
                        result = self.request_command_map[
                            self.in_data[2]
                        ]() + " [{0}]".format(hex(comm_address))
                    else:
                        result = "Unknown request command: {0}".format(self.in_data[2])
                    self.in_data = []
                    return result
                else:
                    self.in_data.append(d)

    def decode_out(self, data):
        for d in data:
            d = ord(d)
            if not self.out_parsing and d != kamstrup_constants.RESPONSE_MAGIC:
                logger.info(
                    "Kamstrup: Expected response magic but got got: %s",
                    d.encode("hex-codec"),
                )
            else:
                self.out_parsing = True

                escape_escape_byte = False
                if self.out_data_escaped:
                    d ^= 0xFF
                    if d is kamstrup_constants.EOT_MAGIC:
                        escape_escape_byte = True
                    self.out_data_escaped = False
                elif d is kamstrup_constants.ESCAPE:
                    self.out_data_escaped = True
                    continue

                assert self.out_data_escaped is False

                if d is kamstrup_constants.EOT_MAGIC and not escape_escape_byte:
                    if not self.valid_crc(self.out_data[1:]):
                        self.out_parsing = False
                        self.out_data = []
                        # TODO: Log discarded bytes?
                        return "Response discarded due to invalid CRC."
                    comm_address = self.out_data[1]
                    if self.out_data[2] in self.response_map:
                        result = self.response_map[
                            self.out_data[2]
                        ]() + " [{0}]".format(hex(comm_address))
                    else:
                        result = "Unknown response command: {0}".format(
                            self.out_data[2]
                        )

                    self.out_data = []
                    return result
                else:
                    self.out_data.append(d)

    def _decode_cmd_get_register(self):
        assert self.in_data[2] == 0x10
        # cmd = self.in_data[2]
        register_count = self.in_data[3]
        message = "Request for {0} register(s): ".format(register_count)
        if len(self.in_data[2:]) < register_count:
            return "Invalid message, register count was too high"
        for count in range(register_count):
            register = self.in_data[4 + count * 2] * 256 + self.in_data[5 + count * 2]
            if register in Decoder382.REGISTERS:
                message += "{0} ({1})".format(register, Decoder382.REGISTERS[register])
            else:
                message += "Unknown ({0})".format(register)
            if count + 1 < register_count:
                message += ", "
        return message

    def _decode_cmd_return_register(self):
        assert self.out_data[2] == 0x10
        # skip command bytes and trailing checksum
        msg = self.out_data[3:-2]

        return_value = "Register reponse: "
        if len(msg) == 0:
            return_value += "Invalid register"
        else:
            i = 0
            while i < len(msg):
                # Header is (ushort registerId, byte units, byte length, byte unknown)
                register = msg[i] * 256 + msg[i + 1]
                # unknown_byte_A = msg[i + 2]
                length = msg[i + 3]
                # unknown_byte_B = msg[i + 2]

                # Payload
                register_value = 0
                for p in range(length):
                    register_value += msg[i + 5 + p] << (8 * ((length - p) - 1))
                if register in Decoder382.REGISTERS:
                    return_value += "{0}({1}):{2}, ".format(
                        register, Decoder382.REGISTERS[register], register_value
                    )
                else:
                    return_value += "{0}:{1}, ".format(register, register_value)
                i += 5 + length

        return return_value

    # meter type
    def _decode_cmd_get_type(self):
        assert self.in_data[2] == 0x01
        return "Request for GetType"

    def _decode_cmd_login(self):
        assert self.in_data[2] == 0x92
        pin_code = self.in_data[3] * 256 + self.in_data[4]
        return "Login command with pin_code: {0}".format(pin_code)

    # supplied message should be stripped of leading and trailing magic
    @classmethod
    def valid_crc(cls, message):
        supplied_crc = message[-2] * 256 + message[-1]
        calculated_crc = crc16xmodem(b"".join([chr_py3(item) for item in message[:-2]]))
        return supplied_crc == calculated_crc

    @classmethod
    def _decode_response(cls):
        return "Decoding of this response has not been implemented yet."
