# Copyright (C) 2018  Abhinav Saxena <xandfury@gmail.com>
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
from lxml import etree
import conpot.core as conpot_core
from conpot.helpers import str_to_bytes
from gevent import socket
from gevent.server import StreamServer
from conpot.protocols.ftp.ftp_exceptions import FTPMaxLoginAttemptsExceeded
from conpot.protocols.ftp.ftp_handler import FTPHandler
from conpot.core.protocol_wrapper import conpot_protocol

logger = logging.getLogger(__name__)


@conpot_protocol
class FTPServer(object):
    def __init__(self, template, timeout=5):
        self.timeout = timeout
        # Initialize vfs here..
        self.server = None
        self.databus = conpot_core.get_databus()
        self._parse_template(template)

    def _parse_template(self, template):
        dom = etree.parse(template)
        self.terminator = b'\r\n'
        self.device_type = dom.xpath('//ftp/device_info/DeviceType/text()')[0]
        self.working_dir = dom.xpath('//ftp/device_info/Path/text()')[0]
        # The directory would be copied into the Temp VFS.
        self.banner = dom.xpath('//ftp/device_info/Banner/text()')[0]
        self.max_login_attempts = int(dom.xpath('//ftp/device_info/max_login_attempts/text()')[0])
        self.anon_auth = bool(dom.xpath('//ftp/device_info/anonymous_login/text()')[0])

    def handle(self, sock, address):
        sock.settimeout(self.timeout)
        session = conpot_core.get_session('ftp', address[0], address[1])
        logger.info('New FTP connection from {}:{}. ({})'.format(address[0], address[1], session.id))
        session.add_event({'type': 'NEW_CONNECTION'})
        # TODO: Is this operation too expensive?!
        command_responder = FTPHandler(self.device_type, self.working_dir, self.max_login_attempts, self.anon_auth,
                                       self.terminator, session)
        try:
            # send 200 + banner -- new client has connected!
            sock.send(b'200 ' + self.banner.encode() + self.terminator)
            while True:
                request = sock.recv(1024)
                if not request:
                    logger.info('FTP client disconnected. ({})', session.id)
                    session.add_event({'type': 'CONNECTION_LOST'})
                    del command_responder
                    break
                log_data = {'request': request}
                # request must of bytes type and response is also bytes
                response = command_responder.handle_request(request)
                log_data['response'] = response
                logger.info('FTP traffic from {}: {} ({})', address[0], log_data, session.id)
                session.add_event(log_data)
                #  Is there a delay in command response? < gevent.sleep(0.3)?

                if response is None:
                    session.add_event({'type': 'CONNECTION_LOST'})
                    break
                # encode data before sending
                reply = str_to_bytes(response)
                sock.send(reply)

        except FTPMaxLoginAttemptsExceeded:
            logger.debug('Maximum number of login attempts reached, disconnecting remote: {}. ({})', address[0],
                         session.id)
            session.add_event({'type': 'CONNECTION_TERMINATED'})
            del command_responder
        except socket.timeout:
            logger.debug('Socket timeout, remote: {}. ({})', address[0], session.id)
            session.add_event({'type': 'CONNECTION_LOST'})
            del command_responder

        sock.close()

    def start(self, host, port):
        connection = (host, port)
        self.server = StreamServer(connection, self.handle)
        logger.info('FTP server started on: {}'.format(connection))
        self.server.serve_forever()

    def stop(self):
        logger.debug('Stopping Telnet server')
        self.server.stop()


# ---- For debugging ----
if __name__ == '__main__':
    # Set vars for connection information
    TCP_IP = '127.0.0.1'
    TCP_PORT = 10001
    import os
    test_template = os.getcwd() + '/../../templates/default/ftp/ftp.xml'
    server = FTPServer(test_template)
    try:
        server.start(TCP_IP, TCP_PORT)
    except KeyboardInterrupt:
        server.stop()