# Copyright (C) 2014  Johnny Vestergaard <jkv@unixcluster.dk>
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

import gevent
import gevent.monkey
gevent.monkey.patch_all()
from gevent.server import StreamServer
from gevent.socket import socket

from conpot.emulators.proxy import Proxy


class TestProxy(unittest.TestCase):
    def test_proxy(self):
        mock_service = StreamServer(('127.0.0.1', 0), self.echo_server)
        gevent.spawn(mock_service.start)
        gevent.sleep(1)

        proxy = Proxy('proxy', '127.0.0.1', mock_service.server_port)
        server = proxy.get_server('127.0.0.1', 0)
        gevent.spawn(server.start)
        gevent.sleep(1)

        s = socket()
        s.connect(('127.0.0.1', server.server_port))
        test_input = 'Hiya, this is a test'
        for c in test_input:
            s.send(c)
            received = s.recv(1)
            self.assertEqual(c, received)

    def test_ssl_proxy(self):
        # TODO
        pass

    def echo_server(self, sock, address):
        while True:
            r = sock.recv(1)
            sock.send(r)
