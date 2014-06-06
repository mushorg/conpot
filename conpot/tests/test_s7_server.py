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

from conpot.protocols.s7comm.s7_server import S7Server
from conpot.tests.helpers import s7comm_client

import conpot.core as conpot_core


class TestBase(unittest.TestCase):

    def setUp(self):
        self.databus = conpot_core.get_databus()
        self.databus.initialize('conpot/templates/default.xml')
        S7_instance = S7Server('conpot/templates/default.xml')
        self.S7_server = S7_instance.get_server('localhost', 0)
        self.S7_server.start()
        self.server_port = self.S7_server.server_port

    def tearDown(self):
        self.S7_server.stop()

    def test_s7(self):
        """
        Objective: Test if the S7 server returns the values expected.
        """
        src_tsaps = (0x100, 0x200)
        dst_tsaps = (0x102, 0x200, 0x201)
        s7_con = s7comm_client.s7('127.0.0.1', self.server_port)
        res = None
        for src_tsap in src_tsaps:
            for dst_tsap in dst_tsaps:
                try:
                    s7_con.src_tsap = src_tsap
                    s7_con.dst_tsap = dst_tsap
                    res = src_tsap, dst_tsap
                    break
                except s7comm_client.S7ProtocolError:
                    continue
            if res:
                break
        s7_con.src_ref = 10
        s7_con.s.settimeout(s7_con.timeout)
        s7_con.s.connect((s7_con.ip, s7_con.port))
        s7_con.Connect()
        identities = s7comm_client.GetIdentity('127.0.0.1', self.server_port, res[0], res[1])

        dic = {
            17: {1: "v.0.0"},
            28: {
                1: "Technodrome",
                2: "Siemens, SIMATIC, S7-200",
                3: "Mouser Factory",
                4: "Original Siemens Equipment",
                5: "88111222",
                7: "IM151-8 PN/DP CPU",
                10: "",
                11: ""
            }
        }

        for line in identities:
            sec, item, val = line.split(";")
            try:
                self.assertTrue(dic[int(sec)][int(item)] == val.strip())
            except AssertionError:
                print sec, item, val
                raise
