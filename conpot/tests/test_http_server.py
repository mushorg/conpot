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

from lxml import etree
from gevent.queue import Queue
from gevent import monkey
import gevent
import requests

from conpot.snmp import command_responder
from conpot.hmi import web_server

#we need to monkey patch for modbus_tcp.TcpMaster
monkey.patch_all()


class MockArgs(object):
    def __init__(self):
        self.www = "conpot/www/"
        self.www_root = "index.html"


class TestBase(unittest.TestCase):

    def setUp(self):
        self.snmp_host = '127.0.0.1'
        self.snmp_port = 1337
        self.log_queue = Queue()
        args = MockArgs()
        http_server = web_server.HTTPServer(self.log_queue, args, "127.0.0.1", 8080, self.snmp_port)
        self.http_worker = gevent.spawn(http_server.run)
        dom = etree.parse('conpot/templates/default.xml')
        mibs = dom.xpath('//conpot_template/snmp/mibs/*')
        #only enable snmp server if we have configuration items
        if not mibs:
            raise Exception("No configuration for SNMP server")
        else:
            self.snmp_server = command_responder.CommandResponder(self.snmp_host, self.snmp_port, self.log_queue, os.getcwd())

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
        self.http_worker.kill()

    def test_http_request(self):
        # TODO: This is a bit ugly...
        gevent.sleep(1)
        ret = requests.get("http://127.0.0.1:8080")
        self.assertIn("Siemens, SIMATIC, S7-200", ret.text)