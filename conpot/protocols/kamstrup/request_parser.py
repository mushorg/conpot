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
import binascii

import crc16
import kamstrup_constants


logger = logging.getLogger(__name__)


class KamstrupRequestParser(object):
    def __init__(self):
        self.bytes = []
        self.parsing = False
        self.data_escaped = False
        self.done = False
        self.request_map = {KamstrupRequestGetRegisters.command_byte: KamstrupRequestGetRegisters}

    def add_byte(self, byte):
        self.bytes.append(ord(byte))

    def get_request(self):
        bytes_len = len(self.bytes)
        position = 0
        while position < bytes_len:
            d = self.bytes[position]
            if not self.parsing and d != kamstrup_constants.REQUEST_MAGIC:
                logger.debug('Skipping byte, expected kamstrup request magic but got: {0}'
                             .format(hex(d)))
                del self.bytes[position]
                bytes_len -= 1
                continue
            else:
                self.parsing = True

                escape_escape_byte = False
                if self.data_escaped:
                    self.bytes[position] ^= 0xff
                    if d is kamstrup_constants.EOT_MAGIC:
                        escape_escape_byte = True
                    self.data_escaped = False
                elif d is kamstrup_constants.ESCAPE:
                    self.data_escaped = True
                    del self.bytes[position]
                    bytes_len -= 1
                    continue

                assert self.data_escaped is False

                if d is kamstrup_constants.EOT_MAGIC and not escape_escape_byte:
                    if not self.valid_crc(self.bytes[1:position]):
                        self.parsing = False
                        del self.bytes[0:position]
                        logger.warning('CRC check failed for request.')
                    # now we expect (0x80, 0x3f, 0x10) =>
                    # (request magic, communication address, command byte)
                    comm_address = self.bytes[1]
                    command_byte = self.bytes[2]
                    if self.bytes[2] in self.request_map:
                        result = self.request_map[command_byte](comm_address, command_byte, self.bytes[3:-3])
                        del self.bytes[:position + 1]
                    else:
                        result = KamstrupRequestUnknown(comm_address, command_byte, self.bytes[3:-3])
                        del self.bytes[:position + 1]
                    return result
                position += 1

    def valid_crc(self, message):
        supplied_crc = message[-2] * 256 + message[-1]
        calculated_crc = crc16.crc16xmodem(''.join([chr(item) for item in message[:-2]]))
        return supplied_crc == calculated_crc


class KamstrupProtocolBase(object):
    def __init__(self, communication_address):
        self.communication_address = communication_address


class KamstrupRequestBase(KamstrupProtocolBase):
    def __init__(self, communication_address, command, message_bytes):
        super(KamstrupRequestBase, self).__init__(communication_address)
        self.command = command
        self.message_bytes = message_bytes
        logger.debug('Request package created with bytes: {0}'.format(self.message_bytes))

    def __str__(self):
        return 'Comm address: {0}, Command: {1}, Message: {2}'.format(hex(self.communication_address),
                                                                      hex(self.command),
                                                                      binascii.hexlify(self.message_bytes))


# Valid but request command unknown
class KamstrupRequestUnknown(KamstrupRequestBase):
    def __init__(self, communication_address, command_byte, message_bytes):
        super(KamstrupRequestGetRegisters, self).__init__(communication_address,
                                                          command_byte, message_bytes)
        logger.warning('Unknown Kamstrup request: {0}'.format(self))


class KamstrupRequestGetRegisters(KamstrupRequestBase):
    command_byte = 0x10

    def __init__(self, communication_address, command_byte, message_bytes):
        assert command_byte is command_byte
        super(KamstrupRequestGetRegisters, self).__init__(communication_address,
                                                          KamstrupRequestGetRegisters.command_byte, message_bytes)
        self.registers = []
        self._parse_register_bytes()
        logger.debug('Request for registers: {0}'.format(str(self.registers).strip('[]')))

    def _parse_register_bytes(self):
        register_count = self.message_bytes[0]
        if len(self.message_bytes[1:] * 2) < register_count:
            raise Exception('Invalid register count in register request')
        for count in xrange(register_count):
            register = self.message_bytes[1 + count * 2] * 256 + self.message_bytes[2 + count * 2]
            self.registers.append(register)
