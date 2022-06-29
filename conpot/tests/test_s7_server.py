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
from conpot.protocols.s7comm.s7_server import S7Server
from conpot.tests.helpers import s7comm_client
from conpot.utils.greenlet import spawn_test_server, teardown_test_server


class TestS7Server(unittest.TestCase):
    def setUp(self):
        self.s7_instance, self.greenlet = spawn_test_server(
            S7Server, "default", "s7comm"
        )

        self.server_host = self.s7_instance.server.server_host
        self.server_port = self.s7_instance.server.server_port

    def tearDown(self):
        teardown_test_server(self.s7_instance, self.greenlet)

    def test_s7(self):
        """
        Objective: Test if the S7 server returns the values expected.
        """
        src_tsaps = (0x100, 0x200)
        dst_tsaps = (0x102, 0x200, 0x201)
        s7_con = s7comm_client.s7(self.server_host, self.server_port)
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
        identities = s7comm_client.GetIdentity(
            self.server_host, self.server_port, res[0], res[1]
        )
        s7_con.plc_stop_function()

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
                11: "",
            },
        }

        for line in identities:
            sec, item, val = line.split(";")
            try:
                self.assertTrue(dic[int(sec)][int(item)] == val.strip())
            except AssertionError:
                print((sec, item, val))
                raise
