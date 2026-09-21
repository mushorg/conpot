# Copyright (C) 2017  Patrick Reichenberger (University of Passau) <patrick.reichenberger@t-online.de>
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
import asyncio
import socket
import time
import unittest
from unittest.mock import patch
import conpot.core as conpot_core
from conpot.protocols.IEC104 import IEC104_server, frames
from conpot.utils.server_tasks import spawn_test_server, teardown_test_server


class TestIEC104Server(unittest.TestCase):
    def setUp(self):
        self.databus = conpot_core.get_databus()

        self.iec104_inst, self.handle = spawn_test_server(
            IEC104_server.IEC104Server, "IEC104", "IEC104", port=2404
        )

        self.coa = self.iec104_inst.device_data_controller.common_address

    def tearDown(self):
        teardown_test_server(self.iec104_inst, self.handle)

    def test_startdt(self):
        """
        Objective: Test if answered correctly to STARTDT act
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", 2404))
        s.send(frames.STARTDT_act.build())
        data = s.recv(6)
        self.assertSequenceEqual(data, frames.STARTDT_con.build())

    def test_testfr(self):
        """
        Objective: Test if answered correctly to TESTFR act
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", 2404))
        s.send(frames.TESTFR_act.build())
        data = s.recv(6)
        self.assertEqual(data, frames.TESTFR_con.build())

    def test_write_for_non_existing(self):
        """
        Objective: Test answer for a command to a device that doesn't exist
        (Correct behaviour of the IEC104 protocol is not known exactly. Other case is test for no answer)
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", 2404))

        s.send(frames.STARTDT_act.build())
        s.recv(6)

        single_command = (
            frames.i_frame()
            / frames.asdu_head(COA=self.coa, COT=6)
            / frames.asdu_infobj_45(IOA=0xEEEEEE, SCS=1)
        )
        s.send(single_command.build())
        data = s.recv(16)

        bad_addr = (
            frames.i_frame(RecvSeq=0x0002)
            / frames.asdu_head(COA=self.coa, COT=47)
            / frames.asdu_infobj_45(IOA=0xEEEEEE, SCS=1)
        )
        self.assertSequenceEqual(data, bad_addr.build())

    def test_write_relation_for_existing(self):
        """
        Objective: Test answer for a correct command to a device that does exist and has a related sensor
        (Actuator 22_20 (Type 45: Single Command) will be tested,
        the corresponding(!) sensor 13_20 (Type 1: Single Point Information) changes the value
        and the termination confirmation is returned)
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", 2404))

        s.send(frames.STARTDT_act.build())
        s.recv(6)

        self.databus.set_value("22_20", 0)  # Must be in template and relation to 13_20
        self.databus.set_value("13_20", 0)  # Must be in template

        single_command = (
            frames.i_frame()
            / frames.asdu_head(COA=self.coa, COT=6)
            / frames.asdu_infobj_45(IOA=0x141600, SCS=1)
        )
        s.send(single_command.build())

        data = s.recv(16)
        act_conf = (
            frames.i_frame(RecvSeq=0x0002)
            / frames.asdu_head(COA=self.coa, COT=7)
            / frames.asdu_infobj_45(IOA=0x141600, SCS=1)
        )
        self.assertSequenceEqual(data, act_conf.build())

        data = s.recv(16)
        info = (
            frames.i_frame(SendSeq=0x0002, RecvSeq=0x0002)
            / frames.asdu_head(COA=self.coa, COT=11)
            / frames.asdu_infobj_1(IOA=0x140D00)
        )
        info.SIQ = frames.SIQ(SPI=1)
        self.assertSequenceEqual(data, info.build())

        data = s.recv(16)
        act_term = (
            frames.i_frame(SendSeq=0x0004, RecvSeq=0x0002)
            / frames.asdu_head(COA=self.coa, COT=10)
            / frames.asdu_infobj_45(IOA=0x141600, SCS=1)
        )
        self.assertSequenceEqual(data, act_term.build())

    def test_write_no_relation_for_existing(self):
        """
        Objective: Test answer for a correct command to a device that does exist and has no related sensor
        (Actuator 22_19 (Type 45: Single Command) will be tested, the corresponding(!) sensor is not existent)
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", 2404))

        s.send(frames.STARTDT_act.build())
        s.recv(6)

        self.databus.set_value("22_19", 0)  # Must be in template and no relation

        single_command = (
            frames.i_frame()
            / frames.asdu_head(COA=self.coa, COT=6)
            / frames.asdu_infobj_45(IOA=0x131600, SCS=0)
        )
        s.send(single_command.build())

        data = s.recv(16)
        act_conf = (
            frames.i_frame(RecvSeq=0x0002)
            / frames.asdu_head(COA=self.coa, COT=7)
            / frames.asdu_infobj_45(IOA=0x131600, SCS=0)
        )
        self.assertSequenceEqual(data, act_conf.build())

        data = s.recv(16)
        act_term = (
            frames.i_frame(SendSeq=0x0002, RecvSeq=0x0002)
            / frames.asdu_head(COA=self.coa, COT=10)
            / frames.asdu_infobj_45(IOA=0x131600, SCS=0)
        )
        self.assertSequenceEqual(data, act_term.build())

    def test_write_wrong_type_for_existing(self):
        """
        Objective: Test answer for a command of wrong type to a device that does exist
        (Actuator 22_20 (Type 45: Single Command) will be tested,
        but a wrong command type (Double Commands instead of Single Command) is sent to device)
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", 2404))

        s.send(frames.STARTDT_act.build())
        s.recv(6)

        self.databus.set_value("22_20", 0)  # Must be in template

        single_command = (
            frames.i_frame()
            / frames.asdu_head(COA=self.coa, COT=6)
            / frames.asdu_infobj_46(IOA=0x141600, DCS=1)
        )
        s.send(single_command.build())

        data = s.recv(16)
        act_conf = (
            frames.i_frame(RecvSeq=0x0002)
            / frames.asdu_head(COA=self.coa, PN=1, COT=7)
            / frames.asdu_infobj_46(IOA=0x141600, DCS=1)
        )
        self.assertSequenceEqual(data, act_conf.build())

    def _get_log_event(self, timeout=2.0):
        loop = self.handle._loop
        log_queue = conpot_core.get_sessionManager().log_queue

        async def _get():
            return await asyncio.wait_for(log_queue.get(), timeout=timeout)

        return asyncio.run_coroutine_threadsafe(_get(), loop).result(
            timeout=timeout + 1
        )

    @patch.object(socket.socket, "recv", side_effect=OSError(32, "Socket Error"))
    def test_failing_connection_connection_lost_event(self, mock_timeout):
        """
        Objective: Test if correct exception is executed when a socket.error
        with EPIPE occurs
        """
        conpot_core.get_sessionManager().purge_sessions()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 2404))
        time.sleep(0.2)
        con_new_event = self._get_log_event()
        con_lost_event = self._get_log_event(timeout=1)

        self.assertEqual("NEW_CONNECTION", con_new_event["event_type"])
        self.assertEqual("CONNECTION_LOST", con_lost_event["event_type"])

        s.close()

    def test_single_byte_then_close_does_not_hang(self):
        """
        Regression test for issue #482.

        A client that sends one byte then half-closes used to busy-loop in
        the header gather while (CPU DoS). The handler must drop the
        connection promptly and still serve later clients.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 2404))
        s.sendall(b"\x68")
        s.shutdown(socket.SHUT_WR)

        s.settimeout(2.0)
        try:
            data = s.recv(1024)
        except socket.timeout:
            self.fail("server never closed the connection")
        s.close()
        self.assertEqual(data, b"")

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", 2404))
        s.send(frames.STARTDT_act.build())
        data = s.recv(6)
        s.close()
        self.assertSequenceEqual(data, frames.STARTDT_con.build())

    def test_trailing_byte_then_close_does_not_hang(self):
        """
        Regression test for issue #482.

        A valid APDU plus one trailing byte left in the TCP buffer, followed
        by a half-close, must not busy-loop when the leftover byte is read as
        an incomplete next header.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 2404))
        # STARTDT act (6 bytes) + one stray byte
        s.sendall(frames.STARTDT_act.build() + b"\x00")
        s.settimeout(2.0)
        try:
            data = s.recv(6)
        except socket.timeout:
            self.fail("server did not answer STARTDT")
        self.assertSequenceEqual(data, frames.STARTDT_con.build())

        s.shutdown(socket.SHUT_WR)
        try:
            data = s.recv(1024)
        except socket.timeout:
            self.fail("server never closed the connection")
        s.close()
        self.assertEqual(data, b"")
