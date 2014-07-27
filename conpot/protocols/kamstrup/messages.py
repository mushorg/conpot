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
import struct

import crc16
import kamstrup_constants


logger = logging.getLogger(__name__)


class KamstrupProtocolBase(object):
    def __init__(self, communication_address):
        self.communication_address = communication_address


# ############ REQUEST MESSAGES ##############
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


############# RESPONSE MESSAGES ##############
class KamstrupResponseRegister(KamstrupProtocolBase):
    def __init__(self, communication_address):
        super(KamstrupResponseRegister, self).__init__(communication_address)
        self.registers = []

    def add_register(self, register, value, units, unknown, length):
        # TODO: create a struct instead of tuple, makes the code more readable
        self.registers.append((register, value, units, unknown, length))

    def serialize(self):
        message = []
        message.append(kamstrup_constants.RESPONSE_MAGIC)
        message.append(self.communication_address)
        message.append(0x10)

        for register in self.registers:
            # (ushort registerId, byte units, byte length, byte unknown)
            # register number
            message.append(register[0] >> 8)
            message.append(register[0] & 0xff)
            # units
            message.append(register[2])
            # length
            message.append(register[4])
            # mystery byte
            message.append(register[3])

            low_endian_value_packed = []
            v = register[1]
            for _ in range(register[4]):
                # get least significant
                low_endian_value_packed.append(v & 0xff)
                v = v >> 8

            # reverse to get pack high endian
            for b in reversed(low_endian_value_packed):
                message.append(b)

            crc = crc16.crc16xmodem(''.join([chr(item) for item in message[1:]]))
            message.append(crc >> 8)
            message.append(crc & 0xff)

        message.append(kamstrup_constants.EOT_MAGIC)
        return bytearray(message)