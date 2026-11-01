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
from collections import deque

from crc16.crc16pure import crc16xmodem

from . import kamstrup_constants
from .messages import (
    KamstrupRequestGetRegisters,
    KamstrupRequestLogin,
    KamstrupRequestUnknown,
)

logger = logging.getLogger(__name__)

# A register request carries a one-byte count and at most 255 two-byte
# register IDs. Include the address, command, CRC, and frame markers, then
# allow every encoded body byte to require an escape byte.
_MAX_DECODED_REQUEST_SIZE = 1 + 1 + 1 + (2 * 255) + 2
MAX_FRAME_SIZE = 2 + (2 * _MAX_DECODED_REQUEST_SIZE)


class RequestFrameTooLarge(ValueError):
    """Raised when a Kamstrup request exceeds the encoded frame limit."""


class KamstrupRequestParser(object):
    def __init__(self):
        # ``bytes`` retains the decoded current frame, including its markers.
        self.bytes = bytearray()
        self.parsing = False
        self.data_escaped = False
        self.done = False
        self._frame_wire_size = 0
        self._completed_frames = deque()
        self.request_map = {
            KamstrupRequestGetRegisters.command_byte: KamstrupRequestGetRegisters,
            KamstrupRequestLogin.command_byte: KamstrupRequestLogin,
        }

    def _reset_frame(self):
        self.bytes.clear()
        self.parsing = False
        self.data_escaped = False
        self.done = False
        self._frame_wire_size = 0

    def add_byte(self, byte):
        if isinstance(byte, int):
            value = byte
        elif isinstance(byte, bytes):
            value = byte[0]
        else:
            value = ord(byte)

        if not self.parsing:
            if value != kamstrup_constants.REQUEST_MAGIC:
                logger.debug(
                    "Kamstrup skipping byte, expected request magic but got: %s",
                    hex(value),
                )
                return
            self.parsing = True
            self._frame_wire_size = 1
            self.bytes.append(value)
            return

        self._frame_wire_size += 1
        if self._frame_wire_size > MAX_FRAME_SIZE:
            self._reset_frame()
            raise RequestFrameTooLarge(
                f"Kamstrup request exceeds {MAX_FRAME_SIZE} encoded bytes"
            )

        escaped = self.data_escaped
        if escaped:
            value ^= 0xFF
            self.data_escaped = False
        elif value == kamstrup_constants.ESCAPE:
            self.data_escaped = True
            return

        self.bytes.append(value)
        if value == kamstrup_constants.EOT_MAGIC and not escaped:
            self._completed_frames.append(bytes(self.bytes))
            self._reset_frame()

    def get_request(self):
        while self._completed_frames:
            frame = self._completed_frames.popleft()
            message = frame[1:-1]
            if len(message) < 4:
                logger.warning("Kamstrup request frame is too short.")
                continue
            if not self.valid_crc(message):
                logger.warning("Kamstrup CRC check failed for request.")
                continue

            communication_address, command_byte = message[:2]
            message_bytes = message[2:-2]
            if command_byte == KamstrupRequestGetRegisters.command_byte:
                if not message_bytes:
                    logger.warning("Kamstrup register request is missing its count.")
                    continue
                required_size = 1 + (2 * message_bytes[0])
                if len(message_bytes) < required_size:
                    logger.warning("Kamstrup register request is truncated.")
                    continue
                request_class = self.request_map[command_byte]
            elif command_byte == KamstrupRequestLogin.command_byte:
                if len(message_bytes) < 2:
                    logger.warning("Kamstrup login request is truncated.")
                    continue
                request_class = self.request_map[command_byte]
            else:
                request_class = KamstrupRequestUnknown

            return request_class(communication_address, command_byte, message_bytes)
        return None

    @classmethod
    def valid_crc(cls, message):
        supplied_crc = message[-2] * 256 + message[-1]
        calculated_crc = crc16xmodem(bytes(message[:-2]))
        return supplied_crc == calculated_crc
