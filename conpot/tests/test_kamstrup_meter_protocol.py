# Copyright (C) 2014  Johnny Vestergaard <jkv@unixcluster.dk>
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

import conpot.core as conpot_core
from conpot.protocols.kamstrup.meter_protocol.command_responder import CommandResponder
from conpot.protocols.kamstrup.meter_protocol import request_parser

import unittest


class TestKamstrup(unittest.TestCase):
    def setUp(self):

        # clean up before we start...
        conpot_core.get_sessionManager().purge_sessions()

        self.databus = conpot_core.get_databus()
        self.databus.initialize('conpot/templates/kamstrup_382/template.xml')
        self.request_parser = request_parser.KamstrupRequestParser()
        self.command_responder = CommandResponder('conpot/templates/kamstrup_382/kamstrup_meter/kamstrup_meter.xml')

    def tearDown(self):
        self.databus.reset()

    def test_request_get_register(self):
        # requesting register 1033
        request_bytes = (0x80, 0x3f, 0x10, 0x01, 0x04, 0x09, 0x18, 0x6d, 0x0d)
        for i in range(0, len(request_bytes)):
            self.request_parser.add_byte(chr(request_bytes[i]))
            if i < len(request_bytes) - 1:
                # parser returns None until it can put together an entire message
                self.assertEqual(self.request_parser.get_request(), None)

        parsed_request = self.request_parser.get_request()
        response = self.command_responder.respond(parsed_request)

        self.assertEqual(len(response.registers), 1)
        self.assertEqual(response.registers[0].name, 1033)
        # we should have no left overs
        self.assertEqual(len(self.request_parser.bytes), 0)
