# Copyright (C) 2015  Adarsh Dinesh <adarshdinesh@gmail.com>
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
import conpot.utils.mac_addr as mac_addr
import subprocess


class TestMacAddrUtil(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_mac(self):
        testmac = "00:de:ad:be:ef:00"
        iface = "dummy"
        subprocess.Popen(["modprobe", "dummy"])
        subprocess.Popen(["ip", "li", "add", "dummy", "type", "dummy"])
        mac_addr.change_mac(iface, testmac)
        s = subprocess.Popen(["ip", "link", "show"], stdout=subprocess.PIPE)
        data = s.stdout.read()
        raise Exception(data)

        flag = mac_addr.check_mac(iface, testmac)
        subprocess.Popen(["ip", "li", "delete", "dummy", "type", "dummy"])
        self.assertTrue(flag is True)

if __name__ == '__main__':
    unittest.main()
