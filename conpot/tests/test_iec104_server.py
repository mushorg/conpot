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
import os
import unittest
import socket
from collections import namedtuple

from conpot.protocols.IEC104 import IEC104_server, frames
import conpot.core as conpot_core
import gevent.monkey
from gevent.server import StreamServer

gevent.monkey.patch_all()


class TestBase(unittest.TestCase):

    def setUp(self):
        template = reduce(os.path.join, 'conpot/templates/IEC104/template.xml'.split('/'))
        iec104_template = reduce(os.path.join, 'conpot/templates/IEC104/IEC104/IEC104.xml'.split('/'))

        self.databus = conpot_core.get_databus()
        self.databus.initialize(template)
        args = namedtuple('FakeArgs', 'mibpaths raw_mib')
        self.iec104_inst = IEC104_server.IEC104Server(iec104_template, 'none', args)
        self.iec104_server = StreamServer(('127.0.0.1', 2404), self.iec104_inst.handle)
        self.iec104_server.start()

    def tearDown(self):
        self.iec104_server.stop()

    def test_startdt(self):
        """
        Objective: Test if answered correctly to STARTDT act
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(('127.0.0.1', 2404))
        s.send(frames.STARTDT_act.build())
        data = s.recv(6)
        self.assertSequenceEqual(data, frames.STARTDT_con.build())

    def test_testfr(self):
        """
        Objective: Test if answered correctly to TESTFR act
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(('127.0.0.1', 2404))
        s.send(frames.TESTFR_act.build())
        data = s.recv(6)
        self.assertEquals(data, frames.TESTFR_con.build())

    def test_write_for_non_existing(self):
        """
        Objective: Test answer for a command to a device that doesn't exist
        (Correct behaviour of the IEC104 protocol is not known exactly. Other case is test for no answer)
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(('127.0.0.1', 2404))

        s.send(frames.STARTDT_act.build())
        s.recv(6)

        single_command = frames.i_frame() / frames.asdu_head(COT=6) / frames.asdu_infobj_45(IOA=0xEEEEEE, SCS=1)
        s.send(single_command.build())
        data = s.recv(16)

        bad_addr = frames.i_frame(RecvSeq=0x0002) / frames.asdu_head(COT=47) / frames.asdu_infobj_45(IOA=0xEEEEEE,
                                                                                                     SCS=1)
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
        s.connect(('127.0.0.1', 2404))

        s.send(frames.STARTDT_act.build())
        s.recv(6)

        self.databus.set_value('22_20', 0)  # Must be in template and relation to 13_20
        self.databus.set_value('13_20', 0)  # Must be in template
        # print str(hex(IEC104.addr_in_hex('13_20')))
        single_command = frames.i_frame() / frames.asdu_head(COT=6) / frames.asdu_infobj_45(IOA=0x141600, SCS=1)
        s.send(single_command.build())

        data = s.recv(16)
        act_conf = frames.i_frame(RecvSeq=0x0002) / frames.asdu_head(COT=7) / frames.asdu_infobj_45(IOA=0x141600, SCS=1)
        self.assertSequenceEqual(data, act_conf.build())

        data = s.recv(16)
        info = frames.i_frame(SendSeq=0x0002, RecvSeq=0x0002) / frames.asdu_head(COT=11) / frames.asdu_infobj_1(
            IOA=0x140d00)
        info.SIQ = frames.SIQ(SPI=1)
        self.assertSequenceEqual(data, info.build())

        data = s.recv(16)
        act_term = frames.i_frame(SendSeq=0x0004, RecvSeq=0x0002) / frames.asdu_head(COT=10) / frames.asdu_infobj_45(
            IOA=0x141600, SCS=1)
        self.assertSequenceEqual(data, act_term.build())

    def test_write_no_relation_for_existing(self):
        """
        Objective: Test answer for a correct command to a device that does exist and has no related sensor
        (Actuator 22_19 (Type 45: Single Command) will be tested, the corresponding(!) sensor is not existent)
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(('127.0.0.1', 2404))

        s.send(frames.STARTDT_act.build())
        s.recv(6)

        self.databus.set_value('22_19', 0)  # Must be in template and no relation
        # print str(hex(IEC104.addr_in_hex('13_20')))
        single_command = frames.i_frame() / frames.asdu_head(COT=6) / frames.asdu_infobj_45(IOA=0x131600, SCS=0)
        s.send(single_command.build())

        data = s.recv(16)
        act_conf = frames.i_frame(RecvSeq=0x0002) / frames.asdu_head(COT=7) / frames.asdu_infobj_45(IOA=0x131600, SCS=0)
        self.assertSequenceEqual(data, act_conf.build())

        data = s.recv(16)
        act_term = frames.i_frame(SendSeq=0x0002, RecvSeq=0x0002) / frames.asdu_head(COT=10) / frames.asdu_infobj_45(
            IOA=0x131600, SCS=0)
        self.assertSequenceEqual(data, act_term.build())

    def test_write_wrong_type_for_existing(self):
        """
        Objective: Test answer for a command of wrong type to a device that does exist
        (Actuator 22_20 (Type 45: Single Command) will be tested,
        but a wrong command type (Double Commands instead of Single Command) is sent to device)
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(('127.0.0.1', 2404))

        s.send(frames.STARTDT_act.build())
        s.recv(6)

        self.databus.set_value('22_20', 0)  # Must be in template
        # print str(hex(IEC104.addr_in_hex('13_20')))
        single_command = frames.i_frame() / frames.asdu_head(COT=6) / frames.asdu_infobj_46(IOA=0x141600, DCS=1)
        s.send(single_command.build())

        data = s.recv(16)
        act_conf = frames.i_frame(RecvSeq=0x0002) / frames.asdu_head(PN=1, COT=7) / frames.asdu_infobj_46(IOA=0x141600,
                                                                                                          DCS=1)
        self.assertSequenceEqual(data, act_conf.build())
