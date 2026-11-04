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
from struct import pack, unpack

from conpot.protocols.s7comm.s7 import S7
from conpot.protocols.s7comm.s7_server import S7Server
from conpot.tests.helpers import s7comm_client
from conpot.utils.server_tasks import spawn_test_server, teardown_test_server


class TestS7Server(unittest.TestCase):
    def setUp(self):
        self.s7_instance, self.handle = spawn_test_server(S7Server, "default", "s7comm")

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
            17: {
                1: "6ES7 151-8AB01-0AB0  v.0.3",
                6: "6ES7 151-8AB01-0AB0  v.0.3",
                7: "v.3.2.8",
                129: "Boot Loader           A",
            },
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
        """SZL 0x0011 returns every identification record for any index."""
        con = self._connect()
        for index in (0, 1, 6, 7):
            data = con.Function(0x04, 0x04, 0x01, pack("!HH", 0x0011, index))
            szl_id, _, length, count = unpack("!HHHH", data[:8])
            self.assertEqual((szl_id, length, count), (0x0011, 28, 4))
            records = [data[8 + i * 28 : 8 + (i + 1) * 28] for i in range(4)]
            self.assertEqual(
                [r[:2] for r in records],
                [b"\x00\x01", b"\x00\x06", b"\x00\x07", b"\x00\x81"],
            )
            # Hardware version words, then binary 'V'/'A' + major.minor.patch
            self.assertEqual(records[0][22:28], b"\x00\xc0\x00\x03\x00\x01")
            self.assertEqual(records[2][24:28], b"V\x03\x02\x08")
            self.assertEqual(records[3][24:28], b"A\x20\x09\x09")
        con.s.close()

    def test_szl_0011_matches_real_cpu_315_2_pn_dp(self):
        """With a real CPU's values, SZL 0x0011 must match its reply byte for byte.

        Reference: Read SZL 0x0011 reply of a CPU 315-2 PN/DP
        (6ES7 315-2EH14-0AB0, firmware V3.2.7), github.com/gymgit/s7-pcaps,
        snap7_s300_everything.pcapng frame 4.
        """
        import conpot.core as conpot_core

        databus = conpot_core.get_databus()
        saved = {
            key: databus.get_value(key)
            for key in ("s7_order_number", "s7_firmware_version")
        }
        databus.set_value("s7_order_number", "6ES7 315-2EH14-0AB0")
        databus.set_value("s7_firmware_version", "V3.2.7")
        try:
            con = self._connect()
            params = pack("!LBBBB", 0x00011204, 0x11, 0x44, 0x01, 0x00)
            data = pack("!BBH", 0xFF, 0x09, 4) + pack("!HH", 0x0011, 0x0000)
            response = con.Request(0x07, params, data)
            con.s.close()
        finally:
            for key, value in saved.items():
                databus.set_value(key, value)
        real_cpu_data = bytes.fromhex(
            "ff09007800110000001c0004"
            "000136455337203331352d32454831342d304142302000c000030001"
            "000636455337203331352d32454831342d304142302000c000030001"
            "0007202020202020202020202020202020202020202000c056030207"
            "0081426f6f74204c6f61646572202020202020202020000041200909"
        )
        self.assertEqual(response.parameters[:7], bytes.fromhex("00011208128401"))
        self.assertEqual(response.parameters[8:], b"\x00\x00\x00\x00")
        self.assertEqual(response.data, real_cpu_data)

    def test_nmap_s7_info_probe(self):
        """Replay nmap's s7-info.nse request sequence and apply its parser offsets.

        s7-info waits for at least 125 bytes after the SZL 0x0011 read and
        180 bytes after the SZL 0x001C read, then reads fixed offsets.
        """
        sock = socket.socket()
        sock.settimeout(2)
        sock.connect((self.server_host, self.server_port))

        def exchange(hex_request, minimum):
            sock.sendall(bytes.fromhex(hex_request))
            reply = b""
            while len(reply) < minimum:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                reply += chunk
            return reply

        def cstring(buf, offset):
            # Lua string.unpack("z", s, i) with 1-based i
            start = offset - 1
            end = buf.index(b"\x00", start) if b"\x00" in buf[start:] else len(buf)
            return buf[start:end]

        exchange("0300001611e00000001400c1020100c2020102c0010a", 6)
        setup = exchange("0300001902f08032010000000000080000f0000001000101e0", 8)
        self.assertEqual(setup[7], 0x32)
        szl_11 = "0300002102f080320700000000000800080001120411440100ff09000400110001"
        exchange(szl_11, 8)

        first = exchange(szl_11, 125)
        self.assertEqual(first[7], 0x32)
        self.assertGreaterEqual(len(first), 125)
        self.assertEqual(cstring(first, 44).strip(), b"6ES7 151-8AB01-0AB0")
        self.assertEqual(cstring(first, 72).strip(), b"6ES7 151-8AB01-0AB0")
        self.assertEqual(tuple(first[122:125]), (3, 2, 8))

        second = exchange(
            "0300002102f080320700000000000800080001120411440100ff090004001c0001",
            180,
        )
        sock.close()
        self.assertEqual(second[7], 0x32)
        self.assertGreaterEqual(len(second), 180)
        offset = 0 if second[30] == 0x1C else 4
        self.assertEqual(cstring(second, 40 + offset), b"Technodrome")
        self.assertEqual(cstring(second, 108 + offset), b"Mouser Factory")
        self.assertEqual(cstring(second, 176 + offset), b"88111222")

    def test_szl_userdata_params_match_declared_length(self):
        """Userdata response params declare 8 trailing bytes and must carry them."""
        con = self._connect()
        params = pack("!LBBBB", 0x00011204, 0x11, 0x44, 0x01, 0x00)
        data = pack("!BBH", 0xFF, 0x09, 4) + pack("!HH", 0x0011, 0x0001)
        response = con.Request(0x07, params, data)
        con.s.close()
        self.assertEqual(len(response.parameters), 12)
        self.assertEqual(response.parameters[3], 8)
        self.assertEqual(response.parameters[8:12], b"\x00\x00\x00\x00")

    def test_szl_0111_returns_single_record(self):
        """SZL 0x0111 returns only the record selected by the index."""
        con = self._connect()
        data = con.Function(0x04, 0x04, 0x01, pack("!HH", 0x0111, 0x0007))
        con.s.close()
        szl_id, index, length, count = unpack("!HHHH", data[:8])
        self.assertEqual((szl_id, index, length, count), (0x0111, 7, 28, 1))
        record = data[8:]
        self.assertEqual(len(record), 28)
        self.assertEqual(record[:2], b"\x00\x07")
        # Ausbg1 = 'V' + major, Ausbg2 = minor, patch (binary)
        self.assertEqual(record[24:28], b"V\x03\x02\x08")

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
