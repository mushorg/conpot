# Copyright (C) 2013  Johnny Vestergaard <jkv@unixcluster.dk>
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

from modules import modbus_server
from gevent.queue import Queue
from gevent.server import StreamServer
from gevent import monkey

#we need to monkey patch for modbus_tcp.TcpMaster
monkey.patch_all()
import modbus_tk.defines as cst
import modbus_tk.modbus_tcp as modbus_tcp


class TestBase(unittest.TestCase):
    def setUp(self):
        self.log_queue = Queue()
        modbus = modbus_server.ModbusServer('tests/data/basic_modbus_template.xml', self.log_queue)
        print modbus._databank
        self.modbus_server = StreamServer(('127.0.0.1', 0), modbus.handle)
        self.modbus_server.start()

    def tearDown(self):
        self.modbus_server.stop()

    def test_read_coils(self):
        """
        Objective: Test if we can extracted the expected bits from a slave using the modbus protocol.
        """
        master = modbus_tcp.TcpMaster(host='127.0.0.1', port=self.modbus_server.server_port)
        master.set_timeout(1.0)
        actual_bits = master.execute(slave=1, function_code=cst.READ_COILS, starting_address=1, quantity_of_x=128)
        #the test template sets all bits to 1 in the range 1-128
        expected_bits = [1 for b in range(0,128)]
        self.assertSequenceEqual(actual_bits, expected_bits)

    def test_write_read_coils(self):
        """
        Objective: Test if we can change values using the modbus protocol.
        """
        master = modbus_tcp.TcpMaster(host='127.0.0.1', port=self.modbus_server.server_port)
        master.set_timeout(1.0)
        set_bits = [1, 0, 0, 1, 0, 0, 1, 1]
        #write 8 bits
        master.execute(1, cst.WRITE_MULTIPLE_COILS, 1, output_value=set_bits)
        #read 8 bit
        actual_bit = master.execute(slave=1, function_code=cst.READ_COILS, starting_address=1, quantity_of_x=8)
        self.assertSequenceEqual(set_bits, actual_bit)

