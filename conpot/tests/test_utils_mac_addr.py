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
        self.change_mac_process = subprocess.Popen(
            ["ip", "li", "delete", "dummy", "type", "dummy"],
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
        )

    def tearDown(self):
        self.change_mac_process.terminate()

    @unittest.skip("shunt to a later phase")
    def test_mac(self):
        """
        Objective: Test if the spoofer is able to change MAC address
        """
        testmac = b"00:de:ad:be:ef:00"
        iface = b"dummy"
        # Load dummy module
        s = subprocess.Popen(
            ["modprobe", "dummy"], stderr=subprocess.STDOUT, stdout=subprocess.PIPE
        )
        # Check if dummy is loaded
        data = s.stdout.read()
        if data:
            self.skipTest("Can't create dummy device")
        # Create a dummy network interface
        subprocess.Popen(
            ["ip", "li", "add", "dummy", "type", "dummy"],
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
        )
        s = subprocess.Popen(["ip", "link", "show"], stdout=subprocess.PIPE)
        data = s.stdout.read()
        if b"dummy" in data:
            # Change mac address of dummy interface and test it
            mac_addr.change_mac(iface=iface, mac=testmac)
            flag = mac_addr._check_mac(iface, testmac)
            # Remove the dummy interface
            with self.change_mac_process:
                self.assertTrue(flag is True)
        else:
            self.skipTest("Can't change MAC address")
