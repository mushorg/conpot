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
from conpot.helpers import chr_py3
from crc16.crc16pure import crc16xmodem
from . import kamstrup_constants
import conpot.core as conpot_core


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
        logger.info(
            "Kamstrup request package created with bytes: %s", self.message_bytes
        )

    def __str__(self):
        return "Comm address: {0}, Command: {1}, Message: {2}".format(
            hex(self.communication_address),
            hex(self.command),
            binascii.hexlify(bytearray(self.message_bytes)),
        )


# Valid but request command unknown
class KamstrupRequestUnknown(KamstrupRequestBase):
    def __init__(self, communication_address, command_byte, message_bytes):
        super(KamstrupRequestUnknown, self).__init__(
            communication_address, command_byte, message_bytes
        )
        logger.warning("Unknown Kamstrup request: %s", self)


class KamstrupRequestGetRegisters(KamstrupRequestBase):
    command_byte = 0x10

    def __init__(self, communication_address, command_byte, message_bytes):
        assert command_byte is command_byte
        super(KamstrupRequestGetRegisters, self).__init__(
            communication_address,
            KamstrupRequestGetRegisters.command_byte,
            message_bytes,
        )
        self.registers = []
        self._parse_register_bytes()
        logger.debug(
            "Kamstrup request for registers: %s", str(self.registers).strip("[]")
        )

    def _parse_register_bytes(self):
        register_count = self.message_bytes[0]
        if len(self.message_bytes[1:]) * 2 < register_count:
            raise Exception("Invalid register count in register request")
        for count in range(register_count):
            register = (
                self.message_bytes[1 + count * 2] * 256
                + self.message_bytes[2 + count * 2]
            )
            self.registers.append(register)


# ############ RESPONSE MESSAGES ##############
class KamstrupResponseBase(KamstrupProtocolBase):
    def __init__(self, communication_address):
        super(KamstrupResponseBase, self).__init__(communication_address)

    def serialize(self, message):
        final_message = list()

        # prefix message
        final_message.append(kamstrup_constants.RESPONSE_MAGIC)
        final_message.append(self.communication_address)

        # add the original content
        for c in message:
            final_message.append(c)

        # generate and append checksum
        crc = crc16xmodem(b"".join([chr_py3(item) for item in final_message[1:]]))
        final_message.append(crc >> 8)
        final_message.append(crc & 0xFF)

        # trailing magic
        final_message.append(kamstrup_constants.EOT_MAGIC)

        escaped_message = self.escape(final_message)
        return escaped_message

    # escape everything but leading and trailing magic
    @classmethod
    def escape(cls, message):
        escaped_list = list()
        escaped_list.append(message[0])
        for c in message[1:-1]:
            if c in kamstrup_constants.NEED_ESCAPE:
                escaped_list.append(kamstrup_constants.ESCAPE)
                escaped_list.append(c ^ 0xFF)
            else:
                escaped_list.append(c)
        escaped_list.append(message[-1])
        return escaped_list


class KamstrupResponseRegister(KamstrupResponseBase):
    def __init__(self, communication_address):
        super(KamstrupResponseRegister, self).__init__(communication_address)
        self.registers = []

    def add_register(self, register):
        self.registers.append(register)

    def serialize(self, message=None):
        if not message:
            message = []
        message.append(0x10)

        for register in self.registers:
            # each register must be packed: (ushort registerId, byte units, byte length, byte unknown)
            # and the following $length payload with the register value
            message.append(register.name >> 8)
            message.append(register.name & 0xFF)
            message.append(register.units)
            message.append(register.length)
            # mystery byte
            message.append(register.unknown)

            low_endian_value_packed = []
            register_value = conpot_core.get_databus().get_value(register.databus_key)
            for _ in range(register.length):
                # get least significant
                low_endian_value_packed.append(register_value & 0xFF)
                register_value >>= 8

            # reverse to get pack high endian
            for b in reversed(low_endian_value_packed):
                message.append(b)

        # add leading/trailing magic and escape as appropriate
        serialized_message = super(KamstrupResponseRegister, self).serialize(message)
        return bytearray(serialized_message)
