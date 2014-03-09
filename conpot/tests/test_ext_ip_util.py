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


import unittest
import conpot.utils.ext_ip


class TestExtIPUtil(unittest.TestCase):

    def setUp(self):
        self.data = """
            <html>
                <head>
                    <title>Current IP Check</title>
                </head>
                <body>Current IP Address: 127.0.0.1</body>
            </html>
        """

    def tearDown(self):
        pass

    def test_ip_verify(self):
        self.assertTrue(conpot.utils.ext_ip._verify_address("127.0.0.1") is True)

    def test_html_parser(self):
        parser = conpot.utils.ext_ip.AddressHTMLParser()
        parser.feed(self.data)
        self.assertTrue(parser.address == "127.0.0.1")

    def test_parse_method(self):
        ext_ip = conpot.utils.ext_ip._parse_html(self.data)
        self.assertTrue(ext_ip == "127.0.0.1")

    def test_ext_util(self):
        raw = conpot.utils.ext_ip._fetch_data(url="http://checkip.dyndns.org/")
        parser = conpot.utils.ext_ip.AddressHTMLParser()
        parser.feed(raw)
        self.assertTrue(conpot.utils.ext_ip._verify_address(parser.address) is True)


if __name__ == '__main__':
    unittest.main()