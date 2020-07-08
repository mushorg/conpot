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

import gevent
from conpot.protocols.ipmi.ipmi_server import IpmiServer
import conpot.core as conpot_core
import subprocess
from gevent import subprocess
from gevent.subprocess import PIPE
import unittest
import os
import conpot
from collections import namedtuple


def run_cmd(cmd, port):
    _cmd = [
        "ipmitool",
        "-I",
        "lanplus",
        "-H",
        "localhost",
        "-p",
        str(port),
        "-R1",
        "-U",
        "Administrator",
        "-P",
        "Password",
    ]
    _cmd += cmd
    _process = subprocess.Popen(_cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    _result_out, _result_err = _process.communicate()
    rc = _process.returncode
    return _result_out, _result_err


class TestIPMI(unittest.TestCase):
    def setUp(self):
        # clean up before we start...
        conpot_core.get_sessionManager().purge_sessions()
        # get the current directory

        dir_name = os.path.dirname(conpot.__file__)
        args = namedtuple("FakeArgs", "port")
        args.port = 0
        conpot_core.get_databus().initialize(
            dir_name + "/templates/default/template.xml"
        )
        self.ipmi_server = IpmiServer(
            dir_name + "/templates/default/ipmi/ipmi.xml",
            dir_name + "/templates/default/",
            args,
        )
        self.greenlet = gevent.spawn(self.ipmi_server.start, "127.0.0.1", 0)
        gevent.sleep(1)

    def tearDown(self):
        self.greenlet.kill()
        # tidy up (again)...
        conpot_core.get_sessionManager().purge_sessions()

    def test_boot_device(self):
        """
        Objective: test boot device get and set
        """
        result, _ = run_cmd(
            cmd=["chassis", "bootdev", "pxe"],
            port=str(self.ipmi_server.server.server_port),
        )
        self.assertEqual(result, b"Set Boot Device to pxe\n")

    def test_power_state(self):
        """
        Objective: test power on/off/reset/cycle/shutdown
        """
        # power status
        result, _ = run_cmd(
            cmd=["chassis", "power", "status"],
            port=str(self.ipmi_server.server.server_port),
        )
        self.assertEqual(result, b"Chassis Power is off\n")
        # power on
        result, _ = run_cmd(
            cmd=["chassis", "power", "on"],
            port=str(self.ipmi_server.server.server_port),
        )
        self.assertEqual(result, b"Chassis Power Control: Up/On\n")
        # power off
        result, _ = run_cmd(
            cmd=["chassis", "power", "off"],
            port=str(self.ipmi_server.server.server_port),
        )
        self.assertEqual(result, b"Chassis Power Control: Down/Off\n")
        # power reset
        result, _ = run_cmd(
            cmd=["chassis", "power", "reset"],
            port=str(self.ipmi_server.server.server_port),
        )
        self.assertEqual(result, b"Chassis Power Control: Reset\n")
        # power cycle
        result, _ = run_cmd(
            cmd=["chassis", "power", "cycle"],
            port=str(self.ipmi_server.server.server_port),
        )
        self.assertEqual(result, b"Chassis Power Control: Cycle\n")
        # shutdown gracefully
        result, _ = run_cmd(
            cmd=["chassis", "power", "soft"],
            port=str(self.ipmi_server.server.server_port),
        )
        self.assertEqual(result, b"Chassis Power Control: Soft\n")

    def test_chassis_status(self):
        result, _ = run_cmd(
            cmd=["chassis", "status"], port=str(self.ipmi_server.server.server_port)
        )
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
        result, _ = run_cmd(
            cmd=["user", "list"], port=str(self.ipmi_server.server.server_port)
        )
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
        result, _ = run_cmd(
            cmd=["channel", "getaccess", "1", "3"],
            port=str(self.ipmi_server.server.server_port),
        )
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
        result, _ = run_cmd(
            cmd=["set", "password", "1", "TEST"],
            port=str(self.ipmi_server.server.server_port),
        )
        self.assertEqual(result, b"Set session password\n")


if __name__ == "__main__":
    unittest.main()
