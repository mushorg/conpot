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
import datetime

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


#class MockArgs(object):
#    def __init__(self):
#        self.www = "conpot/www/"


class TestBase(unittest.TestCase):

    def setUp(self):
        self.snmp_host = '127.0.0.1'
        self.snmp_port = 1337
        self.log_queue = Queue()
        self.dyn_rsp = DynamicResponder()
        self.http_server = web_server.HTTPServer('127.0.0.1',
                                                 8080,
                                                 'conpot/templates/default.xml',
                                                 self.log_queue,
                                                 'conpot/templates/www/default/',
                                                 self.snmp_port)

        self.http_worker = gevent.spawn(self.http_server.start)
        dom = etree.parse('conpot/templates/default.xml')
        mibs = dom.xpath('//conpot_template/snmp/mibs/*')
        #only enable snmp server if we have configuration items
        if not mibs:
            raise Exception("No configuration for SNMP server")
        else:
            self.snmp_server = command_responder.CommandResponder(self.snmp_host,
                                                                  self.snmp_port,
                                                                  self.log_queue,
                                                                  os.getcwd(),
                                                                  self.dyn_rsp)

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
        self.http_server.cmd_responder.httpd.shutdown()
        self.http_server.cmd_responder.httpd.server_close()

    def test_http_request_base(self):
        """
        Objective: Test if http service delivers data on request
        """

        ret = requests.get("http://127.0.0.1:8080/tests/unittest_base.html")
        self.assertIn('ONLINE', ret.text, "Could not retrieve expected data from test output.")

    def test_http_backend_snmp(self):
        """
        Objective: Test if http backend is able to retrieve data from SNMP
        """

        # retrieve configuration from xml
        dom = etree.parse('conpot/templates/default.xml')

        # check for proper snmp support
        sysName = dom.xpath('//conpot_template/snmp/mibs/mib[@name="SNMPv2-MIB"]/symbol[@name="sysName"]/value')
        if sysName:
            assert_reference = sysName[0].xpath('./text()')[0]
        else:
            assert_reference = None

        if assert_reference is not None:
            ret = requests.get("http://127.0.0.1:8080/tests/unittest_snmp.html")
            self.assertIn(assert_reference, ret.text, "Could not find SNMP value in test output.")
        else:
            raise Exception("Assertion failed. Reference OID 'sysName' not found in SNMP template.")

    def test_http_backend_tarpit(self):
        """
        Objective: Test if http tarpit delays responses properly
        """

        # retrieve configuration from xml
        dom = etree.parse('conpot/templates/default.xml')

        # check for proper tarpit support
        tarpit = dom.xpath('//conpot_template/http/htdocs/node[@name="/tests/unittest_tarpit.html"]/tarpit')

        if tarpit:
            tarpit_delay = tarpit[0].xpath('./text()')[0]

            # requesting file via HTTP along with measuring the timedelta
            dt_req_start = datetime.datetime.now()
            requests.get("http://127.0.0.1:8080/tests/unittest_tarpit.html")
            dt_req_delta = datetime.datetime.now() - dt_req_start

            # check if the request took at least the expected delay to be processed
            self.assertLessEqual(int(tarpit_delay),
                                 dt_req_delta.seconds,
                                 "Expected delay: >= {0} seconds. Actual delay: {1} seconds".format(tarpit_delay,
                                                                                            dt_req_delta.seconds))
        else:
            raise Exception("Assertion failed. Tarpit delay not found in HTTP template.")
