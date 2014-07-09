# Copyright (C) 2014 Johnny Vestergaard <jkv@unixcluster.dk>
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

import socket
import crc16
from conpot.protocols.kamstrup import kamstrup_constants


class KamstrupRegisterRetriver(object):
    def __init__(self, ip_address,  port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((ip_address, port))

    def get_register(self, register):
        message = [kamstrup_constants.REQUEST_MAGIC, 0x3f, 0x10, 0x01,register >> 8, register & 0xff]
        crc = crc16.crc16xmodem(''.join([chr(item) for item in message[1:]]))
        message.append(crc >> 8)
        message.append(crc & 0xff)
        message.append(kamstrup_constants.EOT_MAGIC)
        self.sock.send(bytearray(message))
        return self.sock.recv(1024)

k = KamstrupRegisterRetriver('127.0.0.1', 1025)

found_registers = []

for x in range(0x30, 0x34):
    result = k.get_register(x)
    if len(result) > 6:
        found_registers.append(result)
        # TODO: Decode these...
        print 'Found value at {0}:{1}'.format(hex(x), result.encode('hex-codec'))