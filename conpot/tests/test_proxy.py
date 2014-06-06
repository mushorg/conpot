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

import gevent.monkey
gevent.monkey.patch_all()

import unittest
import os

import gevent
from gevent.server import StreamServer
from gevent.socket import socket
from gevent.ssl import wrap_socket

import conpot
from conpot.emulators.proxy import Proxy

package_directory = os.path.dirname(os.path.abspath(conpot.__file__))


class TestProxy(unittest.TestCase):
    def test_proxy(self):
        self.test_input = 'Hiya, this is a test'
        mock_service = StreamServer(('127.0.0.1', 0), self.echo_server)
        gevent.spawn(mock_service.start)
        gevent.sleep(1)

        proxy = Proxy('proxy', '127.0.0.1', mock_service.server_port)
        server = proxy.get_server('127.0.0.1', 0)
        gevent.spawn(server.start)
        gevent.sleep(1)

        s = socket()
        s.connect(('127.0.0.1', server.server_port))
        s.sendall(self.test_input)
        received = s.recv(len(self.test_input))
        self.assertEqual(self.test_input, received)
        mock_service.stop(1)

    def test_ssl_proxy(self):
        self.test_input = 'Hiya, this is a test'
        keyfile = os.path.join(package_directory, 'templates/example_ssl.key')
        certfile = os.path.join(package_directory, 'templates/example_ssl.crt')

        mock_service = StreamServer(('127.0.0.1', 0), self.echo_server, keyfile=keyfile, certfile=certfile)
        gevent.spawn(mock_service.start)
        gevent.sleep(1)

        proxy = Proxy('proxy', '127.0.0.1', mock_service.server_port, keyfile=keyfile, certfile=certfile)
        server = proxy.get_server('127.0.0.1', 0)
        gevent.spawn(server.start)
        gevent.sleep(1)

        s = wrap_socket(socket(), keyfile, certfile)
        s.connect(('127.0.0.1', server.server_port))
        s.sendall(self.test_input)
        received = s.recv(len(self.test_input))
        self.assertEqual(self.test_input, received)
        mock_service.stop(1)

    def echo_server(self, sock, address):
        r = sock.recv(len(self.test_input))
        sock.send(r)
