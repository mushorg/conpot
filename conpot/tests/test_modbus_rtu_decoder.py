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
import os

import conpot
from conpot.protocols.misc.modbus_rtu_decoder import ModbusRtuDecoder

package_directory = os.path.dirname(os.path.abspath(conpot.__file__))
try:
    import pty
except ImportError:
    pty = None
import serial

DATA = b'Hello\n'


@unittest.skipIf(pty is None, "pty module not supported on platform")
class TestModbusRtuDecoder(unittest.TestCase):
    """Test PTY serial open"""

    def setUp(self):
        # Open PTY
        self.master, self.slave = pty.openpty()

    def test_pty_serial_open_slave(self):
        with serial.Serial(os.ttyname(self.slave), timeout=1) as slave:
            pass  # OK

    def test_pty_serial_write(self):
        with serial.Serial(os.ttyname(self.slave), timeout=1) as slave:
            with os.fdopen(self.master, "wb") as fd:
                fd.write(DATA)
                fd.flush()
                out = slave.read(len(DATA))
                self.assertEqual(DATA, out)

    def test_pty_serial_read(self):
        with serial.Serial(os.ttyname(self.slave), timeout=1) as slave:
            with os.fdopen(self.master, "rb") as fd:
                slave.write(DATA)
                slave.flush()
                out = fd.read(len(DATA))
                self.assertEqual(DATA, out)

if __name__ == '__main__':
    sys.stdout.write(__doc__)
    # When this module is executed from the command-line, it runs all its tests
    unittest.main()
