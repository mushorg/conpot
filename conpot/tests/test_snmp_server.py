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


import os
import unittest
from datetime import datetime

from lxml import etree
from gevent.queue import Queue
from gevent import monkey

from pysnmp.proto import rfc1902

#we need to monkey patch for modbus_tcp.TcpMaster
monkey.patch_all()
from conpot.snmp import snmp_client
from conpot.snmp import command_responder


class TestBase(unittest.TestCase):
    def setUp(self):
        self.host = '127.0.0.1'
        self.port = 1337
        self.log_queue = Queue()
        dom = etree.parse('conpot/templates/default.xml')
        mibs = dom.xpath('//conpot_template/snmp/mibs/*')
        #only enable snmp server if we have configuration items
        if not mibs:
            raise Exception("No configuration for SNMP server")
        else:
            self.snmp_server = command_responder.CommandResponder(self.host, self.port, self.log_queue, os.getcwd())

        for mib in mibs:
            mib_name = mib.attrib['name']
            for symbol in mib:
                symbol_name = symbol.attrib['name']
                try:
                    symbol_instance = tuple(int(i) for i in symbol.attrib['instance'].split('.'))
                except KeyError:
                    symbol_instance = (0,)
                value = symbol.xpath('./value/text()')[0]
                self.snmp_server.register(mib_name, symbol_name, symbol_instance, value)
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

    def test_snmp_get(self):
        client = snmp_client.SNMPClient(self.host, self.port)
        OID = ((1, 3, 6, 1, 2, 1, 1, 1, 0), None)
        client.get_command(OID, callback=self.mock_callback)
        self.assertEqual("Siemens, SIMATIC, S7-200", self.result)
        log_item = self.log_queue.get(True, 2)
        self.assertIsInstance(log_item['timestamp'], datetime)
        self.assertEqual('127.0.0.1', log_item['remote'][0])
        self.assertEquals('snmp', log_item['data_type'])

    def test_snmp_set(self):
        client = snmp_client.SNMPClient(self.host, self.port)
        OID = ((1, 3, 6, 1, 2, 1, 1, 6, 0), rfc1902.OctetString('test comment'))
        client.set_command(OID, callback=self.mock_callback)
        client.get_command(OID, callback=self.mock_callback)

        set_log_item = self.log_queue.get(True, 5)
        self.assertEqual("test comment", self.result)
        self.assertIsInstance(set_log_item['timestamp'], datetime)
        self.assertEqual('127.0.0.1', set_log_item['remote'][0])
        self.assertEquals('snmp', set_log_item['data_type'])
        self.assertIn('SNMPv3 Set:', set_log_item['data'][0]['request'])

        get_log_item = self.log_queue.get(True, 5)
        self.assertEqual("test comment", self.result)
        self.assertIsInstance(get_log_item['timestamp'], datetime)
        self.assertEqual('127.0.0.1', get_log_item['remote'][0])
        self.assertEquals('snmp', get_log_item['data_type'])
        self.assertIn('SNMPv3 Get:', get_log_item['data'][0]['request'])
