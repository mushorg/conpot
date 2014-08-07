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
import socket
import binascii

from gevent.server import StreamServer
import gevent

import conpot.core as conpot_core
from conpot.protocols.kamstrup.meter_protocol import request_parser
from command_responder import CommandResponder


logger = logging.getLogger(__name__)


class KamstrupServer(object):
    def __init__(self, template, timeout=0):
        self.timeout = timeout
        self.command_responder = CommandResponder(template)
        self.server_active = True
        conpot_core.get_databus().observe_value('reboot_signal', self.reboot)
        logger.info('Kamstrup protocol server initialized.')

    # pretending reboot... really just closing connecting while "rebooting"
    def reboot(self, key):
        assert(key == 'reboot_signal')
        self.server_active = False
        logger.debug('Pretending server reboot')
        gevent.spawn_later(2, self.set_reboot_done)

    def set_reboot_done(self):
        logger.debug('Stopped pretending reboot')
        self.server_active = True

    def handle(self, sock, address):
        session = conpot_core.get_session('kamstrup_protocol', address[0], address[1])
        logger.info('New connection from {0}:{1}. ({2})'.format(address[0], address[1], session.id))

        server_active = True

        parser = request_parser.KamstrupRequestParser()
        try:
            while server_active:
                raw_request = sock.recv(1024)

                if not raw_request:
                    logger.info('Client disconnected. ({0})'.format(session.id))
                    break

                for x in raw_request:
                    parser.add_byte(x)

                while True:
                    # TODO: Handle requests to wrong communication address
                    request = parser.get_request()
                    if not request:
                        break
                    else:
                        logdata = {'request': binascii.hexlify(bytearray(request.message_bytes))}
                        response = self.command_responder.respond(request)
                        serialized_response = response.serialize()
                        logdata['response'] = binascii.hexlify(serialized_response)
                        # TODO: Need a delay here, real Kamstrup meter has a delay aroudn 60 - 200 ms
                        # between each command
                        logger.debug('Kamstrup traffic from {0}: {1} ({2})'.format(address[0], logdata, session.id))
                        sock.send(serialized_response)
                        session.add_event(logdata)
        except socket.timeout:
            logger.debug('Socket timeout, remote: {0}. ({1})'.format(address[0], session.id))

        sock.close()

    def get_server(self, host, port):
        connection = (host, port)
        server = StreamServer(connection, self.handle)
        logger.info('Kamstrup protocol server started on: {0}'.format(connection))
        return server


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    print 'Starting kamstrup protocol server'
    kamstrup_server = KamstrupServer(None)
    server = kamstrup_server.get_server('0.0.0.0', 6666)
    server_greenlet = gevent.spawn(server.start)
    gevent.sleep(10000)

