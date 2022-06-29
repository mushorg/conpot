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
        _process = Popen(_cmd, stdout=PIPE, stderr=STDOUT, universal_newlines=True)
        _result_out, _ = _process.communicate()
        return _result_out

    def test_boot_device(self):
        """
        Objective: test boot device get and set
        """
        result = self.run_cmd(["chassis", "bootdev", "pxe"])
        self.assertEqual(result, "Set Boot Device to pxe\n")

    def test_power_state(self):
        """
        Objective: test power on/off/reset/cycle/shutdown
        """
        # power status
        result = self.run_cmd(["chassis", "power", "status"])
        self.assertEqual(result, "Chassis Power is off\n")

        # power on
        result = self.run_cmd(["chassis", "power", "on"])
        self.assertEqual(result, "Chassis Power Control: Up/On\n")

        # power off
        result = self.run_cmd(["chassis", "power", "off"])
        self.assertEqual(result, "Chassis Power Control: Down/Off\n")

        # power reset
        result = self.run_cmd(["chassis", "power", "reset"])
        self.assertEqual(result, "Chassis Power Control: Reset\n")

        # power cycle
        result = self.run_cmd(["chassis", "power", "cycle"])
        self.assertEqual(result, "Chassis Power Control: Cycle\n")

        # shutdown gracefully
        result = self.run_cmd(["chassis", "power", "soft"])
        self.assertEqual(result, "Chassis Power Control: Soft\n")

    def test_chassis_status(self):
        result = self.run_cmd(["chassis", "status"])
        self.assertEqual(
            result,
            "System Power         : off\n"
            "Power Overload       : false\n"
            "Power Interlock      : inactive\n"
            "Main Power Fault     : false\n"
            "Power Control Fault  : false\n"
            "Power Restore Policy : always-off\n"
            "Last Power Event     : \n"
            "Chassis Intrusion    : inactive\n"
            "Front-Panel Lockout  : inactive\n"
            "Drive Fault          : false\n"
            "Cooling/Fan Fault    : false\n",
        )

    def test_user_list(self):
        result = self.run_cmd(["user", "list"])
        self.assertEqual(
            result,
            "ID  Name\t     Callin  Link Auth\tIPMI Msg   Channel Priv Limit\n"
            "1   Administrator    true    true       true       ADMINISTRATOR\n"
            "2   Operator         true    false      false      OPERATOR\n"
            "3   User1            true    true       true       USER\n"
            "4   User2            true    false      false      USER\n"
            "5   User3            true    true       true       CALLBACK\n",
        )

    def test_channel_get_access(self):
        result = self.run_cmd(["channel", "getaccess", "1", "3"])
        self.assertIn(
            "Maximum User IDs     : 5\n"
            "Enabled User IDs     : 3\n\n"
            "User ID              : 3\n"
            "User Name            : User1\n"
            "Fixed Name           : Yes\n"
            "Access Available     : call-in / callback\n"
            "Link Authentication  : enabled\n"
            "IPMI Messaging       : enabled\n"
            "Privilege Level      : USER\n",
            result,
        )

    def test_misc(self):
        # change the session pass
        result = self.run_cmd(["set", "password", "1", "TEST"])
        self.assertEqual(result, "Set session password\n")
