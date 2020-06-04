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

from gevent import monkey

monkey.patch_all()
import unittest
from datetime import datetime
from modbus_tk.exceptions import ModbusError
import modbus_tk.defines as cst
import modbus_tk.modbus_tcp as modbus_tcp
from gevent import socket
import conpot.core as conpot_core
from conpot.protocols.modbus import modbus_server
from conpot.utils.greenlet import spawn_test_server, teardown_test_server


class TestModbusServer(unittest.TestCase):
    def setUp(self):
        conpot_core.get_sessionManager().purge_sessions()

        self.modbus, self.greenlet = spawn_test_server(
            modbus_server.ModbusServer, "default", "modbus"
        )

        self.databus = conpot_core.get_databus()
        self.host = self.modbus.server.server_host
        self.port = self.modbus.server.server_port

        # We have to use different slave IDs under different modes. In tcp mode,
        # only 255 and 0 make sense. However, modbus_tcp.TcpMaster explicitly
        # ignores slave ID 0. Therefore we can only use 255 in tcp mode.
        self.target_slave_id = 1 if self.modbus.mode == "serial" else 255

    def tearDown(self):
        teardown_test_server(self.modbus, self.greenlet)

    def test_read_coils(self):
        """
        Objective: Test if we can extract the expected bits from a slave using the modbus protocol.
        """
        self.databus.set_value(
            "memoryModbusSlave%dBlockA" % self.target_slave_id,
            [1 for b in range(0, 128)],
        )

        # create READ_COILS request
        master = modbus_tcp.TcpMaster(host=self.host, port=self.port)
        master.set_timeout(1.0)
        actual_bits = master.execute(
            slave=self.target_slave_id,
            function_code=cst.READ_COILS,
            starting_address=1,
            quantity_of_x=128,
        )

        # the test template sets all bits to 1 in the range 1-128
        expected_bits = [1 for b in range(0, 128)]
        self.assertSequenceEqual(actual_bits, expected_bits)

    def test_write_read_coils(self):
        """
        Objective: Test if we can change values using the modbus protocol.
        """
        master = modbus_tcp.TcpMaster(host=self.host, port=self.port)
        master.set_timeout(1.0)
        set_bits = [1, 0, 0, 1, 0, 0, 1, 1]

        # write 8 bits
        master.execute(
            slave=self.target_slave_id,
            function_code=cst.WRITE_MULTIPLE_COILS,
            starting_address=1,
            output_value=set_bits,
        )
        # read 8 bit
        actual_bit = master.execute(
            slave=self.target_slave_id,
            function_code=cst.READ_COILS,
            starting_address=1,
            quantity_of_x=8,
        )

        self.assertSequenceEqual(set_bits, actual_bit)

    def test_read_nonexistent_slave(self):
        """
        Objective: Test if the correct exception is raised when trying to read from nonexistent slave.
        """
        master = modbus_tcp.TcpMaster(host=self.host, port=self.port)
        master.set_timeout(1.0)
        with self.assertRaises(ModbusError) as cm:
            master.execute(
                slave=5,
                function_code=cst.READ_COILS,
                starting_address=1,
                quantity_of_x=1,
            )
        self.assertEqual(cm.exception.get_exception_code(), cst.SLAVE_DEVICE_FAILURE)

    def test_modbus_logging(self):
        """
        Objective: Test if modbus generates log messages as expected.
        Expected output is a dictionary with the following structure:
        {'timestamp': datetime.datetime(2013, 4, 23, 18, 47, 38, 532960),
         'remote': ('127.0.0.1', 60991),
         'data_type': 'modbus',
         'id': '01bd90d6-76f4-43cb-874f-5c8f254367f5',
         'data': {'function_code': 1,
                  'slave_id': 1,
                  'request': '0100010080',
                  'response': '0110ffffffffffffffffffffffffffffffff'}}
        """

        self.databus.set_value(
            "memoryModbusSlave%dBlockA" % self.target_slave_id,
            [1 for b in range(0, 128)],
        )

        master = modbus_tcp.TcpMaster(host=self.host, port=self.port)
        master.set_timeout(1.0)

        # issue request to modbus server
        master.execute(
            slave=self.target_slave_id,
            function_code=cst.READ_COILS,
            starting_address=1,
            quantity_of_x=128,
        )

        # extract the generated log entries
        log_queue = conpot_core.get_sessionManager().log_queue

        conn_log_item = log_queue.get(True, 2)
        conn_expected_payload = {"type": "NEW_CONNECTION"}
        self.assertDictEqual(conn_expected_payload, conn_log_item["data"])

        modbus_log_item = log_queue.get(True, 2)
        self.assertIsInstance(modbus_log_item["timestamp"], datetime)
        self.assertTrue("data" in modbus_log_item)
        # we expect session_id to be 36 characters long (32 x char, 4 x dashes)
        self.assertTrue(len(str(modbus_log_item["id"])), modbus_log_item)
        self.assertEqual("127.0.0.1", modbus_log_item["remote"][0])
        self.assertEqual("modbus", modbus_log_item["data_type"])

        req = (
            "000100000006%s0100010080" % ("01" if self.target_slave_id == 1 else "ff")
        ).encode()
        # testing the actual modbus data
        modbus_expected_payload = {
            "function_code": 1,
            "slave_id": self.target_slave_id,
            "request": req,
            "response": b"0110ffffffffffffffffffffffffffffffff",
        }

        self.assertDictEqual(modbus_expected_payload, modbus_log_item["data"])

    def test_report_slave_id(self):
        """
        Objective: Test conpot for function code 17.
        """
        # Function 17 is not currently supported by modbus_tk
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.host, self.port))
        s.sendall(b"\x00\x00\x00\x00\x00\x02\x01\x11")
        data = s.recv(1024)
        s.close()
        self.assertEqual(data, b"\x00\x00\x00\x00\x00\x06\x01\x11\x11\x01\x01\xff")

    def test_response_function_43_device_info(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.host, self.port))
        s.sendall(b"\x00\x01\x00\x00\x00\x05\x01\x2b\x0e\x01\x02")
        data = s.recv(1024)
        s.close()
        self.assertTrue(b"SIMATIC" in data and b"Siemens" in data)
