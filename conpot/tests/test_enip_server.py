# Copyright (C) 2017  Yuru Shao <shaoyuru@gmail.com>
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
import struct
import unittest

import pytest
from gevent import sleep, socket

from conpot.protocols.enip.enip_server import EnipServer
from conpot.tests.helpers.enip_client import EnipClient
from conpot.utils.greenlet import spawn_test_server, teardown_test_server

# Values intentionally differ from cm-ethernetip Identity defaults so
# list_identity tests prove template device_info is wired through.
_TEST_PRODUCT_NAME = "ConpotTestENIP"
_TEST_PRODUCT_CODE = 70
_TEST_VENDOR_ID = 68
_TEST_DEVICE_TYPE = 31
_TEST_SERIAL_NUMBER = "720834"
_TEST_PRODUCT_REV = 0x1001


class EnipServerTCP(EnipServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.addr = "127.0.0.1"
        self.port = 50002
        self.config.mode = "tcp"
        self.config.product_name = _TEST_PRODUCT_NAME
        self.config.product_code = _TEST_PRODUCT_CODE
        self.config.vendor_id = _TEST_VENDOR_ID
        self.config.device_type = _TEST_DEVICE_TYPE
        self.config.serial_number = _TEST_SERIAL_NUMBER
        self.config.product_rev = _TEST_PRODUCT_REV


class EnipServerUDP(EnipServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.addr = "127.0.0.1"
        self.port = 60002
        self.config.mode = "udp"
        self.config.product_name = _TEST_PRODUCT_NAME
        self.config.product_code = _TEST_PRODUCT_CODE
        self.config.vendor_id = _TEST_VENDOR_ID
        self.config.device_type = _TEST_DEVICE_TYPE
        self.config.serial_number = _TEST_SERIAL_NUMBER
        self.config.product_rev = _TEST_PRODUCT_REV


@pytest.fixture(scope="class")
def enip_test_servers(request):
    """One TCP + UDP ENIP server pair for the whole test class."""
    tcp_server, tcp_greenlet = spawn_test_server(
        EnipServerTCP, "default", "enip", port=50002
    )
    udp_server, udp_greenlet = spawn_test_server(
        EnipServerUDP, "default", "enip", port=60002
    )
    request.cls.enip_server_tcp = tcp_server
    request.cls.server_greenlet_tcp = tcp_greenlet
    request.cls.enip_server_udp = udp_server
    request.cls.server_greenlet_udp = udp_greenlet
    yield
    teardown_test_server(udp_server, udp_greenlet)
    teardown_test_server(tcp_server, tcp_greenlet)


@pytest.mark.usefixtures("enip_test_servers")
class TestENIPServer(unittest.TestCase):

    def test_read_tags(self):
        with EnipClient(
            self.enip_server_tcp.addr, self.enip_server_tcp.port, timeout=4.0
        ) as client:
            data = client.get_attribute_single(22, 1, 1)
            self.assertEqual(100, struct.unpack_from("<b", data)[0])

    def test_write_tags(self):
        with EnipClient(
            self.enip_server_tcp.addr, self.enip_server_tcp.port, timeout=4.0
        ) as client:
            client.set_attribute_single(22, 1, 1, struct.pack("<b", 50))
            data = client.get_attribute_single(22, 1, 1)
            self.assertEqual(50, struct.unpack_from("<b", data)[0])

    def test_list_services_tcp(self):
        with EnipClient(
            self.enip_server_tcp.addr,
            self.enip_server_tcp.port,
            udp=False,
            timeout=4.0,
        ) as client:
            self.assertEqual("Communications", client.list_services())

    def test_list_services_udp(self):
        with EnipClient(
            self.enip_server_udp.addr,
            self.enip_server_udp.port,
            udp=True,
            timeout=4.0,
        ) as client:
            self.assertEqual("Communications", client.list_services())

    def test_list_identity_tcp(self):
        with EnipClient(
            self.enip_server_tcp.addr,
            self.enip_server_tcp.port,
            udp=False,
            timeout=4.0,
        ) as client:
            identity = client.list_identity()
            self.assertEqual(_TEST_PRODUCT_NAME, identity["product_name"])
            self.assertEqual(_TEST_PRODUCT_CODE, identity["product_code"])
            self.assertEqual(_TEST_VENDOR_ID, identity["vendor_id"])
            self.assertEqual(_TEST_DEVICE_TYPE, identity["device_type"])
            self.assertEqual(int(_TEST_SERIAL_NUMBER), identity["serial_number"])
            self.assertEqual(_TEST_PRODUCT_REV, identity["product_revision"])

    def test_list_identity_udp(self):
        with EnipClient(
            self.enip_server_udp.addr,
            self.enip_server_udp.port,
            udp=True,
            timeout=4.0,
        ) as client:
            identity = client.list_identity()
            self.assertEqual(_TEST_PRODUCT_NAME, identity["product_name"])
            self.assertEqual(_TEST_PRODUCT_CODE, identity["product_code"])
            self.assertEqual(_TEST_VENDOR_ID, identity["vendor_id"])
            self.assertEqual(_TEST_DEVICE_TYPE, identity["device_type"])
            self.assertEqual(int(_TEST_SERIAL_NUMBER), identity["serial_number"])
            self.assertEqual(_TEST_PRODUCT_REV, identity["product_revision"])

    def test_list_interfaces_tcp(self):
        with EnipClient(
            self.enip_server_tcp.addr,
            self.enip_server_tcp.port,
            udp=False,
            timeout=4.0,
        ) as client:
            self.assertDictEqual({"count": 0}, client.list_interfaces())

    def test_list_interfaces_udp(self):
        with EnipClient(
            self.enip_server_udp.addr,
            self.enip_server_udp.port,
            udp=True,
            timeout=4.0,
        ) as client:
            self.assertDictEqual({"count": 0}, client.list_interfaces())

    def test_send_nop(self):
        """NOP is a keepalive: no reply, and the TCP session stays up."""
        nop = struct.pack("<HHII8sI", 0, 0, 0, 0, b"\x00" * 8, 0)
        identity = struct.pack("<HHII8sI", 0x0063, 0, 0, 0, b"\x00" * 8, 0)

        tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            tcp.settimeout(2.0)
            tcp.connect((self.enip_server_tcp.addr, self.enip_server_tcp.port))
            tcp.sendall(nop)
            tcp.settimeout(0.4)
            with self.assertRaises(socket.timeout):
                tcp.recv(1024)
            tcp.settimeout(2.0)
            tcp.sendall(identity)
            reply = tcp.recv(1024)
        finally:
            tcp.close()
        self.assertGreaterEqual(len(reply), 24)
        self.assertEqual(struct.unpack_from("<H", reply)[0], 0x0063)
        self.assertIn(b"ConpotTestENIP", reply)

        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            udp.settimeout(0.5)
            udp.sendto(nop, (self.enip_server_udp.addr, self.enip_server_udp.port))
            with self.assertRaises(socket.timeout):
                udp.recvfrom(1024)
        finally:
            udp.close()
        sleep(0.2)
        with EnipClient(
            self.enip_server_udp.addr,
            self.enip_server_udp.port,
            udp=True,
            timeout=4.0,
        ) as client:
            identity_obj = client.list_identity()
        self.assertEqual(_TEST_PRODUCT_NAME, identity_obj["product_name"])

    def test_malformend_request_tcp(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(4.0)
            s.connect((self.enip_server_tcp.addr, self.enip_server_tcp.port))
            s.send(
                b"e\x00\x04\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                + b"x00\x00\x01\x00\x00\x00"
            )
            try:
                _ = s.recv(1024)
            except socket.timeout:
                pass
        finally:
            s.close()

    def test_malformend_request_udp(self):
        pass
