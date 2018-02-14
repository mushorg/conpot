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

import gevent
from gevent import monkey

import socket
import os
import select
import sys
import time
import serial

# gevent.monkey.patch_all() - crashes -- check
# import serial.rfc2217

import logging
from lxml import etree

logger = logging.getLogger(__name__)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


_READ_ONLY = select.POLLIN # select.POLLPRI not supported by gevent


class SerialServer:
    """
    Some description - Serial to Ethernet converter
    """
    def __init__(self, config, timeout=5):

        # Get the slave settings from template
        self.name = config.xpath('@name')[0]
        self.host = config.xpath('@host')[0]
        self.port = int(config.xpath('@port')[0])

        self.device = config.xpath('serial_port/text()')[0]
        self.baudrate = int(config.xpath('baud_rate/text()')[0])
        # should be something like - serial.EIGHTBITS
        self.width = int(config.xpath('data_bits/text()')[0])
        self.parity = config.xpath('parity/text()')[0]
        self.stopbits = int(config.xpath('stop_bits/text()')[0]) #serial.STOPBITS_ONE
        self.timeout = timeout
        self.xonxoff = int(config.xpath('xonxoff/text()')[0])
        self.rts = int(config.xpath('rtscts/text()')[0])

        self.decoder = None    # Implement later
        # self.READ_ONLY = select.POLLIN | select.POLLPRI

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.settimeout(self.timeout)

        self.poller = gevent.select.poll()
        self.fd_to_socket = {}
        self.clients = []
        # self.rfc2217 = None   # Initialize later

    def start(self):
        """
        Start the serial server
        """
        try:
            self.tty = serial.Serial(self.device, self.baudrate, self.width, self.parity, self.stopbits, self.timeout, self.xonxoff, self.rts)

            # Flush the input and output
            self.tty.flushInput()
            self.tty.flushOutput()

            # connect the terminal with control lines
            # self.tty.dtr = Ture
            # self.tty.rts = Ture
            # self.rfc2217 = serial.rfc2217.PortManager(self.tty, self)

            # add the serial device to the poller
            self.poller.register(self.tty, _READ_ONLY)
            # add tty fd to the dictionary
            self.fd_to_socket[self.tty.fileno()] = self.tty
            logging.debug("Added serial port {0} at baud rate {1}".format(self.device, self.baudrate))

            self.server.bind((self.host, self.port))
            self.server.listen(5)
            self.poller.register(self.server, _READ_ONLY)
            self.fd_to_socket[self.server.fileno()] = self.server
            logging.info("Starting serial server at: {0}".format(self.server.getsockname()))
            while True:
                self.handle()

        except serial.SerialException as e:
            logging.debug("Unable to connect to serial device. Please check your serial connection config. {0}".format(e))
            sys.exit(1)
        except socket.error as e:
            logging.debug("Socket Error: {0}".format(e))
        finally:
            self.stop()

    def stop(self):
        """
        Stop the serial server
        """
        logging.info("Stopping the serial-server {0}:{1}".format(self.host, self.port))
        for client in self.clients:
            client.close()
        logging.info("Closing the serial connection for {0} on {1}".format(self.name, self.device))
        self.tty.close()
        self.server.close()

    def add_client(self, client):
        logging.info("The fd is : {0}".format(self.fd_to_socket))
        logging.info("New Connection from {0}".format(client.getpeername()))
        client.setblocking(0)   # why?
        # Add the client to a dictionary of file descriptors
        self.fd_to_socket[client.fileno()] = client
        # Add client to the list clients
        self.clients.append(client)
        # register with the poller
        self.poller.register(client, _READ_ONLY)

    def remove_client(self, client, reason='unknown'):
        try:
            name = client.getpeername()
            logging.info("Disconnecting client {0} : {1}".format(name, reason))
        except:
            # unable to fetch the peername
            logging.info("Disconnecting client with FD {0} : {1}".format(client.fileno(), reason))
        self.poller.unregister(client)
        self.clients.remove(client)
        client.close()

    def handle(self):
        # Trying to IO multiplex things here.
        events = self.poller.poll(5) # poll timeout is 5
        for fd, flag in events:
            # Get the socket from the fd dict
            s = self.fd_to_socket[fd]
            # TODO: add more info here
            if flag & select.POLLHUP:
                self.remove_client(s, 'HUP')
            elif flag & select.POLLERR:
                self.remove_client(s, 'Received error')
            elif flag & (_READ_ONLY):
                # readable socket is ready of accepting a connection.
                # check to see if the tty is the readable or server is readable
                if s is self.server:
                    connection, client_address = s.accept()
                    self.add_client(connection)
                # serial port is readable; Read data from serial port
                elif s is self.tty:
                    data = s.read(1024)
                    for client in self.clients:
                        client.send(data)
                # Need to fetch data from client instead!
                else:
                    # the famous recv blocking call from the client
                    data = s.recv(1024)
                    # check if client has data
                    if data:
                        # write to serial device
                        try:
                            self.tty.write(data)
                        except serial.SerialTimeoutException as e:
                            logging.info("Serial Timeout Reached".format(e))
                    else:
                        logging.info("s is {0}".format(s))
                        # No data supplied
                        # Interpret empty result as closed connection - close the connection
                        self.remove_client(s, 'Got no data')


# For debugging
if __name__ == '__main__':

    template_directory = os.getcwd() + '/../../templates/serial_server/serial_server/'
    e = etree.parse(template_directory + 'serial_server.xml').getroot()
    # Find all the serial connections
    serial_configs = e.findall('server')
    for config in serial_configs:
        server = SerialServer(config)
        try:
            server.start()
        except:
            raise
