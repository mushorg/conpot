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
from .messages import KamstrupRequestGetRegisters, KamstrupRequestUnknown

logger = logging.getLogger(__name__)


class KamstrupRequestParser(object):
    def __init__(self):
        self.bytes = list()
        self.parsing = False
        self.data_escaped = False
        self.done = False
        self.request_map = {
            KamstrupRequestGetRegisters.command_byte: KamstrupRequestGetRegisters
        }

    def add_byte(self, byte):
        self.bytes.append(ord(byte))

    def get_request(self):
        bytes_len = len(self.bytes)
        position = 0
        while position < bytes_len:
            d = self.bytes[position]
            if not self.parsing and d != kamstrup_constants.REQUEST_MAGIC:
                logger.info(
                    "Kamstrup skipping byte, expected kamstrup_meter request magic but got: {0}".format(
                        hex(d)
                    )
                )
                del self.bytes[position]
                bytes_len -= 1
                continue
            else:
                self.parsing = True

                escape_escape_byte = False
                if self.data_escaped:
                    self.bytes[position] ^= 0xFF
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
                        logger.warning("Kamstrup CRC check failed for request.")
                    # now we expect (0x80, 0x3f, 0x10) =>
                    # (request magic, communication address, command byte)
                    comm_address = self.bytes[1]
                    command_byte = self.bytes[2]
                    if self.bytes[2] in self.request_map:
                        result = self.request_map[command_byte](
                            comm_address, command_byte, self.bytes[3:-3]
                        )
                        del self.bytes[: position + 1]
                    else:
                        result = KamstrupRequestUnknown(
                            comm_address, command_byte, self.bytes[3:-3]
                        )
                        del self.bytes[: position + 1]
                    return result
                position += 1

    @classmethod
    def valid_crc(cls, message):
        supplied_crc = message[-2] * 256 + message[-1]
        calculated_crc = crc16xmodem(b"".join([chr_py3(item) for item in message[:-2]]))
        return supplied_crc == calculated_crc
