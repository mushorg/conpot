# Copyright (C) 2013 MushMush Foundation
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

import socket
import unittest
from struct import pack

from conpot.protocols.s7comm.s7 import S7
from conpot.protocols.s7comm.s7_server import S7Server
from conpot.tests.helpers import s7comm_client
from conpot.utils.server_tasks import spawn_test_server, teardown_test_server


class TestS7Server(unittest.TestCase):
    def setUp(self):
        self.s7_instance, self.handle = spawn_test_server(
            S7Server, "default", "s7comm"
        )

        self.server_host = self.s7_instance.server.server_host
        self.server_port = self.s7_instance.server.server_port

    def tearDown(self):
        teardown_test_server(self.s7_instance, self.handle)

    def _connect(self, src_tsap=0x100, dst_tsap=0x102):
        con = s7comm_client.s7(self.server_host, self.server_port, src_tsap, dst_tsap)
        con.Connect()
        return con

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

    def test_unknown_szl_does_not_crash(self):
        """Unknown SZL IDs must not raise TypeError on len(int) (issue #507)."""
        sock = socket.socket()
        sock.settimeout(2)
        sock.connect((self.server_host, self.server_port))
        # COTP CR + S7 negotiate + SZL read for unsupported ID 0x9999
        sock.sendall(bytes.fromhex("0300001611e00000000600c1020100c2020102c0010a"))
        self.assertTrue(sock.recv(1024))
        sock.sendall(
            bytes.fromhex("0300001902f08032010000ccc100080000f0000001000103c0")
        )
        self.assertTrue(sock.recv(1024))
        sock.sendall(
            bytes.fromhex(
                "0300002102f080320700001200000800080001120411440100ff09000499990000"
            )
        )
        reply = sock.recv(1024)
        sock.close()
        # Server must answer (previously crashed while packing int data).
        self.assertTrue(reply)

    def test_cotp_cr_long_tsap_accepted(self):
        """COTP CR with TSAP length > 2 must get a CC (issue #452)."""
        from conpot.protocols.s7comm.cotp import COTP_ConnectionRequest

        # Calling TSAP "SIMATIC-ROOT-ES" (15 bytes) as seen with S7-1200 tools.
        long_tsap = b"SIMATIC-ROOT-ES"
        payload = (
            bytes.fromhex("0000000600")
            + bytes([0xC1, len(long_tsap)])
            + long_tsap
            + bytes.fromhex("c2020102c0010a")
        )
        req = COTP_ConnectionRequest().dissect(payload)
        self.assertEqual(req.src_tsap, long_tsap)
        self.assertEqual(req.dst_tsap, 0x0102)
        self.assertEqual(req.tpdu_size, 0x0A)

        sock = socket.socket()
        sock.settimeout(2)
        sock.connect((self.server_host, self.server_port))
        # TPKT + COTP CR (tpdu type 0xE0) with the long calling TSAP.
        cotp = bytes([len(payload) + 1, 0xE0]) + payload
        tpkt = pack("!BBH", 3, 0, 4 + len(cotp)) + cotp
        sock.sendall(tpkt)
        reply = sock.recv(1024)
        sock.close()
        self.assertGreaterEqual(len(reply), 6)
        # TPKT version 3, COTP CC TPDU type 0xD0
        self.assertEqual(reply[0], 3)
        self.assertEqual(reply[5], 0xD0)

    def test_cotp_cr_preserves_byte_0x62(self):
        """TPKT/COTP bytes must not strip 0x62 ('b') from the wire."""
        sock = socket.socket()
        sock.settimeout(2)
        sock.connect((self.server_host, self.server_port))
        # Classic CR with src_tsap 0x0162 (contains byte 'b').
        sock.sendall(bytes.fromhex("0300001611e00000000600c1020162c2020102c0010a"))
        reply = sock.recv(1024)
        sock.close()
        self.assertGreaterEqual(len(reply), 6)
        self.assertEqual(reply[5], 0xD0)
        # CC should echo src_tsap 0x0162 (not 0x0100 after stripping 0x62).
        self.assertIn(bytes.fromhex("c1020162"), reply)

    def test_szl_module_identification_hardware_firmware(self):
        """SZL 0x0011 indexes 6/7 must pack version words without struct.error."""
        con = self._connect()
        for index in (6, 7):
            data = con.Function(0x04, 0x04, 0x01, pack("!HH", 0x0011, index))
            self.assertGreaterEqual(len(data), 8)
            # Wire format carries ASCII 'V''3' in the version word (0x5633).
            self.assertIn(b"V3", data)
        con.s.close()

    def test_read_write_db_via_databus(self):
        """Read/Write VAR on DB1 must use the databus-backed bytearray (issue #524)."""
        import conpot.core as conpot_core

        db = conpot_core.get_databus().get_value("s7_db1")
        self.assertIsInstance(db, bytearray)
        self.assertEqual(len(db), 256)
        # Seed a known pattern without going through S7
        db[0:4] = b"\x10\x20\x30\x40"

        con = self._connect()
        # Area DB = 0x84
        data = con.ReadVar(0x84, 1, 0, 4)
        self.assertEqual(data, b"\x10\x20\x30\x40")

        con.WriteVar(0x84, 1, 2, b"\xaa\xbb")
        self.assertEqual(bytes(db[0:4]), b"\x10\x20\xaa\xbb")
        data = con.ReadVar(0x84, 1, 0, 4)
        self.assertEqual(data, b"\x10\x20\xaa\xbb")
        con.s.close()

    def test_read_db_out_of_range_keeps_connection(self):
        """Out-of-range Read VAR returns an item error without dropping the session."""
        con = self._connect()
        with self.assertRaises(s7comm_client.S7Error):
            # DB1 is 256 bytes; offset 250 + length 20 exceeds the block
            con.ReadVar(0x84, 1, 250, 20)
        # Connection must still accept another request
        data = con.ReadVar(0x84, 1, 0, 2)
        self.assertEqual(len(data), 2)
        con.s.close()

    def test_plc_stop_is_ack_data(self):
        S7.cpu_running = True
        con = self._connect()
        packet = con.plc_stop_function()
        self.assertIsNotNone(packet)
        self.assertEqual(packet.type, 3)
        self.assertEqual(packet.error, 0)
        self.assertEqual(packet.parameters, b"\x29")
        self.assertEqual(packet.data, b"")
        self.assertFalse(S7.cpu_running)
        con.s.close()

    def test_plc_start_is_ack_data(self):
        S7.cpu_running = False
        con = self._connect()
        packet = con.plc_start_function(b"COLD_START")
        self.assertIsNotNone(packet)
        self.assertEqual(packet.type, 3)
        self.assertEqual(packet.error, 0)
        self.assertEqual(packet.parameters, b"\x28")
        self.assertTrue(S7.cpu_running)
        con.s.close()
