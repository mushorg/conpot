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
import random
import conpot.utils.mac_addr
import subprocess
import re


class TestMacAddrUtil(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_mac(self):
        randmac = ":".join(
            ["%02x" % (random.randint(1, 255)) for i in range(6)])
        s = subprocess.Popen(["spoof-mac.py", "list"], stdout=subprocess.PIPE)
        line = re.findall(r'"[a-z]*[0-9]*"', s.readlines()[0])
        iface = re.findall('"[0-z]*"', line)[1].replace('"', '')
        mac_addr.change_mac(iface=iface, mac=randmac)
        self.assertTrue(check_mac(iface, randmac) is True)

if __name__ == '__main__':
    unittest.main()
