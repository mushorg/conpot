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
import socket as _socket

import gevent
from gevent.socket import socket
from gevent.ssl import wrap_socket
from gevent.server import StreamServer

import conpot.core as conpot_core


logger = logging.getLogger(__name__)


class Proxy(object):
    def __init__(self, name, proxy_host, proxy_port, decoder=None, keyfile=None, certfile=None):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.name = name
        self.proxy_id = self.name.lower().replace(' ', '_')
        self.host = None
        self.port = None
        self.keyfile = keyfile
        self.certfile = certfile
        if decoder:
            namespace, _classname = decoder.rsplit('.', 1)
            module = __import__(namespace, fromlist=[_classname])
            _class = getattr(module, _classname)
            self.decoder = _class()
        else:
            self.decoder = None

    def get_server(self, host, port):
        self.host = host
        connection = (host, port)
        if self.keyfile and self.certfile:
            server = StreamServer(connection, self.handle, keyfile=self.keyfile, certfile=self.certfile)
        else:
            server = StreamServer(connection, self.handle)
        self.port = server.server_port
        logger.info('{0} proxy server started, listening on {1}, proxy for: ({2}, {3}) using {4} decoder.'
                    .format(self.name, connection, self.proxy_host, self.proxy_port, self.decoder))
        return server

    def handle(self, sock, address):
        session = conpot_core.get_session(self.proxy_id, address[0], address[1])
        logger.info('New connection from {0}:{1} on {2} proxy. ({3})'.format(address[0], address[1],
                                                                             self.proxy_id, session.id))
        proxy_socket = socket()

        if self.keyfile and self.certfile:
            proxy_socket = wrap_socket(proxy_socket, self.keyfile, self.certfile)

        try:
            proxy_socket.connect((self.proxy_host, self.proxy_port))
        except _socket.error as ex:
            logger.error('Error while connecting to proxied service at ({0}, {1}): {2}'
                         .format(self.proxy_host, self.proxy_port, ex))
            self._close([proxy_socket, sock])
            return

        sockets = [proxy_socket, sock]
        while len(sockets) == 2:
            gevent.sleep()
            sockets_read, _, sockets_err = select.select(sockets, [], sockets, 10)

            if len(sockets_err) > 0:
                self._close([proxy_socket, sock])
                break

            for s in sockets_read:
                socket_close_reason = 'socket closed'
                try:
                    data = s.recv(1024)
                except _socket.error as socket_err:
                    data = []
                    socket_close_reason = str(socket_err)
                if len(data) is 0:
                    self._close([proxy_socket, sock])
                    if s is proxy_socket:
                        logging.warning('Closing proxied socket while receiving ({0}, {1}): {2}.'
                                        .format(self.proxy_host, self.proxy_port, socket_close_reason))
                        sockets = []
                        break
                    elif s is sock:
                        logging.warning('Closing connection to remote while receiving from remote ({0}, {1}): {2}'
                                        .format(socket_close_reason, address[0], address[1]))
                        sockets = []
                        break
                    else:
                        assert False

                try:
                    if s is proxy_socket:
                        self.handle_out_data(data, sock, session)
                    elif s is sock:
                        self.handle_in_data(data, proxy_socket, session)
                    else:
                        assert False
                except _socket.error as socket_err:
                    if s is proxy_socket:
                        destination = 'proxied socket'
                    else:
                        destination = 'remote connection'
                    logger.warning('Error while sending data to {0}: {1}.'.format(destination, str(socket_err)))
                    sockets = []
                    break

        session.set_ended()
        proxy_socket.close()
        sock.close()

    def handle_in_data(self, data, sock, session):
        hex_data = data.encode('hex_codec')
        session.add_event({'raw_request': hex_data, 'raw_response': ''})
        logger.debug('Received {0} bytes from outside to proxied service: {1}'.format(len(data), hex_data))
        if self.decoder:
            # TODO: data could be chunked, proxy needs to handle this
            decoded = self.decoder.decode_in(data)
            logger.debug('Decoded request: {0}'.format(decoded))
            session.add_event({'request': decoded, 'raw_response': ''})
        sock.send(data)

    def handle_out_data(self, data, sock, session):
        hex_data = data.encode('hex_codec')
        session.add_event({'raw_request': '', 'raw_response': hex_data})
        logger.debug('Received {0} bytes from proxied service: {1}'.format(len(data), hex_data))
        if self.decoder:
            # TODO: data could be chunked, proxy needs to handle this
            decoded = self.decoder.decode_out(data)
            logger.debug('Decoded response: {0}'.format(decoded))
            session.add_event({'request': '', 'raw_response': decoded})
        sock.send(data)

    def _close(self, sockets):
        for s in sockets:
            s.close()

    def stop(self):
        # TODO: Keep active sockets in list and close them on stop()
        return
