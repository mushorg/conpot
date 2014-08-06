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

import gevent.monkey
gevent.monkey.patch_all()

import unittest
from datetime import datetime

from gevent.queue import Queue
from gevent.server import StreamServer
from gevent import monkey
from modbus_tk.modbus import ModbusError
import modbus_tk.defines as cst
import modbus_tk.modbus_tcp as modbus_tcp

from conpot.protocols.modbus import modbus_server
import conpot.core as conpot_core

monkey.patch_all()


class TestBase(unittest.TestCase):
    def setUp(self):

        # clean up before we start...
        conpot_core.get_sessionManager().purge_sessions()

        self.databus = conpot_core.get_databus()
        self.databus.initialize('conpot/templates/default.xml')
        modbus = modbus_server.ModbusServer('conpot/templates/default.xml', timeout=2)
        self.modbus_server = StreamServer(('127.0.0.1', 0), modbus.handle)
        self.modbus_server.start()

    def tearDown(self):
        self.modbus_server.stop()

        # tidy up (again)...
        conpot_core.get_sessionManager().purge_sessions()

    def test_read_coils(self):
        """
        Objective: Test if we can extract the expected bits from a slave using the modbus protocol.
        """
        self.databus.set_value('memoryModbusSlave1BlockA', [1 for b in range(0, 128)])

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
        Objective: Test if modbus generates log messages as expected.
        Expected output is a dictionary with the following structure:
        {'timestamp': datetime.datetime(2013, 4, 23, 18, 47, 38, 532960),
         'remote': ('127.0.0.1', 60991),
         'data_type': 'modbus',
         'id': '01bd90d6-76f4-43cb-874f-5c8f254367f5',
         'data': {'function_code': 1, 'slave_id': 1, 'request': '0100010080', 'response': '0110ffffffffffffffffffffffffffffffff'}}

        """

        self.databus.set_value('memoryModbusSlave1BlockA', [1 for b in range(0,128)])

        master = modbus_tcp.TcpMaster(host='127.0.0.1', port=self.modbus_server.server_port)
        master.set_timeout(1.0)
        #issue request to modbus server
        master.execute(slave=1, function_code=cst.READ_COILS, starting_address=1, quantity_of_x=128)

        #extract the generated logentry
        log_queue = conpot_core.get_sessionManager().log_queue
        log_item = log_queue.get(True, 2)

        self.assertIsInstance(log_item['timestamp'], datetime)
        self.assertTrue('data' in log_item)
        # we expect session_id to be 36 characters long (32 x char, 4 x dashes)
        self.assertTrue(len(str(log_item['id'])), log_item)
        self.assertEqual('127.0.0.1', log_item['remote'][0])
        self.assertEquals('modbus', log_item['data_type'])
        #testing the actual modbus data
        expected_payload = {'function_code': 1, 'slave_id': 1,'request': '000100000006010100010080',
                            'response': '0110ffffffffffffffffffffffffffffffff'}
        self.assertDictEqual(expected_payload, log_item['data'])