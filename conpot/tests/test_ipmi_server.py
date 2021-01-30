# Copyright (C) 2015 Lukas Rist <glaslos@gmail.com>
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
from gevent.subprocess import Popen, PIPE, STDOUT
import unittest
from conpot.protocols.ipmi.ipmi_server import IpmiServer
from conpot.utils.greenlet import spawn_test_server, teardown_test_server


class TestIPMI(unittest.TestCase):
    def setUp(self):
        self.ipmi_server, self.greenlet = spawn_test_server(
            IpmiServer, "default", "ipmi"
        )

    def tearDown(self):
        teardown_test_server(self.ipmi_server, self.greenlet)

    def run_cmd(self, cmd):
        _cmd = [
            "ipmitool",
            "-I",
            "lanplus",
            "-H",
            self.ipmi_server.server.server_host,
            "-p",
            str(self.ipmi_server.server.server_port),
            "-R1",
            "-U",
            "Administrator",
            "-P",
            "Password",
        ]
        _cmd += cmd
        _process = Popen(_cmd, stdout=PIPE, stderr=STDOUT)
        _result_out, _ = _process.communicate()
        return _result_out

    def test_boot_device(self):
        """
        Objective: test boot device get and set
        """
        result = self.run_cmd(["chassis", "bootdev", "pxe"])
        self.assertEqual(result, b"Set Boot Device to pxe\n")

    def test_power_state(self):
        """
        Objective: test power on/off/reset/cycle/shutdown
        """
        # power status
        result = self.run_cmd(["chassis", "power", "status"])
        self.assertEqual(result, b"Chassis Power is off\n")

        # power on
        result = self.run_cmd(["chassis", "power", "on"])
        self.assertEqual(result, b"Chassis Power Control: Up/On\n")

        # power off
        result = self.run_cmd(["chassis", "power", "off"])
        self.assertEqual(result, b"Chassis Power Control: Down/Off\n")

        # power reset
        result = self.run_cmd(["chassis", "power", "reset"])
        self.assertEqual(result, b"Chassis Power Control: Reset\n")

        # power cycle
        result = self.run_cmd(["chassis", "power", "cycle"])
        self.assertEqual(result, b"Chassis Power Control: Cycle\n")

        # shutdown gracefully
        result = self.run_cmd(["chassis", "power", "soft"])
        self.assertEqual(result, b"Chassis Power Control: Soft\n")

    def test_chassis_status(self):
        result = self.run_cmd(["chassis", "status"])
        self.assertEqual(
            result,
            b"System Power         : off\n"
            b"Power Overload       : false\n"
            b"Power Interlock      : inactive\n"
            b"Main Power Fault     : false\n"
            b"Power Control Fault  : false\n"
            b"Power Restore Policy : always-off\n"
            b"Last Power Event     : \n"
            b"Chassis Intrusion    : inactive\n"
            b"Front-Panel Lockout  : inactive\n"
            b"Drive Fault          : false\n"
            b"Cooling/Fan Fault    : false\n",
        )

    def test_user_list(self):
        result = self.run_cmd(["user", "list"])
        self.assertEqual(
            result,
            b"ID  Name\t     Callin  Link Auth\tIPMI Msg   Channel Priv Limit\n"
            b"1   Administrator    true    true       true       ADMINISTRATOR\n"
            b"2   Operator         true    false      false      OPERATOR\n"
            b"3   User1            true    true       true       USER\n"
            b"4   User2            true    false      false      USER\n"
            b"5   User3            true    true       true       CALLBACK\n",
        )

    def test_channel_get_access(self):
        result = self.run_cmd(["channel", "getaccess", "1", "3"])
        self.assertIn(
            b"Maximum User IDs     : 5\n"
            b"Enabled User IDs     : 3\n\n"
            b"User ID              : 3\n"
            b"User Name            : User1\n"
            b"Fixed Name           : Yes\n"
            b"Access Available     : call-in / callback\n"
            b"Link Authentication  : enabled\n"
            b"IPMI Messaging       : enabled\n"
            b"Privilege Level      : USER\n",
            result,
        )

    def test_misc(self):
        # change the session pass
        result = self.run_cmd(["set", "password", "1", "TEST"])
        self.assertEqual(result, b"Set session password\n")
