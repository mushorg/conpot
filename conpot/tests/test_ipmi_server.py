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


class TestIPMI(unittest.TestCase):
    def setUp(self):
        # clean up before we start...
        conpot_core.get_sessionManager().purge_sessions()
        # get the current directory

        dir_name = os.path.dirname(conpot.__file__)
        args = namedtuple('FakeArgs', 'port')
        args.port = 0
        conpot_core.get_databus().initialize(dir_name + '/templates/default/template.xml')
        self.ipmi_server = IpmiServer(dir_name + '/templates/default/ipmi/ipmi.xml',
                                      dir_name + '/templates/default/', args)
        self.greenlet = gevent.spawn(self.ipmi_server.start, '127.0.0.1', 0)
        gevent.sleep(1)

    def tearDown(self):
        self.greenlet.kill()
        # tidy up (again)...
        conpot_core.get_sessionManager().purge_sessions()

    def test_boot_device(self):
        """
        Objective: test boot device get and set
        """
        _process = subprocess.Popen(['ipmitool', '-I', 'lanplus', '-H', 'localhost', '-p',
                                    str(self.ipmi_server.server.server_port), '-R1', '-U', 'Administrator', '-P',
                                     'Password', 'chassis', 'power', 'status'], stdin=PIPE, stdout=PIPE, stderr=PIPE)
        _result_out, _result_err = _process.communicate()
        rc = _process.returncode
        self.assertTrue(_result_out)

    def test_reset(self):
        """
        Objective: test device reset/cold reset
        """
        self.assertTrue(self.ipmi_server != None)

    def test_power_state(self):
        """
        Objective: test power on/off/reset/cycle/shutdown
        """
        self.assertTrue(self.ipmi_server != None)

    def test_auth(self):
        # set user pass
        # set User Name
        # Session Privilege
        pass


if __name__ == '__main__':
    unittest.main()