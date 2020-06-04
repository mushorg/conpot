# Copyright (C) 2018  Abhinav Saxena <xandfury@gmail.com>
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
import re
import unittest

from gevent import socket

from conpot.protocols.guardian_ast.guardian_ast_server import GuardianASTServer
from conpot.utils.greenlet import spawn_test_server, teardown_test_server

DATA = {
    "I20100": b"\nI20100\n05/30/2018 19:15\n\nSTATOIL STATION\n\n\n\nIN-TANK INVENTORY\n\nTANK PRODUCT             VOLUME TC VOLUME   ULLAGE   HEIGHT    WATER     TEMP\n  1  SUPER                 2428      2540     4465    39.88     6.62    53.74\n  2  UNLEAD                7457      7543     7874    65.59     8.10    58.17\n  3  DIESEL                6532      6664     4597    33.06     5.91    57.91\n  4  PREMIUM               2839      2867     4597    66.57     4.49    57.88\n",
    "I20200": b"\nI20200\n05/30/2018 19:17\n\nSTATOIL STATION\n\n\n\nDELIVERY REPORT\n\nT 1:SUPER                 \nINCREASE   DATE / TIME             GALLONS TC GALLONS WATER  TEMP DEG F  HEIGHT\n\n      END: 05/30/2018 14:14         1947       2064   5.32      56.55    65.48\n    START: 05/30/2018 14:04         1347       1464   5.32      56.55    42.480000000000004\n   AMOUNT:                          1647       1764\n\n",
    "I20300": b"\nI20300\n05/30/2018 19:18\n\nSTATOIL STATION\n\n\nTANK 1    SUPER                 \n    TEST STATUS: OFF\nLEAK DATA NOT AVAILABLE ON THIS TANK\n\nTANK 2    UNLEAD                \n    TEST STATUS: OFF\nLEAK DATA NOT AVAILABLE ON THIS TANK\n\nTANK 3    DIESEL                \n    TEST STATUS: OFF\nLEAK DATA NOT AVAILABLE ON THIS TANK\n\nTANK 4    PREMIUM               \n    TEST STATUS: OFF\nLEAK DATA NOT AVAILABLE ON THIS TANK\n\n",
    "I20400": b"\nI20400\n05/30/2018 19:18\n\nSTATOIL STATION\n\n\n\nSHIFT REPORT\n\nSHIFT 1 TIME: 12:00 AM\n\nTANK PRODUCT\n\n  1  SUPER                  VOLUME TC VOLUME  ULLAGE  HEIGHT  WATER   TEMP\nSHIFT  1 STARTING VALUES      7950     8130    9372   31.03   1.25    52.60\n         ENDING VALUES        8890     9016    9717   84.03  1.25    52.60\n         DELIVERY VALUE          0\n         TOTALS                940\n\n",
    "I20500": b"\nI20500\n05/30/2018 19:18\n\n\nSTATOIL STATION\n\n\nTANK   PRODUCT                 STATUS\n\n  1    SUPER                   NORMAL\n\n  2    UNLEAD                  HIGH WATER ALARM\n                               HIGH WATER WARNING\n\n  3    DIESEL                  NORMAL\n\n  4    PREMIUM                 NORMAL\n\n",
}


class TestGuardianAST(unittest.TestCase):
    def setUp(self):
        self.guardian_ast_server, self.server_greenlet = spawn_test_server(
            GuardianASTServer, "guardian_ast", "guardian_ast"
        )

    def tearDown(self):
        teardown_test_server(self.guardian_ast_server, self.server_greenlet)

    def test_I20100(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", self.guardian_ast_server.server.server_port))
        s.send(b"\x01I20100\r\n")
        data = s.recv(1024)
        s.close()
        # FIXME: Omitting the time etc from data - mechanism to check them needed as well?
        self.assertEqual(
            data[:8] + data[24:156], DATA["I20100"][:8] + DATA["I20100"][24:156]
        )

    def test_I20200(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", self.guardian_ast_server.server.server_port))
        s.send(b"\x01I20200\r\n")
        data = s.recv(1024)
        s.close()
        self.assertEqual(
            data[:8] + data[24:181], DATA["I20200"][:8] + DATA["I20200"][24:181]
        )

    def test_I20300(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", self.guardian_ast_server.server.server_port))
        s.send(b"\x01I20300\r\n")
        data = s.recv(1024)
        s.close()
        self.assertEqual(data[:8] + data[24:], DATA["I20300"][:8] + DATA["I20300"][24:])

    def test_I20400(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", self.guardian_ast_server.server.server_port))
        s.send(b"\x01I20400\r\n")
        data = s.recv(1024)
        s.close()
        self.assertEqual(
            data[:8] + data[24:202], DATA["I20400"][:8] + DATA["I20400"][24:202]
        )

    def test_I20500(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", self.guardian_ast_server.server.server_port))
        s.send(b"\x01I20500\r\n")
        data = s.recv(1024)
        s.close()
        self.assertEqual(data[:8] + data[24:], DATA["I20500"][:8] + DATA["I20500"][24:])

    def test_ast_error(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", self.guardian_ast_server.server.server_port))
        s.send(b"\x01S6020\r\n")
        data = s.recv(1024)
        s.close()
        self.assertEqual(data, b"9999FF1B\n")

    def test_S60201(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(("127.0.0.1", self.guardian_ast_server.server.server_port))
        s.send(b"\x01S60201NONSUPER\r\n")
        try:
            _ = s.recv(1024)
        except socket.timeout:
            pass
        s.send(b"\x01I20100\r\n")
        data = s.recv(1024)
        s.close()
        self.assertIn(b"NONSUPER", data)

    def test_S60202(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(("127.0.0.1", self.guardian_ast_server.server.server_port))
        s.send(b"\x01S60202TESTLEAD\r\n")
        try:
            _ = s.recv(1024)
        except socket.timeout:
            pass
        s.send(b"\x01I20100\r\n")
        data = s.recv(1024)
        s.close()
        self.assertIn(b"TESTLEAD", data)

    def test_S60203(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(("127.0.0.1", self.guardian_ast_server.server.server_port))
        s.send(b"\x01S60203TESTDIESEL\r\n")
        try:
            _ = s.recv(1024)
        except socket.timeout:
            pass
        s.send(b"\x01I20100\r\n")
        data = s.recv(1024)
        s.close()
        self.assertIn(b"TESTDIESEL", data)

    def test_S60204(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(("127.0.0.1", self.guardian_ast_server.server.server_port))
        s.send(b"\x01S60204TESTPREMIUM\r\n")
        try:
            _ = s.recv(1024)
        except socket.timeout:
            pass
        s.send(b"\x01I20100\r\n")
        data = s.recv(1024)
        s.close()
        self.assertIn(b"TESTPREMIUM", data)

    def test_S60200(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(("127.0.0.1", self.guardian_ast_server.server.server_port))
        s.send(b"\x01S60200ULTIMATETEST\r\n")
        try:
            _ = s.recv(1024)
        except socket.timeout:
            pass
        s.send(b"\x01I20100\r\n")
        data = s.recv(1024)
        s.close()
        count = len(re.findall("(?=ULTIMATETEST)", data.decode()))
        self.assertEqual(count, 4)
