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
from conpot.snmp.dynrsp import DynamicResponder
from conpot.http import web_server

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
        self.dyn_rsp = DynamicResponder()
        http_server = web_server.HTTPServer('127.0.0.1', 8080, 'conpot/templates/default.xml', self.log_queue, 'conpot/templates/www/default', self.snmp_port)
        self.http_worker = gevent.spawn(http_server.start)
        dom = etree.parse('conpot/templates/default.xml')
        mibs = dom.xpath('//conpot_template/snmp/mibs/*')
        #only enable snmp server if we have configuration items
        if not mibs:
            raise Exception("No configuration for SNMP server")
        else:
            self.snmp_server = command_responder.CommandResponder(self.snmp_host, self.snmp_port, self.log_queue, os.getcwd(), self.dyn_rsp)

        for mib in mibs:
            mib_name = mib.attrib['name']
            for symbol in mib:
                symbol_name = symbol.attrib['name']

                # retrieve instance from template
                if 'instance' in symbol.attrib:
                    # convert instance to (int-)tuple
                    symbol_instance = symbol.attrib['instance'].split('.')
                    symbol_instance = tuple(map(int, symbol_instance))
                else:
                    # use default instance (0)
                    symbol_instance = (0,)

                # retrieve value from template
                value = symbol.xpath('./value/text()')[0]

                # retrieve engine from template
                if len(symbol.xpath('./engine')) > 0:
                    engine_type = symbol.find('./engine').attrib['type']
                    engine_aux = symbol.findtext('./engine')
                else:
                    # disable dynamic responses (static)
                    engine_type = 'static'
                    engine_aux = ''

                # register this MIB instance to the command responder
                self.snmp_server.register(mib_name, symbol_name, symbol_instance, value, engine_type, engine_aux)

        self.snmp_server.snmpEngine.transportDispatcher.start()

    def tearDown(self):
        self.snmp_server.snmpEngine.transportDispatcher.stop()
        self.http_worker.kill()

    def test_http_request(self):

        # TODO: johnnykv: This is a bit ugly...
        # TODO: creolis:  A bit more flexible now, but still ugly...

        # get reference value from template
        dom = etree.parse('conpot/templates/default.xml')
        sysName = dom.xpath('//conpot_template/snmp/mibs/mib[@name="SNMPv2-MIB"]/symbol[@name="sysName"]/value')

        if sysName:
            assert_reference = sysName[0].xpath('./text()')[0]

        gevent.sleep(1)
        ret = requests.get("http://127.0.0.1:8080/index.html")

        if assert_reference:
            print "asserting {0}".format(assert_reference)
            self.assertIn(assert_reference, ret.text)
        else:
            raise Exception("Assertion failed. Reference OID 'sysName' missing.")
