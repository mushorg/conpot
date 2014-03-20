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
        self.data = "127.0.0.1"

    def tearDown(self):
        pass

    def test_ip_verify(self):
        self.assertTrue(conpot.utils.ext_ip._verify_address("127.0.0.1") is True)

    def test_ext_util(self):
        ip_address = conpot.utils.ext_ip._fetch_data(urls=["http://www.telize.com/ip", ])
        self.assertTrue(conpot.utils.ext_ip._verify_address(ip_address) is True)


if __name__ == '__main__':
    unittest.main()