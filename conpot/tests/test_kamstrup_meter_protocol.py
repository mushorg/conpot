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
from conpot.protocols.kamstrup.meter_protocol.kamstrup_server import KamstrupServer
from conpot.helpers import chr_py3
import conpot
import gevent
from gevent import socket
import os
import unittest


class TestKamstrup(unittest.TestCase):
    def setUp(self):

        # clean up before we start...
        conpot_core.get_sessionManager().purge_sessions()

        # get the conpot directory
        self.dir_name = os.path.dirname(conpot.__file__)
        self.kamstrup_management_server = KamstrupServer(
            self.dir_name + "/templates/kamstrup_382/kamstrup_meter/kamstrup_meter.xml",
            None,
            None,
        )
        self.server_greenlet = gevent.spawn(
            self.kamstrup_management_server.start, "127.0.0.1", 0
        )

        # initialize the databus
        self.databus = conpot_core.get_databus()
        self.databus.initialize(self.dir_name + "/templates/kamstrup_382/template.xml")
        gevent.sleep(1)

        self.request_parser = request_parser.KamstrupRequestParser()
        self.command_responder = CommandResponder(
            self.dir_name + "/templates/kamstrup_382/kamstrup_meter/kamstrup_meter.xml"
        )

    def tearDown(self):
        self.databus.reset()

    def test_request_get_register(self):
        # requesting register 1033
        request_bytes = (0x80, 0x3F, 0x10, 0x01, 0x04, 0x09, 0x18, 0x6D, 0x0D)
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

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", self.kamstrup_management_server.server.server_port))
        s.sendall(
            chr_py3(0x80)
            + chr_py3(0x3F)
            + chr_py3(0x10)
            + chr_py3(0x01)
            + chr_py3(0x04)
            + chr_py3(0x09)
            + chr_py3(0x18)
            + chr_py3(0x6D)
            + chr_py3(0x0D)
        )
        data = s.recv(1024)
        s.close()
        # FIXME: verify bytes received from server - ask jkv?
        pkt = [hex(data[i]) for i in range(len(data))]
        self.assertTrue(("0x40" in pkt) and ("0x3f" in pkt) and ("0xd" in pkt))


if __name__ == "__main__":
    unittest.main()
