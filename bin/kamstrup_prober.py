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
import json
from datetime import datetime
import calendar
import crc16
import time
from conpot.protocols.kamstrup import kamstrup_constants


class KamstrupRegisterReader(object):
    def __init__(self, ip_address,  port):
        self._sock = None
        self.ip_address = ip_address
        self.port = port
        self._connect()

    def _connect(self):
        print 'Connecting to {0}:{1}'.format(self.ip_address, self.port)
        if self._sock is not None:
            self._sock.close()
            time.sleep(1)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(2)
        self._sock.connect((self.ip_address, self.port))

    def get_register(self, register):
        message = [kamstrup_constants.REQUEST_MAGIC, 0x3f, 0x10, 0x01, register >> 8, register & 0xff]
        crc = crc16.crc16xmodem(''.join([chr(item) for item in message[1:]]))
        message.append(crc >> 8)
        message.append(crc & 0xff)
        message_length = len(message)
        y = 1
        while y < message_length:
            # TODO: Something is up with the CRC, sometimes it fails. seems related to escaping
            if message[y] in kamstrup_constants.NEED_ESCAPE:
                message.insert(y, kamstrup_constants.ESCAPE)
                y += 1
                message_length += 1
            y += 1
        message.append(kamstrup_constants.EOT_MAGIC)

        received_data = None
        while received_data is None:
            try:
                self._sock.send(bytearray(message))
                received_data = self._sock.recv(1024)
            except socket.error as socket_err:
                print 'Error while communicating: {0}'.format(str(socket_err))
                self._connect()

        return received_data


def json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return None

k = KamstrupRegisterReader('127.0.0.1', 1025)

found_registers = {}

for x in range(0x01, 0xff):
    result = k.get_register(x).encode('hex-codec')
    if len(result) > 12:
        assert x not in found_registers
        # TODO: Strip message down to raw value
        found_registers[x] = (datetime.utcnow(), result)
        print 'Found register value at {0}:{1}'.format(hex(x), result)

print 'Scan done, found {0} registers.'.format(len(found_registers))
with open('kamstrup_dump_{0}.json'.format(calendar.timegm(datetime.utcnow().utctimetuple())), 'w') as the_file:
    the_file.write(json.dumps(found_registers, indent=4, default=json_default))