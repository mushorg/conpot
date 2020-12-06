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
import os
import gevent
from gevent.server import StreamServer
from gevent.socket import socket
from gevent.ssl import wrap_socket
from conpot.helpers import fix_sslwrap
import conpot
from conpot.emulators.proxy import Proxy
from conpot.protocols.misc.ascii_decoder import AsciiDecoder

package_directory = os.path.dirname(os.path.abspath(conpot.__file__))


class TestProxy(unittest.TestCase):
    def test_proxy(self):
        self.test_input = "Hiya, this is a test".encode("utf-8")
        mock_service = StreamServer(("127.0.0.1", 0), self.echo_server)
        gevent.spawn(mock_service.start)
        gevent.sleep(1)

        proxy = Proxy("proxy", "127.0.0.1", mock_service.server_port)
        server = proxy.get_server("127.0.0.1", 0)
        gevent.spawn(server.start)
        gevent.sleep(1)

        s = socket()
        s.connect(("127.0.0.1", server.server_port))
        s.sendall(self.test_input)
        received = s.recv(len(self.test_input))
        self.assertEqual(self.test_input, received)
        mock_service.stop(1)

    def test_ssl_proxy(self):
        fix_sslwrap()
        self.test_input = "Hiya, this is a test".encode("utf-8")
        keyfile = os.path.join(package_directory, "templates/default/ssl/ssl.key")
        certfile = os.path.join(package_directory, "templates/default/ssl/ssl.crt")

        mock_service = StreamServer(
            ("127.0.0.1", 0), self.echo_server, keyfile=keyfile, certfile=certfile
        )
        gevent.spawn(mock_service.start)
        gevent.sleep(1)

        proxy = Proxy(
            "proxy",
            "127.0.0.1",
            mock_service.server_port,
            keyfile=keyfile,
            certfile=certfile,
        )
        server = proxy.get_server("127.0.0.1", 0)
        gevent.spawn(server.start)
        gevent.sleep(1)

        s = wrap_socket(socket(), keyfile=keyfile, certfile=certfile)
        s.connect(("127.0.0.1", server.server_port))
        s.sendall(self.test_input)
        received = s.recv(len(self.test_input))
        self.assertEqual(self.test_input, received)
        mock_service.stop(1)

    def test_ascii_decoder(self):
        test_decoder = AsciiDecoder()
        # should not raise a UnicodeDecodeError
        self.assertTrue(
            (test_decoder.decode_in(b"\x80abc") == b"\xef\xbf\xbdabc")
            and (test_decoder.decode_out(b"\x80abc") == b"\xef\xbf\xbdabc")
        )

    def test_proxy_with_decoder(self):
        self.test_input = "Hiya, this is a test".encode("utf-8")
        mock_service = StreamServer(("127.0.0.1", 0), self.echo_server)
        gevent.spawn(mock_service.start)
        gevent.sleep(1)

        proxy = Proxy(
            "proxy",
            "127.0.0.1",
            mock_service.server_port,
            decoder="conpot.protocols.misc.ascii_decoder.AsciiDecoder",
        )
        server = proxy.get_server("127.0.0.1", 0)
        gevent.spawn(server.start)
        gevent.sleep(1)

        s = socket()
        s.connect(("127.0.0.1", server.server_port))
        s.sendall(self.test_input)
        received = s.recv(len(self.test_input))
        self.assertEqual(self.test_input, received)
        mock_service.stop(1)

    def test_ssl_proxy_with_decoder(self):
        fix_sslwrap()
        self.test_input = "Hiya, this is a test".encode("utf-8")
        keyfile = os.path.join(package_directory, "templates/default/ssl/ssl.key")
        certfile = os.path.join(package_directory, "templates/default/ssl/ssl.crt")

        mock_service = StreamServer(
            ("127.0.0.1", 0), self.echo_server, keyfile=keyfile, certfile=certfile
        )
        gevent.spawn(mock_service.start)
        gevent.sleep(1)

        proxy = Proxy(
            "proxy",
            "127.0.0.1",
            mock_service.server_port,
            decoder="conpot.protocols.misc.ascii_decoder.AsciiDecoder",
            keyfile=keyfile,
            certfile=certfile,
        )
        server = proxy.get_server("127.0.0.1", 0)
        gevent.spawn(server.start)
        gevent.sleep(1)

        s = wrap_socket(socket(), keyfile=keyfile, certfile=certfile)
        s.connect(("127.0.0.1", server.server_port))
        s.sendall(self.test_input)
        received = s.recv(len(self.test_input))
        self.assertEqual(self.test_input, received)
        mock_service.stop(1)

    def echo_server(self, sock, address):
        r = sock.recv(len(self.test_input))
        sock.send(r)
