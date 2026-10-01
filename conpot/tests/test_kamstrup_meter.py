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

import os
import socket
import unittest

from crc16.crc16pure import crc16xmodem

import conpot
from conpot.protocols.kamstrup_meter import messages
from conpot.protocols.kamstrup_meter.command_responder import CommandResponder
from conpot.protocols.kamstrup_meter.kamstrup_server import KamstrupServer
from conpot.protocols.kamstrup_meter.request_parser import KamstrupRequestParser
from conpot.templates.parse import parse_toml_config
from conpot.utils.networking import chr_py3
from conpot.utils.server_tasks import spawn_test_server, teardown_test_server


def _build_login_request(comm_address, pin_code):
    """Build a framed KMP login request (CID 0x92) with CRC and EOT."""
    body = [
        comm_address,
        messages.KamstrupRequestLogin.command_byte,
        (pin_code >> 8) & 0xFF,
        pin_code & 0xFF,
    ]
    crc = crc16xmodem(bytes(body))
    frame = [0x80] + body + [crc >> 8, crc & 0xFF, 0x0D]
    return bytes(frame)


class TestKamstrup(unittest.TestCase):
    def setUp(self):
        # get the conpot directory
        self.dir_name = os.path.dirname(conpot.__file__)
        self.request_parser = KamstrupRequestParser()
        meter_cfg = parse_toml_config(
            os.path.join(
                self.dir_name, "templates", "kamstrup_382", "kamstrup_meter.toml"
            )
        )["kamstrup_meter"]
        self.command_responder = CommandResponder(meter_cfg)
        self.login_pin = meter_cfg.get("login_pin", 12345)

        self.kamstrup_management_server, self.server_handle = spawn_test_server(
            KamstrupServer, "kamstrup_382", "kamstrup_meter"
        )

    def tearDown(self):
        teardown_test_server(self.kamstrup_management_server, self.server_handle)

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

    def test_login_accepted(self):
        frame = _build_login_request(0x3F, self.login_pin)
        for b in frame:
            self.request_parser.add_byte(chr(b))
        parsed = self.request_parser.get_request()
        self.assertIsInstance(parsed, messages.KamstrupRequestLogin)
        self.assertEqual(parsed.pin_code, self.login_pin)

        response = self.command_responder.respond(parsed)
        self.assertIsInstance(response, messages.KamstrupResponseLogin)
        self.assertEqual(response.status, messages.KamstrupResponseLogin.STATUS_OK)

        serialized = response.serialize()
        self.assertEqual(serialized[0], 0x40)
        self.assertEqual(serialized[1], 0x3F)
        self.assertEqual(serialized[2], 0x92)
        self.assertEqual(serialized[3], 0x00)
        self.assertEqual(serialized[-1], 0x0D)

    def test_login_denied(self):
        wrong_pin = (self.login_pin + 1) % 65536
        frame = _build_login_request(0x3F, wrong_pin)
        for b in frame:
            self.request_parser.add_byte(chr(b))
        parsed = self.request_parser.get_request()
        response = self.command_responder.respond(parsed)
        self.assertEqual(response.status, messages.KamstrupResponseLogin.STATUS_DENIED)

    def test_login_over_socket(self):
        frame = _build_login_request(0x3F, self.login_pin)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(("127.0.0.1", self.kamstrup_management_server.server.server_port))
        s.sendall(frame)
        data = s.recv(1024)
        s.close()
        self.assertEqual(data[0], 0x40)
        self.assertEqual(data[1], 0x3F)
        self.assertEqual(data[2], 0x92)
        self.assertEqual(data[3], 0x00)
        self.assertEqual(data[-1], 0x0D)

    def test_skipped_bytes_not_logged_per_byte(self):
        with self.assertNoLogs(
            "conpot.protocols.kamstrup_meter.request_parser", level="INFO"
        ):
            for _ in range(1000):
                self.request_parser.add_byte(chr(0))
            self.assertIsNone(self.request_parser.get_request())
