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

import logging
import select
import os

from datetime import datetime

from gevent.socket import socket
from gevent.server import StreamServer

import conpot.core as conpot_core

logger = logging.getLogger(__name__)


class Proxy(object):
    def __init__(self, name, proxy_host, proxy_port, decoder=None):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.decoder = decoder
        self.name = name
        self.host = None
        self.port = None

    def get_server(self, host, port):
        self.host = host
        self.port = port
        connection = (host, port)
        server = StreamServer(connection, self.handle)
        logger.info('{0} proxy server started on: {1}, using {2} decoder.'.format(self.name, connection, self.decoder))
        return server

    def handle(self, sock, address):
        self.session = conpot_core.get_session('s7comm', address[0], address[1])
        logger.info('New connection from {0}:{1} on {2} proxy. ({3})'.format(address[0], address[1],
                                                                             self.name, self.session.id))

        data_file = None
        # to enable logging of raw socket data uncomment the following line
        # and execute the commands: 'mkdir data; chown nobody:nobody data'
        # data_file = open(os.path.join('data', 'Session-{0}'.format(self.session.id)), 'w')

        proxy_socket = socket()
        proxy_socket.connect((self.proxy_host, self.proxy_port))

        while True:
            sockets_read, _, sockets_err = select.select([proxy_socket, sock], [], [proxy_socket, sock], 10)

            if len(sockets_err) > 0:
                self._close(proxy_socket, sock)
                break

            for s in sockets_read:
                data = s.recv(1024)
                if len(data) is 0:
                    self._close([proxy_socket, sock])
                    break
                if s is proxy_socket:
                    self.handle_out_data(data, sock, data_file)
                elif s is sock:
                    self.handle_in_data(data, proxy_socket, data_file)
                else:
                    assert False

        data_file.close()

    def handle_in_data(self, data, sock, data_file):
        hex_data = data.encode('hex_codec')
        self.session.add_event({'request': hex_data, 'response': ''})
        logger.debug('Received {0} bytes from outside to proxied service: {1}'.format(len(data), hex_data))
        if self.decoder:
            self.decoder.add_adversary_data(data)
        if data_file:
            self._dump_data(data_file, 'in', hex_data)
        sock.send(data)

    def handle_out_data(self, data, sock, data_file):
        hex_data = data.encode('hex_codec')
        self.session.add_event({'request': '', 'response': hex_data})
        logger.debug('Received {0} bytes from proxied service: {1}'.format(len(data), hex_data))
        if self.decoder:
            self.decoder.add_proxy_data(data)
        if data_file:
            self._dump_data(data_file, 'out', hex_data)
        sock.send(data)

    def _dump_data(self, file_handle, direction, hex_data):
        file_handle.write('{0};{1};{2}\n'.format(datetime.utcnow().isoformat(), direction, hex_data))

    def _close(self, sockets):
        for s in sockets:
            s.close()
