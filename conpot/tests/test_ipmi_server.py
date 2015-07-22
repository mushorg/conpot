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


from conpot.protocols.ipmi.ipmi_server import IpmiServer
import conpot.core as conpot_core

import unittest
from collections import namedtuple

import gevent.monkey

gevent.monkey.patch_all()


class TestIPMI(unittest.TestCase):
    def setUp(self):
        self.template_path = 'conpot/templates/ipmi/ipmi/ipmi.xml'

        # clean up before we start...
        conpot_core.get_sessionManager().purge_sessions()

        self.databus = conpot_core.get_databus()
        self.databus.initialize('conpot/templates/ipmi/template.xml')
	args = namedtuple('FakeArgs', 'port')
	args.port = 0
        self.ipmi_server = IpmiServer(
            self.template_path,
            'conpot/templates/ipmi/',
            args
        )
        self.greenlet = gevent.spawn(self.ipmi_server.start, '127.0.0.1', 0)

    def tearDown(self):
        self.greenlet.kill()
        # tidy up (again)...
        conpot_core.get_sessionManager().purge_sessions()

    def test_something(self):
        """
        Objective: Test the IPMI server
        """
        self.assertTrue(self.ipmi_server != None)
