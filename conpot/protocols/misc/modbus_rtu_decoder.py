# Copyright (C) 2018  Abhinav Saxena <xandfury@gmail.com>
# Institute of Informatics and Communication, University of Delhi, South Campus
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
from struct import unpack
from modbus_tk import utils


class ModbusRtuDecoder:
    def __init__(self):
        pass

    @staticmethod
    def validate_crc(message):
        """Check whether the packet received is valid"""
        if len(message) < 3:
            return False
        else:
            (crc,) = unpack('>H', message[-2:])
            return crc == utils.calculate_crc(message[:-2])

    @classmethod
    def decode(cls, data):
        """Decode the contents of the packet"""
        assert cls.validate_crc(data), 'Not a valid Modbus RTU packet'
        logging.debug('Decoding message: {0}'.format(data))
        message = {}
        (message['Slave ID'], ) = unpack('>B', data[0])
        pdu = data[1:-2]
        if len(pdu) > 1:
            (message['function code'], ) = unpack('>B', data[1])
            message['Data'] = unpack('>' + ('B' * len(data[2:-2])), data[2:-2])
        (message['CRC'], ) = unpack('>H', data[-2:])
        return message


# for debugging:
if __name__ == '__main__':
    test_data = b'\x01\x02\x00\x00\x00\x01\xb9\xca'
    assert ModbusRtuDecoder.validate_crc(test_data)
    print(ModbusRtuDecoder.decode(test_data))