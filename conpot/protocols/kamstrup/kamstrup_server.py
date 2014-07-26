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

from lxml import etree
from gevent.server import StreamServer
import gevent

import conpot.core as conpot_core
import request_parser


logger = logging.getLogger(__name__)


class KamstrupServer(object):
    def __init__(self, template, timeout=0):
        self.timeout = timeout
        # key: kamstrup register, value: databus key
        self.registers = {}
        dom = etree.parse(template)
        # template_name = dom.xpath('//kamstrup_protocol/@name')[0]
        registers = dom.xpath('//conpot_template/protocols/kamstrup/registers/*')
        for register in registers:
            register_name = register.attrib['name']
            register_databuskey = register.xpath('./value/text()')[0]
            assert register_name not in self.registers
            self.registers[register_name] = register_databuskey
        logger.info('Kamstrup protocol server initialized.')

    def handle(self, sock, address):
        session = conpot_core.get_session('kamstrup_protocol', address[0], address[1])
        logger.info('New connection from {0}:{1}. ({2})'.format(address[0], address[1], session.id))

        parser = request_parser.KamstrupRequestParser()
        try:
            while True:
                raw_request = sock.recv(1024)

                if not raw_request:
                    logger.info('Client disconnected. ({0})'.format(session.id))
                    break

                for x in raw_request:
                    parser.add_byte(x)

                while True:
                    request = parser.get_request()
                    if not request:
                        break
                    else:
                        logdata = {'request': binascii.hexlify(bytearray(request.message_bytes))}
                        logger.debug('Kamstrup traffic from {0}: {1} ({2})'.format(address[0], logdata, session.id))
                        # TODO: Create response packet and log it.
                        # logdata['response'] = binascii.hexlify(response.message_bytes)}
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

