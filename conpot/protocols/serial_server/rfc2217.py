# Conpot's serial to Ethernet conversion.
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

import socket

import sys
import time
import threading
import serial
import serial.rfc2217

import logging
from lxml import etree

logger = logging.getLogger(__name__)


class SerialServer:
    """
    Some description - Serial to Ethernet converter
    """
    def __init__(self, template, template_directory, args):

        self.timeout = 5
        self.server = None # Initialize later

        # Get the slave settings from template
        self.dom = etree.parse(template)
        self.serial_connection_settings = self.dom.xpath('//serial_server/connection_settings/*')
        for item in serial_connection_settings:
            self.baud_rate = baud_rate

    def handle(self, sock, address):
        """
        Main handler for the serial server. Does logging of messages parsed.
        :return:
        """
        sock.settimeout(self.timeout)
        session = conpot_core.get_session('serial_server', address[0], address[1])

        self.start_time = time.time()
        logger.info('New Serial-server connection from {0}:{1}. ({2})'.format(address[0], address[1], session.id))
        session.add_event({'type': 'NEW_CONNECTION'})

    def start(self, host, port):
        """
        Start the serial server
        :param host: host IP address - string
        :param port: port number - int
        """
        connection = (host, port)
        self.server = StreamServer(connection, self.handle)
        logger.info('Serial server started on: {0}'.format(connection))
        self.server.start()

    def stop(self):
        """
        Stop the serial server
        :return:
        """
        self.server.stop()


class Redirector(object):
    def __init__(self, serial_instance, socket, debug=False):
        self.serial = serial_instance
        self.socket = socket
        self._write_lock = threading.Lock()
        self.rfc2217 = serial.rfc2217.PortManager(
            self.serial,
            self,
            logger=logging.getLogger('rfc2217.server') if debug else None)
        self.log = logging.getLogger('redirector')

    def statusline_poller(self):
        self.log.debug('status line poll thread started')
        while self.alive:
            time.sleep(1)
            self.rfc2217.check_modem_lines()
        self.log.debug('status line poll thread terminated')

    def shortcircuit(self):
        """connect the serial port to the TCP port by copying everything
           from one side to the other"""
        self.alive = True
        self.thread_read = threading.Thread(target=self.reader)
        self.thread_read.daemon = True
        self.thread_read.name = 'serial->socket'
        self.thread_read.start()
        self.thread_poll = threading.Thread(target=self.statusline_poller)
        self.thread_poll.daemon = True
        self.thread_poll.name = 'status line poll'
        self.thread_poll.start()
        self.writer()

    def reader(self):
        """loop forever and copy serial->socket"""
        self.log.debug('reader thread started')
        while self.alive:
            try:
                data = self.serial.read(self.serial.in_waiting or 1)
                if data:
                    # escape outgoing data when needed (Telnet IAC (0xff) character)
                    self.write(serial.to_bytes(self.rfc2217.escape(data)))
            except socket.error as msg:
                self.log.error('{}'.format(msg))
                # probably got disconnected
                break
        self.alive = False
        self.log.debug('reader thread terminated')

    def write(self, data):
        """thread safe socket write with no data escaping. used to send telnet stuff"""
        with self._write_lock:
            self.socket.sendall(data)

    def writer(self):
        """loop forever and copy socket->serial"""
        while self.alive:
            try:
                data = self.socket.recv(1024)
                if not data:
                    break
                self.serial.write(serial.to_bytes(self.rfc2217.filter(data)))
            except socket.error as msg:
                self.log.error('{}'.format(msg))
                # probably got disconnected
                break
        self.stop()

    def stop(self):
        """Stop copying"""
        self.log.debug('stopping')
        if self.alive:
            self.alive = False
            self.thread_read.join()
            self.thread_poll.join()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description="RFC 2217 Serial to Network (TCP/IP) redirector.",
        epilog="""\
NOTE: no security measures are implemented. Anyone can remotely connect
to this service over the network.

Only one connection at once is supported. When the connection is terminated
it waits for the next connect.
""")

    parser.add_argument('SERIALPORT')

    parser.add_argument(
        '-p', '--localport',
        type=int,
        help='local TCP port, default: %(default)s',
        metavar='TCPPORT',
        default=2217)

    parser.add_argument(
        '-v', '--verbose',
        dest='verbosity',
        action='count',
        help='print more diagnostic messages (option can be given multiple times)',
        default=0)

    args = parser.parse_args()

    # connect to serial port
    ser = serial.serial_for_url(args.SERIALPORT, do_not_open=True)
    ser.timeout = 3     # required so that the reader thread can exit
    # reset control line as no _remote_ "terminal" has been connected yet
    ser.dtr = False
    ser.rts = False

    logging.info("Initialized RFC 2217 TCP/IP to Serial redirector")

    try:
        ser.open()
    except serial.SerialException as e:
        logging.error("Could not open serial port {}: {}".format(ser.name, e))
        sys.exit(1)

    logging.info("Serving serial port: {}".format(ser.name))
    settings = ser.get_settings()
    # start the stream server
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('', args.localport))
    srv.listen(1)
    logging.info("TCP/IP port: {}".format(args.localport))
    # handler
    while True:
        try:
            client_socket, addr = srv.accept()
            logging.info('Connected by {}:{}'.format(addr[0], addr[1]))
            client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            ser.rts = True
            ser.dtr = True
            # enter network <-> serial loop
            r = Redirector(
                ser,
                client_socket,
                args.verbosity > 0)
            try:
                r.shortcircuit()
            finally:
                logging.info('Disconnected')
                r.stop()
                client_socket.close()
                ser.dtr = False
                ser.rts = False
                # Restore port settings (may have been changed by RFC 2217
                # capable client)
                ser.apply_settings(settings)
        except KeyboardInterrupt:
            sys.stdout.write('\n')
            break
        except socket.error as msg:
            logging.error(str(msg))

    logging.info('--- exit ---')
