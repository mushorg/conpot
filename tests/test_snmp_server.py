# Copyright (C) 2013  Lukas Rist <glaslos@gmail.com>
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

from lxml import etree

from gevent.queue import Queue
from gevent import monkey

from modules import snmp_client
from modules import snmp_command_responder

#we need to monkey patch for modbus_tcp.TcpMaster
monkey.patch_all()


class TestBase(unittest.TestCase):

    class MockConfig(object):
        def __init__(self):
            self.snmp_host = "127.0.0.1"
            self.snmp_port = 1337

    def setUp(self):
        self.log_queue = Queue()
        dom = etree.parse('templates/default.xml')
        mibs = dom.xpath('//conpot_template/snmp/mibs/*')
        #only enable snmp server if we have configuration items
        if not mibs:
            raise Exception("No configuration for SNMP server")
        else:
            self.snmp_server = snmp_command_responder.CommandResponder(self.log_queue, server_config=self.MockConfig())

        for mib in mibs:
            mib_name = mib.attrib['name']
            for symbol in mib:
                symbol_name = symbol.attrib['name']
                value = symbol.xpath('./value/text()')[0]
                self.snmp_server.register(mib_name, symbol_name, value)
        self.snmp_server.snmpEngine.transportDispatcher.start()

    def tearDown(self):
        self.snmp_server.snmpEngine.transportDispatcher.stop()

    def mock_callback(self, sendRequestHandle, errorIndication, errorStatus, errorIndex, varBindTable, cbCtx):
        self.result = None
        if errorIndication:
            self.result = errorIndication
        elif errorStatus:
            self.result = errorStatus.prettyPrint()
        else:
            for oid, val in varBindTable:
                self.result = val.prettyPrint()

    def test_snmp(self):
        client = snmp_client.SNMPClient(client_config=self.MockConfig())
        client.get_command(callback=self.mock_callback)
        self.assertEqual("Siemens, SIMATIC, S7-200", self.result)