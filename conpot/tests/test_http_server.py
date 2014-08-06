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

import gevent.monkey
gevent.monkey.patch_all()

import unittest
import datetime

from lxml import etree
import gevent
import requests

from conpot.protocols.http import web_server
import conpot.core as conpot_core


class TestBase(unittest.TestCase):

    def setUp(self):

        # clean up before we start...
        conpot_core.get_sessionManager().purge_sessions()

        self.http_server = web_server.HTTPServer('127.0.0.1',
                                                 0,
                                                 'conpot/templates/default.xml',
                                                 'conpot/templates/www/default/',)
        # get the assigned ephemeral port for http
        self.http_port = self.http_server.server_port
        self.http_worker = gevent.spawn(self.http_server.start)

        # initialize the databus
        self.databus = conpot_core.get_databus()
        self.databus.initialize('conpot/templates/default.xml')

    def tearDown(self):
        self.http_server.cmd_responder.httpd.shutdown()
        self.http_server.cmd_responder.httpd.server_close()

        # tidy up (again)...
        conpot_core.get_sessionManager().purge_sessions()

    def test_http_request_base(self):
        """
        Objective: Test if http service delivers data on request
        """
        ret = requests.get("http://127.0.0.1:{0}/tests/unittest_base.html".format(self.http_port))
        self.assertIn('ONLINE', ret.text, "Could not retrieve expected data from test output.")

    def test_http_backend_databus(self):
        """
        Objective: Test if http backend is able to retrieve data from databus
        """
        # retrieve configuration from xml
        dom = etree.parse('conpot/templates/default.xml')

        # retrieve reference value from configuration
        sysName = dom.xpath('//conpot_template/core/databus/key_value_mappings/key[@name="sysName"]/value')
        if sysName:
            print sysName
            assert_reference = sysName[0].xpath('./text()')[0][1:-1]
        else:
            assert_reference = None
        if assert_reference is not None:
            ret = requests.get("http://127.0.0.1:{0}/tests/unittest_databus.html".format(self.http_port))
            self.assertIn(assert_reference, ret.text,
                          "Could not find databus entity 'sysName' (value '{0}') in output.".format(assert_reference))
        else:
            raise Exception("Assertion failed. Key 'sysName' not found in databus definition table.")

    def test_http_backend_tarpit(self):
        """
        Objective: Test if http tarpit delays responses properly
        """
        # retrieve configuration from xml
        dom = etree.parse('conpot/templates/default.xml')

        # check for proper tarpit support
        tarpit = dom.xpath('//conpot_template/protocols/http/htdocs/node[@name="/tests/unittest_tarpit.html"]/tarpit')

        if tarpit:
            tarpit_delay = tarpit[0].xpath('./text()')[0]

            # requesting file via HTTP along with measuring the timedelta
            dt_req_start = datetime.datetime.now()
            requests.get("http://127.0.0.1:{0}/tests/unittest_tarpit.html".format(self.http_port))
            dt_req_delta = datetime.datetime.now() - dt_req_start

            # check if the request took at least the expected delay to be processed
            self.assertLessEqual(
                int(tarpit_delay),
                dt_req_delta.seconds,
                "Expected delay: >= {0} seconds. Actual delay: {1} seconds".format(tarpit_delay, dt_req_delta.seconds)
            )
        else:
            raise Exception("Assertion failed. Tarpit delay not found in HTTP template.")

    def test_http_subselect_trigger(self):
        """
        Objective: Test if http subselect triggers work correctly
        """
        ret = requests.get("http://127.0.0.1:{0}/tests/unittest_subselects.html?action=unit&subaction=test".format(self.http_port))
        self.assertIn('SUCCESSFUL', ret.text, "Trigger missed. An unexpected page was delivered.")