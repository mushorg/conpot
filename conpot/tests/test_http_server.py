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

from gevent import monkey

monkey.patch_all()
import unittest
import datetime
import conpot
import os
from lxml import etree
import requests
from gevent import socket, sleep
from conpot.protocols.http import web_server
from conpot.utils.greenlet import spawn_test_server, teardown_test_server
import conpot.core as conpot_core


class TestHTTPServer(unittest.TestCase):
    def setUp(self):
        self.http_server, self.http_worker = spawn_test_server(
            web_server.HTTPServer, "default", "http"
        )
        sleep(0.5)

    def tearDown(self):
        teardown_test_server(self.http_server, self.http_worker)

    def test_http_request_base(self):
        """
        Objective: Test if http service delivers data on request
        """
        ret = requests.get(
            "http://127.0.0.1:{0}/tests/unittest_base.html".format(
                self.http_server.server_port
            )
        )
        self.assertIn(
            "ONLINE", ret.text, "Could not retrieve expected data from test output."
        )

    def test_http_backend_databus(self):
        """
        Objective: Test if http backend is able to retrieve data from databus
        """
        sysName = conpot_core.get_databus().get_value("sysName")

        if sysName:
            ret = requests.get(
                "http://127.0.0.1:{0}/tests/unittest_databus.html".format(
                    self.http_server.server_port
                )
            )
            self.assertIn(
                sysName,
                ret.text,
                "Could not find databus entity 'sysName' (value '{0}') in output.".format(
                    sysName
                ),
            )
        else:
            raise Exception(
                "Assertion failed. Key 'sysName' not found in databus definition table."
            )

    def test_http_backend_tarpit(self):
        """
        Objective: Test if http tarpit delays responses properly
        """
        # retrieve configuration from xml
        dir_name = os.path.dirname(conpot.__file__)
        dom = etree.parse(dir_name + "/templates/default/http/http.xml")

        # check for proper tarpit support
        tarpit = dom.xpath(
            '//http/htdocs/node[@name="/tests/unittest_tarpit.html"]/tarpit'
        )

        if tarpit:
            tarpit_delay = tarpit[0].xpath("./text()")[0]

            # requesting file via HTTP along with measuring the timedelta
            dt_req_start = datetime.datetime.now()
            requests.get(
                "http://127.0.0.1:{0}/tests/unittest_tarpit.html".format(
                    self.http_server.server_port
                )
            )
            dt_req_delta = datetime.datetime.now() - dt_req_start

            # check if the request took at least the expected delay to be processed
            self.assertLessEqual(
                int(tarpit_delay),
                dt_req_delta.seconds,
                "Expected delay: >= {0} seconds. Actual delay: {1} seconds".format(
                    tarpit_delay, dt_req_delta.seconds
                ),
            )
        else:
            raise AssertionError(
                "Assertion failed. Tarpit delay not found in HTTP template."
            )

    def test_http_subselect_trigger(self):
        """
        Objective: Test if http subselect triggers work correctly
        """
        ret = requests.get(
            "http://127.0.0.1:{0}/tests/unittest_subselects.html?action=unit&subaction=test".format(
                self.http_server.server_port
            )
        )
        self.assertIn(
            "SUCCESSFUL", ret.text, "Trigger missed. An unexpected page was delivered."
        )

    def test_do_TRACE(self):
        """
        Objective: Test the web server with a trace request
        """
        # requests has no trace method.. So resorting to the good'ol socket - sending raw data
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", self.http_server.server_port))
        s.sendall(b"TRACE /index.html HTTP/1.1\r\nHost: localhost\r\n\r\n")
        data = s.recv(1024)
        # FIXME: Omitting the time etc from data - mechanism to check them needed as well?
        self.assertIn(b"HTTP/1.1 200 OK", data)
        # test for 501 - Disable TRACE method
        self.http_server.cmd_responder.httpd.disable_method_trace = True
        s.sendall(b"TRACE /index.html HTTP/1.1\r\nHost: localhost\r\n\r\n")
        data = s.recv(1024)
        s.close()
        self.assertIn(b"501", data)

    def test_do_HEAD(self):
        """
        Objective: Test the web server by sending a HTTP HEAD request.
        Should be responded back by the valid HTTP headers
        """
        ret = requests.head(
            "http://127.0.0.1:{0}/tests/unittest_subselects.html?action=unit&subaction=test".format(
                self.http_server.server_port
            )
        )
        self.assertTrue(
            ret.status_code == 200 and ret.headers["Content-Length"] == "370"
        )

        # Test for 404
        ret = requests.head(
            "http://127.0.0.1:{0}/tests/random_page_does_not_exists.html".format(
                self.http_server.server_port
            )
        )
        self.assertEqual(ret.status_code, 404)

        # test for 501 - Disable HEAD method
        self.http_server.cmd_responder.httpd.disable_method_head = True
        ret = requests.head(
            "http://127.0.0.1:{0}/tests/unittest_subselects.html?action=unit&subaction=test".format(
                self.http_server.server_port
            )
        )
        self.assertEqual(ret.status_code, 501)

    def test_do_OPTIONS(self):
        """
        Objective: Test the web server by sending a valid OPTIONS HTTP request
        """
        ret = requests.options(
            "http://127.0.0.1:{0}/tests/unittest_subselects.html?action=unit&subaction=test".format(
                self.http_server.server_port
            )
        )
        self.assertEqual((ret.headers["allow"]), "GET,HEAD,POST,OPTIONS,TRACE")
        # test for 501 - Disable OPTIONS method
        self.http_server.cmd_responder.httpd.disable_method_options = True
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", self.http_server.server_port))
        s.sendall(b"OPTIONS /index.html HTTP/1.1\r\nHost: localhost\r\n\r\n")
        data = s.recv(1024)
        self.assertIn(b"501", data)

    def test_do_POST(self):
        """
        Objective: send a POST request to a invalid URI. Should get a 404 response
        """
        payload = {"key1": "value1", "key2": "value2"}
        ret = requests.post(
            "http://127.0.0.1:{0}/tests/demo.html".format(self.http_server.server_port),
            data=payload,
        )
        self.assertEqual(ret.status_code, 404)

    def test_not_implemented_method(self):
        """
        Objective: PUT HTTP method is not implemented in Conpot, should raise 501
        """
        payload = b"PUT /index.html HTTP/1.1\r\nHost: localhost\r\n\r\n"
        ret = requests.put(
            "http://127.0.0.1:{0}/tests/demo.html".format(self.http_server.server_port),
            data=payload,
        )
        self.assertEqual(ret.status_code, 501)
