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
from datetime import datetime

from gevent.queue import Queue
from gevent.server import StreamServer
from gevent import monkey
from modbus_tk.modbus import ModbusError
import modbus_tk.defines as cst
import modbus_tk.modbus_tcp as modbus_tcp

#we need to monkey patch for modbus_tcp.TcpMaster
from conpot.modbus import modbus_server

monkey.patch_all()


class TestBase(unittest.TestCase):
    def setUp(self):
        self.log_queue = Queue()
        modbus = modbus_server.ModbusServer('conpot/tests/data/basic_modbus_template.xml', self.log_queue, timeout=0.1)
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
        expected_bits = [1 for b in range(0, 128)]
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

    def test_read_nonexistent_slave(self):
        """
        Objective: Test if the correct exception is raised when trying to read from nonexistent slave.
        """
        master = modbus_tcp.TcpMaster(host='127.0.0.1', port=self.modbus_server.server_port)
        master.set_timeout(1.0)
        with self.assertRaises(ModbusError) as cm:
            master.execute(slave=5, function_code=cst.READ_COILS, starting_address=1, quantity_of_x=1)

        self.assertEqual(cm.exception.get_exception_code(), cst.SLAVE_DEVICE_FAILURE)

    def test_modbus_logging(self):
        """
        Objective: Test if modbus generates logging messages as expected.
        Expected output is a dictionary with the following structure:
        {'timestamp': datetime.datetime(2013, 4, 23, 18, 47, 38, 532960),
         'remote': ('127.0.0.1', 60991),
         'data_type': 'modbus',
         'session_id': '01bd90d6-76f4-43cb-874f-5c8f254367f5',
         'data': {0: {'function_code': 1, 'slave_id': 1, 'request': '0100010080', 'response': '0110ffffffffffffffffffffffffffffffff'}}}

        """
        master = modbus_tcp.TcpMaster(host='127.0.0.1', port=self.modbus_server.server_port)
        master.set_timeout(1.0)
        #issue request to modbus server
        master.execute(slave=1, function_code=cst.READ_COILS, starting_address=1, quantity_of_x=128)

        #extract the generated logentry
        log_item = self.log_queue.get(True, 2)

        #self.assertIn('timestamp', log_item)
        self.assertIsInstance(log_item['timestamp'], datetime)
        #we expect session_id to be 36 characters long (32 x char, 4 x dashes)
        self.assertTrue(len(log_item['session_id']), log_item)
        self.assertEqual('127.0.0.1', log_item['remote'][0])
        self.assertEquals('modbus', log_item['data_type'])
        #testing the actual modbus data
        self.assertEquals('0100010080', log_item['data'][0]['request'])
        self.assertEquals('0110ffffffffffffffffffffffffffffffff', log_item['data'][0]['response'])
