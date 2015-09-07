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

from gevent.server import StreamServer
from gevent import monkey

from conpot.protocols.guardian_ast import guardian_ast_server
import conpot.core as conpot_core

monkey.patch_all()


class TestBase(unittest.TestCase):
    def setUp(self):
        conpot_core.get_sessionManager().purge_sessions()
        self.databus = conpot_core.get_databus()
        self.databus.initialize('conpot/templates/guardian_ast/template.xml')
        guardian_ast = guardian_ast_server.GuardianASTServer(None, None, None)
        self.guardian_ast_server = StreamServer(('127.0.0.1', 0), guardian_ast.handle)
        self.guardian_ast_server.start()

    def tearDown(self):
        self.guardian_ast_server.stop()

        # tidy up (again)...
        conpot_core.get_sessionManager().purge_sessions()

    def test_I20100(self):
        """
        Objective: Test if we can read the I20100 command
        """
        from gevent.socket import create_connection
        socket = create_connection(('127.0.0.1', self.guardian_ast_server.server_port))
        socket.send('\x01I20100')
        data = socket.recv(1024)
        self.assertTrue('IN-TANK INVENTORY' in data)

    def test_I20200(self):
        """
        Objective: Test if we can read the I20200 command
        """
        from gevent.socket import create_connection
        socket = create_connection(('127.0.0.1', self.guardian_ast_server.server_port))
        socket.send('\x01I20200')
        data = socket.recv(1024)
        self.assertTrue('DELIVERY REPORT' in data)

    def test_I20300(self):
        """
        Objective: Test if we can read the I20300 command
        """
        from gevent.socket import create_connection
        socket = create_connection(('127.0.0.1', self.guardian_ast_server.server_port))
        socket.send('\x01I20300')
        data = socket.recv(1024)
        self.assertTrue('TEST STATUS' in data)

    def test_I20400(self):
        """
        Objective: Test if we can read the I20400 command
        """
        from gevent.socket import create_connection
        socket = create_connection(('127.0.0.1', self.guardian_ast_server.server_port))
        socket.send('\x01I20400')
        data = socket.recv(1024)
        self.assertTrue('SHIFT REPORT' in data)

    def test_I20500(self):
        """
        Objective: Test if we can read the I20500 command
        """
        from gevent.socket import create_connection
        socket = create_connection(('127.0.0.1', self.guardian_ast_server.server_port))
        socket.send('\x01I20500')
        data = socket.recv(1024)
        self.assertTrue('HIGH WATER ALARM' in data)


if __name__ == '__main__':
    unittest.main()
