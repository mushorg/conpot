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

# import gevent.monkey
# gevent.monkey.patch_all()

import unittest
import os
from lxml import etree
from gevent.server import StreamServer

import serial

DATA = b'Hello\n'


import conpot
import conpot.core as conpot_core
from conpot.emulators.serial.serial_server import SerialServer

package_directory = os.path.dirname(os.path.abspath(conpot.__file__))


class TestSerial(unittest.TestCase):
    """Test to check if serial server is working correctly"""

    def setUp(self):
        # clean up before we start...
        conpot_core.get_sessionManager().purge_sessions()
        # make paths platform-independent
        template = reduce(os.path.join, 'conpot/templates/serial_server/template.xml'.split('/'))
        serial_template = reduce(os.path.join, 'conpot/templates/serial_server/serial_server/serial_server.xml'.split('/'))
        server_config = etree.parse(serial_template).getroot().findall('server')
        # Modifying template object for testing purposes
        server_config[0][0].text = 'loop://'  # Accommodate serial loopback interface
        server_config[0].attrib['host'] = '127.0.0.1'  # The listener port would be 6500
        server_config[0].attrib['name'] = 'Test'
        # We are find with the remaining settings
        self.serial_server = SerialServer(server_config)
        self.serial_server.start()

        self.databus = conpot_core.get_databus()
        self.databus.initialize(template)

    def tearDown(self):
        self.serial_server.stop()
        # tidy up (again)...
        conpot_core.get_sessionManager().purge_sessions()

    def test_single_client_connect(self):
        """test to check whether a single client is able to connect to serial server"""
        pass

    def test_on_multiple_clients_connect(self):
        """
        Objective: Benchmark the total number of requests/response serial server can process under heavy traffic
        from multiple clients. Gives an idea regarding asynchronous i/o capability.
        """
        pass


if __name__ == '__main__':
    unittest.main()