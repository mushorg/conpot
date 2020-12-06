# Copyright (C) 2014  Lukas Rist <glaslos@gmail.com>
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
import conpot.utils.ext_ip

from gevent.pywsgi import WSGIServer
import gevent


class TestExtIPUtil(unittest.TestCase):
    def setUp(self):
        def application(environ, start_response):
            headers = [("Content-Type", "text/html")]
            start_response("200 OK", headers)
            return [b"127.0.0.1"]

        self.server = WSGIServer(("localhost", 8000), application)
        gevent.spawn(self.server.serve_forever)

    def tearDown(self):
        self.server.stop()

    def test_ip_verify(self):
        self.assertTrue(conpot.utils.ext_ip._verify_address("127.0.0.1") is True)

    def test_ext_util(self):
        ip_address = str(
            conpot.utils.ext_ip._fetch_data(
                urls=[
                    "http://127.0.0.1:8000",
                ]
            )
        )
        self.assertTrue(conpot.utils.ext_ip._verify_address(ip_address) is True)

    def test_fetch_ext_ip(self):
        self.assertIsNotNone(
            conpot.utils.ext_ip.get_ext_ip(urls=["https://api.ipify.org"])
        )
