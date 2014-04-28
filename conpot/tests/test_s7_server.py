# Copyright (C) 2013  Lukas Rist <glaslos@gmail.com>
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

import unittest
import socket

from gevent.queue import Queue
from conpot.protocols.s7comm.s7_server import S7Server

from gevent import monkey

monkey.patch_all()


class TestBase(unittest.TestCase):

    def setUp(self):
        self.log_queue = Queue()
        S7_instance = S7Server('conpot/templates/default.xml')
        self.S7_server = S7_instance.get_server('localhost', 0)
        self.S7_server.start()
        self.server_port = self.S7_server.server_port

    def tearDown(self):
        self.S7_server.stop()

    def test_s7(self):
        data = '0300001902f08032010000000000080000f0000001000101e0'.decode('hex')
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('localhost', self.server_port))
        s.sendall(data)
        data = s.recv(1024)
        s.close()
