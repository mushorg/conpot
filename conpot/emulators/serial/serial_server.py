# Copyright (C) 2018  Abhinav Saxena <xandfury@gmail.com>
# Institute of Informatics and Communication, University of Delhi, South Campus
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

# import gevent
# from gevent import monkey

import socket
import os
import select
import sys
import serial

# gevent.monkey.patch_all() # unstable behaviour -- recheck
# import serial.rfc2217

import logging
from lxml import etree

logger = logging.getLogger(__name__)

# logging.basicConfig(stream=sys.stdout, level=logging.INFO)

import conpot.core as conpot_core


class SerialServer:
    """
    Serial over IP Converter -- Not RFC2217 complaint.
    Allows connecting a serial device to *any* number of TCP clients.

    (Serial Device -- RS232 or similar --) <-->  Conpot  <--> (-- Network -- Attacker)

    :param: XML template object having information regarding host, port, serial device, baud rate etc.
    """
    def __init__(self, args, decoder=None):
        self._parse_template_obj(args, decoder)  # setup the config for one serial device per template object
        # TODO: Figure out a better way to parse the template. Using a template object is probably not a good idea
        self._setup_tty()  # setup the serial device
        self.listener = None
        self._create_srv_socket((self.host, self.port))
        self.sockets = {
            self.listener.fileno(): self.listener,
            self.tty.fileno(): self.tty
        }

        self.addresses = {}   # store the client sockets info
        self.bytes_to_send = {}  # buffer to store data that is to be sent from serial device - for decoder
        self.bytes_received = {}  # buffer to store data received from clients - for decoder

        # Setup the poller
        self.poller = select.poll()  # gevent.select.poll() - Since we are monkey_patching - unstable behaviour
        self.poller.register(self.listener, select.POLLIN)
        self.poller.register(self.tty, select.POLLIN)
        # self.rfc2217 = NotImplemented  # Initialize later

    def _parse_template_obj(self, config, decoder):
        # Get the slave settings from template
        self.name = config.xpath('@name')[0]
        self.host = config.xpath('@host')[0]
        self.port = int(config.xpath('@port')[0])
        # Get the slave settings from template
        self.device = config.xpath('serial_port/text()')[0]
        self.baud_rate = int(config.xpath('baud_rate/text()')[0])
        self.width = int(config.xpath('data_bits/text()')[0])
        self.parity = config.xpath('parity/text()')[0]
        self.stop_bits = int(config.xpath('stop_bits/text()')[0])
        self.xon = int(config.xpath('xonxoff/text()')[0])
        self.rts = int(config.xpath('rtscts/text()')[0])
        self.time_out = 0  # serial connection read timeout
        self.serial_id = self.name.lower().replace(' ', '_')
        if decoder:
            namespace, _classname = decoder.rsplit('.', 1)
            module = __import__(namespace, fromlist=[_classname])
            _class = getattr(module, _classname)
            self.decoder = _class()
        else:
            self.decoder = None
        logger.info('On serial server %s - using decoder: %s', self.name, self.decoder)

    def _setup_tty(self):
        """Setup and connect to the serial device specified"""
        self.tty = serial.serial_for_url(self.device,
                                         self.baud_rate,
                                         self.width,
                                         self.parity,
                                         self.stop_bits,
                                         self.time_out,
                                         self.xon,
                                         self.rts,
                                         do_not_open=True)
        try:
            self.tty.open()
            logger.info('Connected to %s device on serial port %s', self.name, self.device)
        except serial.SerialException:
            logger.exception('Could not open serial port')
            sys.exit(3)
        # Flush input and output
        self.tty.flushInput()
        self.tty.flushOutput()

    # Some basic utility functions
    def _create_srv_socket(self, connection):
        """Build and return a listening server socket."""
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(connection)
        self.listener.listen(64)
        # self.listener.settimeout(timeout)

    def start(self):
        """Start the Serial Server"""
        logger.info('Starting serial server at: %s', self.listener.getsockname())
        try:
            # TODO: Add authentication here
            self.handle()
        except socket.timeout:
            logger.exception('Serial server socket timeout')
        except socket.error:
            logger.exception('Serial server socket error')
        finally:
            self.stop()

    def _add_client(self, sock, address, session):
        """Add/configure a connected client socket"""
        sock.setblocking(False)  # force socket.timeout in worst case
        self.sockets[sock.fileno()] = sock  # Add client to the dictionary
        self.addresses[sock] = address  # store the address of client
        session.add_event({'type': 'NEW_CONNECTION'})
        self.poller.register(sock, select.POLLIN)

    def _remove_client(self, sock, session, reason='UNKNOWN'):
        """Remove a connected client"""
        conn = self.addresses.pop(sock, None)
        logger.info('Disconnecting client %s : %s on %s', conn, reason, self.name)
        session.add_event({'type': reason})
        self.poller.unregister(sock)
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()

    def _build_request(self, sock, raw_data, session):
        # build request for nice request/response logs
        # having and adding to buffers only required when we need request/response logs
        if self.decoder:
            if sock in self.bytes_received:
                self.bytes_received[sock] += raw_data
            else:
                self.bytes_received[sock] = raw_data
            logger.debug('Received data from client: %s - %s', self.addresses[sock], self.bytes_received[sock])
        else:
            self.bytes_received[sock] = raw_data  # make sure poller does not misbehave
            logger.info('Received data from client: %s - %s', self.addresses[sock], raw_data.encode('string-escape'))
            session.add_event({'raw_request': raw_data.encode('string-escape'), 'raw_response': ''})

    def _build_response(self, sock, raw_data, session):
        # build response for nice request/response logs
        # having and adding to buffers only required when we need request/response logs
        if self.decoder:
            if sock in self.bytes_to_send:
                self.bytes_to_send[sock] += raw_data
            else:
                self.bytes_to_send[sock] = raw_data
            logger.debug('Response data from serial device: %s - %s', self.device, self.bytes_to_send[sock])
        else:
            self.bytes_to_send[sock] = raw_data  # make sure poller does not misbehave
            logger.info('Response data from serial device: %s - %s', self.device, raw_data.encode('string-escape'))
            session.add_event({'raw_request': '', 'raw_response': raw_data.encode('string-escape')})

    def _parse_request_response(self, client_sock, session):
        """Function that checks whether the packet in buffers is valid, logs request and response"""
        if self.decoder:
            try:
                if self.decoder.validate_crc(self.bytes_received[client_sock]) and \
                        self.decoder.validate_crc(self.bytes_to_send[self.tty]):
                    rb = self.decoder.decode(self.bytes_received.pop(client_sock, b''))
                    sb = self.decoder.decode(self.bytes_to_send.pop(self.tty, b''))
                    logger.info('Traffic on serial device - request: %s,\n response: %s on serial server %s', rb, sb,
                                self.name)
                    session.add_event({'request': rb, 'response': sb})
            except Exception:
                logger.exception('On serial server %s - error occurred while decoding', self.name)

    def _all_events(self):
        while True:
            for fd, event in self.poller.poll(500):  # wait 500 milliseconds before selecting
                yield fd, event

    def handle(self):
        """Handle connections and manage the poll."""
        session = None
        for fd, event in self._all_events():
            sock = self.sockets[fd]
            # Socket closed: remove from the DS
            if event & (select.POLLHUP | select.POLLERR | select.POLLNVAL):
                address = self.addresses.pop(sock)
                rb = self.bytes_received.pop(sock, b'')
                sb = self.bytes_to_send.pop(sock, b'')
                if rb:
                    logger.info('On serial server %s - %s Client sent {} but then closed', address, rb, self.name)
                    self._remove_client(sock, session, 'CONNECTION_QUIT')
                elif sb:
                    logger.info('On serial server %s - %s Client closed before we sent {}', address, sb, self.name)
                    self._remove_client(sock, session, 'CONNECTION_LOST')
                else:
                    logger.info('On serial server %s - %s Client closed socket normally', address, self.name)
                self.poller.unregister(fd)
                # close the databus session
                session.set_ended()
                del self.sockets[fd]

            # Incoming data from either a serial device or a client
            elif event & select.POLLIN:
                # New Socket: A new client has connected
                if sock is self.listener:
                    sock, address = sock.accept()
                    # For new client, start the databus session.
                    session = conpot_core.get_session(self.serial_id, address[0], address[1])
                    logger.info('New Connection from %s:%s on serial server %s. (%s)', address[0], address[1],
                                self.serial_id, session.id)
                    self._add_client(sock, address, session)

                # check whether sock is client or serial device
                elif sock is self.tty:
                    try:
                        # read from serial device
                        data = sock.read(80)
                        if not data:
                            raise serial.SerialException
                        else:
                            self._build_response(sock, data, session)
                            for client in self.addresses.keys():
                                client.send(data)
                                if self.decoder: self._parse_request_response(client, session)
                    except socket.timeout:
                        logger.exception('Client Timed out on serial server %s', self.name)
                    except socket.error:
                        logger.exception('Socket error on serial server %s', self.name)
                    except Exception:
                        logger.exception('Exception occurred while reading serial device: %s', self.name)
                        sys.exit(3)

                else:
                    # sock is a client sending in some data
                    data = sock.recv(80)
                    if not data:  # end of file
                        # remove the client and close the databus session
                        self._remove_client(sock, session, 'CONNECTION_TERMINATED')
                        # next poll() would be POLLNVAL, and thus cleanup
                    else:
                        self._build_request(sock, data, session)
                        try:
                            self.tty.write(data)
                        except serial.SerialTimeoutException:
                            logger.exception('Serial Timeout Reached')

    def stop(self):
        """Stop the Serial Server"""
        logger.info('Stopping serial-server %s:%s', self.host, self.port)
        for client in self.addresses.keys():
            client.close()
        logger.info('Closing the serial connection for %s on %s', self.name, self.device)
        self.tty.close()
        self.listener.shutdown(socket.SHUT_RDWR)
        self.listener.close()


# For debugging
if __name__ == '__main__':
    template_directory = os.getcwd() + '/../../templates/serial_server/serial_server/'
    e = etree.parse(template_directory + 'serial_server.xml').getroot()
    sys.path.append('../misc')  # for decoder
    from modbus_rtu_decoder import ModbusRtuDecoder  # testing for modbus rtu slave device
    # Find all the serial connections
    serial_configs = e.findall('server')
    for config in serial_configs:
        server = SerialServer(config, ModbusRtuDecoder)
        try:
            server.start()
        except Exception:
            logging.exception('Error Occurred!')
            sys.exit(1)
