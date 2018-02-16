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

import unittest
from conpot.protocols.misc.modbus_rtu_decoder import ModbusRtuDecoder


class TestModbusRtuDecoder(unittest.TestCase):
    """Test to check if Modbus RTU decoder is working as expected"""

    def setUp(self):
        self.test_data = b'\x01\x02\x00\x00\x00\x01\xb9\xca'
        self.result = {'Data': (0, 0, 0, 1), 'function code': 2, 'Slave ID': 1, 'CRC': 47562}

    def test_modbus_rtu_decoder(self):
        self.assertTrue(ModbusRtuDecoder.validate_crc(self.test_data))
        self.decoded = [values for values in ModbusRtuDecoder.decode(self.test_data).values()]
        for i in self.decoded:
            self.assertIn(i, self.result.values())


if __name__ == '__main__':
    unittest.main()
