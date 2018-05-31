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

import gevent
import os
import unittest
import conpot
from gevent import socket
import conpot.core as conpot_core
from conpot.protocols.kamstrup.management_protocol.kamstrup_management_server import KamstrupManagementServer
from conpot.tests.data.kamstrup_management_data import RESPONSES


class TestKamstrupManagementProtocol(unittest.TestCase):
    """
        All tests work in similar way. We send a get command check for a valid reply. We send in set command and
        expect things to change in the databus.
    """

    def setUp(self):

        # clean up before we start...
        conpot_core.get_sessionManager().purge_sessions()

        # get the conpot directory
        self.dir_name = os.path.dirname(conpot.__file__)
        self.kamstrup_management_server = KamstrupManagementServer(
            self.dir_name + '/templates/kamstrup_382/kamstrup_meter/kamstrup_meter.xml', None, None
        )
        self.server_greenlet = gevent.spawn(self.kamstrup_management_server.start, '127.0.0.1', 50100)

        # initialize the databus
        self.databus = conpot_core.get_databus()
        self.databus.initialize(self.dir_name + '/templates/kamstrup_382/template.xml')
        gevent.sleep(1)

    def tearDown(self):
        self.kamstrup_management_server.stop()
        gevent.joinall([self.server_greenlet])
        # tidy up (again)...
        conpot_core.get_sessionManager().purge_sessions()

    def test_help_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.kamstrup_management_server.server.server_port))
        # receive the banner
        _ = s.recv(1024)
        # test the help command
        s.sendall(b'H\r\n')
        data = s.recv(1024)
        s.close()
        help_response = (data == RESPONSES['H']['H'])
        self.assertTrue(help_response)

    def test_access_control_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.kamstrup_management_server.server.server_port))
        # receive the banner
        _ = s.recv(1024)
        # test the help command
        s.sendall(b'H !AC\r\n')
        data = s.recv(1024)
        s.close()
        help_response = (data == RESPONSES['H']['!AC'])
        self.assertTrue(help_response)
        # TODO: next send a valid command and tests the command output
        # TODO: finally verify that values in the databus have actually changed!

    def test_alarm_server_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.kamstrup_management_server.server.server_port))
        # receive the banner
        _ = s.recv(1024)
        # test the help command
        s.sendall(b'H !AS\r\n')
        data = s.recv(1024)
        s.close()
        help_response = (data == RESPONSES['H']['!AS'])
        self.assertTrue(help_response)
        # TODO: next send a valid command and tests the command output
        # TODO: finally verify that values in the databus have actually changed!

    def test_get_config_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.kamstrup_management_server.server.server_port))
        # receive the banner
        _ = s.recv(1024)
        # test the help command
        s.sendall(b'H !GC\r\n')
        data = s.recv(1024)
        s.close()
        help_response = (data == RESPONSES['H']['!GC'])
        self.assertTrue(help_response)
        # TODO: next send a valid command and tests the command output
        # TODO: finally verify that values in the databus have actually changed!

    def test_get_software_version_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.kamstrup_management_server.server.server_port))
        # receive the banner
        _ = s.recv(1024)
        # test the help command
        s.sendall(b'H !GV\r\n')
        data = s.recv(1024)
        s.close()
        help_response = (data == RESPONSES['H']['!GV'])
        self.assertTrue(help_response)
        # TODO: next send a valid command and tests the command output
        # TODO: finally verify that values in the databus have actually changed!

    def test_set_kap1_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.kamstrup_management_server.server.server_port))
        # receive the banner
        _ = s.recv(1024)
        # test the help command
        s.sendall(b'H !SA\r\n')
        data = s.recv(1024)
        s.close()
        help_response = (data == RESPONSES['H']['!SA'])
        self.assertTrue(help_response)
        # TODO: next send a valid command and tests the command output
        # TODO: finally verify that values in the databus have actually changed!

    def test_set_kap2_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.kamstrup_management_server.server.server_port))
        # receive the banner
        _ = s.recv(1024)
        # test the help command
        s.sendall(b'H !SB\r\n')
        data = s.recv(1024)
        s.close()
        help_response = (data == RESPONSES['H']['!SB'])
        self.assertTrue(help_response)
        # TODO: next send a valid command and tests the command output
        # TODO: finally verify that values in the databus have actually changed!

    def test_set_config_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.kamstrup_management_server.server.server_port))
        # receive the banner
        _ = s.recv(1024)
        # test the help command
        s.sendall(b'H !SC\r\n')
        data = s.recv(1024)
        s.close()
        help_response = (data == RESPONSES['H']['!SC'])
        self.assertTrue(help_response)
        # TODO: next send a valid command and tests the command output
        # TODO: finally verify that values in the databus have actually changed!

    def test_set_device_name_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.kamstrup_management_server.server.server_port))
        # receive the banner
        _ = s.recv(1024)
        # test the help command
        s.sendall(b'H !SD\r\n')
        data = s.recv(1024)
        s.close()
        help_response = (data == RESPONSES['H']['!SD'])
        self.assertTrue(help_response)
        # TODO: next send a valid command and tests the command output
        # TODO: finally verify that values in the databus have actually changed!

    def test_set_lookup_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.kamstrup_management_server.server.server_port))
        # receive the banner
        _ = s.recv(1024)
        # test the help command
        s.sendall(b'H !SH\r\n')
        data = s.recv(1024)
        s.close()
        help_response = (data == RESPONSES['H']['!SH'])
        self.assertTrue(help_response)
        # TODO: next send a valid command and tests the command output
        # TODO: finally verify that values in the databus have actually changed!

    def test_set_ip_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.kamstrup_management_server.server.server_port))
        # receive the banner
        _ = s.recv(1024)
        # test the help command
        s.sendall(b'H !SI\r\n')
        data = s.recv(1024)
        s.close()
        help_response = (data == RESPONSES['H']['!SI'])
        self.assertTrue(help_response)
        # TODO: next send a valid command and tests the command output
        # TODO: finally verify that values in the databus have actually changed!

    def test_set_watchdog_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.kamstrup_management_server.server.server_port))
        # receive the banner
        _ = s.recv(1024)
        # test the help command
        s.sendall(b'H !SK\r\n')
        data = s.recv(1024)
        s.close()
        help_response = (data == RESPONSES['H']['!SK'])
        self.assertTrue(help_response)
        # TODO: next send a valid command and tests the command output
        # TODO: finally verify that values in the databus have actually changed!

    def test_set_name_server_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.kamstrup_management_server.server.server_port))
        # receive the banner
        _ = s.recv(1024)
        # test the help command
        s.sendall(b'H !SN\r\n')
        data = s.recv(1024)
        s.close()
        help_response = (data == RESPONSES['H']['!SN'])
        self.assertTrue(help_response)
        # TODO: next send a valid command and tests the command output
        # TODO: finally verify that values in the databus have actually changed!

    def test_set_ports_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.kamstrup_management_server.server.server_port))
        # receive the banner
        _ = s.recv(1024)
        # test the help command
        s.sendall(b'H !SP\r\n')
        data = s.recv(1024)
        s.close()
        help_response = (data == RESPONSES['H']['!SP'])
        self.assertTrue(help_response)
        # TODO: next send a valid command and tests the command output
        # TODO: finally verify that values in the databus have actually changed!

    def test_set_serial_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.kamstrup_management_server.server.server_port))
        # receive the banner
        _ = s.recv(1024)
        # test the help command
        s.sendall(b'H !SS\r\n')
        data = s.recv(1024)
        s.close()
        help_response = (data == RESPONSES['H']['!SS'])
        self.assertTrue(help_response)
        # TODO: next send a valid command and tests the command output
        # TODO: finally verify that values in the databus have actually changed!

    def test_request_connect_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.kamstrup_management_server.server.server_port))
        # receive the banner
        _ = s.recv(1024)
        # test the help command
        s.sendall(b'H !RC\r\n')
        data = s.recv(1024)
        s.close()
        help_response = (data == RESPONSES['H']['!RC'])
        self.assertTrue(help_response)
        # TODO: next send a valid command and tests the command output
        # TODO: finally verify that values in the databus have actually changed!


if __name__ == '__main__':
    unittest.main()