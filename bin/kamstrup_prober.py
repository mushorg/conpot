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
from conpot.protocols.kamstrup import kamstrup_constants


class KamstrupRegisterReader(object):
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
        # TODO: Reconncet on failure, kamstrup drops after 20-30 requests.
        return self.sock.recv(1024)


def json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return None

k = KamstrupRegisterReader('127.0.0.1', 1025)

found_registers = {}

for x in range(0x00, 0xff):
    result = k.get_register(x).encode('hex-codec')
    if len(result) > 12:
        print result
        assert x not in found_registers
        # TODO: Strip message down to raw value
        found_registers[x] = (datetime.utcnow(), result)
        print 'Found register value at {0}:{1}'.format(hex(x), result)

print 'Scan done, found {0} registers.'.format(len(found_registers))
with open('kamstrup_dump_{0}.json'.format(calendar.timegm(datetime.utcnow().utctimetuple())), 'w') as the_file:
    the_file.write(json.dumps(found_registers, indent=4, default=json_default))