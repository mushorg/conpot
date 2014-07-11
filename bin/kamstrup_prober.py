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
import time
import argparse
import crc16
from conpot.protocols.kamstrup import kamstrup_constants


class KamstrupRegisterCopier(object):
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
            if message[y] in kamstrup_constants.NEED_ESCAPE:
                message[y] ^= 0xff
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


parser = argparse.ArgumentParser(description='Probes kamstrup meter registers.')
parser.add_argument('--registerfile', dest='registerfile', help='Reads registers from previous dumps files instead of'
                                                                'bruteforcing the meter.')
args = parser.parse_args()

found_registers = {}

if args.registerfile:
    candidate_registers_values = []
    with open(args.registerfile, 'r') as register_file:
        old_register_values = json.load(register_file)
    for value in old_register_values.iterkeys():
        candidate_registers_values.append(int(value))
else:
    candidate_registers_values = range(0x00, 0xffff)

kamstrupRegisterCopier = KamstrupRegisterCopier('127.0.0.1', 1025)

not_found_counts = 0
scanned = 0
for x in candidate_registers_values:
    result = kamstrupRegisterCopier.get_register(x).encode('hex-codec')
    if len(result) > 12:
        assert x not in found_registers
        # TODO: Strip message down to raw value
        found_registers[x] = (datetime.utcnow(), result)
        print 'Found register value at {0}:{1}'.format(hex(x), result)
    else:
        not_found_counts += 1
        if not_found_counts % 10 == 0:
            print ('Hang on, still scanning, so far scanned {0} and found {1} registers'
                    .format(scanned, len(found_registers)))
    scanned += 1

print 'Scanned {0} registers, found {1}.'.format(len(candidate_registers_values), len(found_registers))
with open('kamstrup_dump_{0}.json'.format(calendar.timegm(datetime.utcnow().utctimetuple())), 'w') as json_file:
    json_file.write(json.dumps(found_registers, indent=4, default=json_default))
