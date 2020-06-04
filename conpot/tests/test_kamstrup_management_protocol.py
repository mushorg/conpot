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
import unittest
from gevent import socket
from conpot.protocols.kamstrup.management_protocol.kamstrup_management_server import (
    KamstrupManagementServer,
)
from conpot.tests.data.kamstrup_management_data import RESPONSES
from conpot.utils.greenlet import spawn_test_server, teardown_test_server


def check_command_resp_help_message(
    packet_type, help_msg_command, packet_msg_command, kamstrup_management_server
):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", kamstrup_management_server.server.server_port))
    _ = s.recv(1024)  # receive the banner
    s.sendall(help_msg_command)  # test the help command
    help_data = s.recv(1024)
    help_response = help_data == RESPONSES["H"][packet_type]
    s.sendall(packet_msg_command)
    pkt_data = s.recv(1024)
    packet_resp = pkt_data == RESPONSES[packet_type]
    s.close()
    return help_response and packet_resp


class TestKamstrupManagementProtocol(unittest.TestCase):
    """
    All tests work in similar way. We send a get command check for a valid reply. We send in set command and
    expect things to change in the databus.
    """

    def setUp(self):
        self.kamstrup_management_server, self.server_greenlet = spawn_test_server(
            KamstrupManagementServer, "kamstrup_382", "kamstrup_management"
        )

    def tearDown(self):
        teardown_test_server(self.kamstrup_management_server, self.server_greenlet)

    def test_help_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", self.kamstrup_management_server.server.server_port))
        _ = s.recv(1024)  # receive the banner
        s.sendall(b"H\r\n")  # test the help command
        data = s.recv(1024)
        s.close()
        self.assertEqual(data, RESPONSES["H"]["H"])

    def test_set_config_command(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", self.kamstrup_management_server.server.server_port))
        _ = s.recv(1024)  # receive the banner
        s.sendall(b"H !SC\r\n")  # test the help command
        data = s.recv(1024)
        s.close()
        self.assertEqual(data, RESPONSES["H"]["!SC"])

    def test_access_control_command(self):
        self.assertTrue(
            check_command_resp_help_message(
                "!AC",
                b"H !AC\r\n",
                b"!AC 0 2 192.168.1.211\r\n",
                self.kamstrup_management_server,
            )
        )

    def test_alarm_server_command(self):
        self.assertTrue(
            check_command_resp_help_message(
                "!AS",
                b"H !AS\r\n",
                b"!AC 192.168.1.4 4000\r\n",
                self.kamstrup_management_server,
            )
        )

    def test_get_config_command(self):
        self.assertTrue(
            check_command_resp_help_message(
                "!GC", b"H !GC\r\n", b"!GC\r\n", self.kamstrup_management_server
            )
        )

    def test_get_software_version_command(self):
        self.assertTrue(
            check_command_resp_help_message(
                "!GV", b"H !GV\r\n", b"!GV\r\n", self.kamstrup_management_server
            )
        )

    def test_set_kap1_command(self):
        # TODO: verify that values in the databus have actually changed!
        self.assertTrue(
            check_command_resp_help_message(
                "!SA",
                b"H !SA\r\n",
                b"!SA 192168001002 61000\r\n",
                self.kamstrup_management_server,
            )
        )

    def test_set_kap2_command(self):
        # TODO: verify that values in the databus have actually changed!
        self.assertTrue(
            check_command_resp_help_message(
                "!SB",
                b"H !SB\r\n",
                b"!SB 192.168.1.2 61000\r\n",
                self.kamstrup_management_server,
            )
        )

    def test_set_device_name_command(self):
        # TODO: verify that values in the databus have actually changed!
        self.assertTrue(
            check_command_resp_help_message(
                "!SD", b"H !SD\r\n", b"!SD\r\n", self.kamstrup_management_server
            )
        )

    def test_set_lookup_command(self):
        # TODO: verify that values in the databus have actually changed!
        self.assertTrue(
            check_command_resp_help_message(
                "!SH",
                b"H !SH\r\n",
                b"!SH hosting.kamstrup_meter.dk\r\n",
                self.kamstrup_management_server,
            )
        )

    def test_set_ip_command(self):
        # TODO: verify that values in the databus have actually changed!
        self.assertTrue(
            check_command_resp_help_message(
                "!SI",
                b"H !SI\r\n",
                b"!SI 192168001200\r\n",
                self.kamstrup_management_server,
            )
        )

    def test_set_watchdog_command(self):
        # TODO: verify that values in the databus have actually changed!
        self.assertTrue(
            check_command_resp_help_message(
                "!SK",
                b"H !SK\r\n",
                b"!SK 3600 60 10\r\n",
                self.kamstrup_management_server,
            )
        )

    def test_set_name_server_command(self):
        # TODO: verify that values in the databus have actually changed!
        self.assertTrue(
            check_command_resp_help_message(
                "!SN",
                b"H !SN\r\n",
                b"!SN 192168001200 192168001201 000000000000\r\n",
                self.kamstrup_management_server,
            )
        )

    def test_set_ports_command(self):
        # TODO: verify that values in the databus have actually changed!
        self.assertTrue(
            check_command_resp_help_message(
                "!SP",
                b"H !SP\r\n",
                b"!SP 50 1025 1026 50100\r\n",
                self.kamstrup_management_server,
            )
        )

    def test_set_serial_command(self):
        # TODO: verify that values in the databus have actually changed!
        self.assertTrue(
            check_command_resp_help_message(
                "!SS",
                b"H !SS\r\n",
                b"!SS B 115200,8,E,1,L\r\n",
                self.kamstrup_management_server,
            )
        )

    def test_request_connect_command(self):
        self.assertTrue(
            check_command_resp_help_message(
                "!RC",
                b"H !RC\r\n",
                b"!RC A 195.215.168.45\r\n",
                self.kamstrup_management_server,
            )
        )
