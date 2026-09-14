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
import unittest

import pytest
from cpppo.server.enip import client
from gevent import socket

from conpot.protocols.enip.enip_server import EnipServer
from conpot.utils.greenlet import spawn_test_server, teardown_test_server

# In lieu of creating dedicated test templates we modify
# EnipServer config through inheritance.
# Values intentionally differ from cpppo's built-in Identity defaults so
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
    """One TCP + UDP ENIP server pair for the whole test class (avoids ~10× spawn cost)."""
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

    @staticmethod
    def attribute_operations(paths, int_type=None, **kwds):
        for op in client.parse_operations(paths, int_type=int_type or "SINT", **kwds):
            path_end = op["path"][-1]
            if "instance" in path_end:
                op["method"] = "get_attributes_all"
                assert (
                    "data" not in op
                ), "All Attributes cannot be operated on using Set Attribute services"
            elif "symbolic" in path_end or "attribute" in path_end or "element":
                op["method"] = (
                    "set_attribute_single" if "data" in op else "get_attribute_single"
                )
            else:
                raise AssertionError(
                    "Path invalid for Attribute services: %r", op["path"]
                )
            yield op

    @staticmethod
    def await_cpf_response(connection, command):
        response, _ = client.await_response(connection, timeout=4.0)
        return response["enip"]["CIP"][command]["CPF"]

    def test_read_tags(self):
        with client.connector(
            host=self.enip_server_tcp.addr, port=self.enip_server_tcp.port, timeout=4.0
        ) as connection:
            tags = ["@22/1/1"]
            ops = self.attribute_operations(tags)
            for _, _, _, _, _, val in connection.pipeline(operations=ops):
                self.assertEqual(100, val[0])

    def test_write_tags(self):
        with client.connector(
            host=self.enip_server_tcp.addr, port=self.enip_server_tcp.port, timeout=4.0
        ) as connection:
            tags = ["@22/1/1=(SINT)50", "@22/1/1"]
            ops = self.attribute_operations(tags)
            for idx, _, _, _, _, val in connection.pipeline(operations=ops):
                if idx == 0:
                    self.assertEqual(True, val)
                elif idx == 1:
                    self.assertEqual(50, val[0])

    def test_list_services_tcp(self):
        with client.connector(
            host=self.enip_server_tcp.addr,
            port=self.enip_server_tcp.port,
            timeout=4.0,
            udp=False,
            broadcast=False,
        ) as connection:
            connection.list_services()
            connection.shutdown()
            response = self.await_cpf_response(connection, "list_services")

            self.assertEqual(
                "Communications",
                response["item"][0]["communications_service"]["service_name"],
            )

    def test_list_services_udp(self):
        with client.connector(
            host=self.enip_server_udp.addr,
            port=self.enip_server_udp.port,
            timeout=4.0,
            udp=True,
            broadcast=True,
        ) as connection:
            connection.list_services()
            response = self.await_cpf_response(connection, "list_services")

            self.assertEqual(
                "Communications",
                response["item"][0]["communications_service"]["service_name"],
            )

    def test_list_identity_tcp(self):
        with client.connector(
            host=self.enip_server_tcp.addr,
            port=self.enip_server_tcp.port,
            timeout=4.0,
            udp=False,
            broadcast=False,
        ) as connection:
            connection.list_identity()
            connection.shutdown()
            response = self.await_cpf_response(connection, "list_identity")

            identity = response["item"][0]["identity_object"]
            self.assertEqual(_TEST_PRODUCT_NAME, identity["product_name"])
            self.assertEqual(_TEST_PRODUCT_CODE, identity["product_code"])
            self.assertEqual(_TEST_VENDOR_ID, identity["vendor_id"])
            self.assertEqual(_TEST_DEVICE_TYPE, identity["device_type"])
            self.assertEqual(int(_TEST_SERIAL_NUMBER), identity["serial_number"])
            self.assertEqual(_TEST_PRODUCT_REV, identity["product_revision"])

    def test_list_identity_udp(self):
        with client.connector(
            host=self.enip_server_udp.addr,
            port=self.enip_server_udp.port,
            timeout=4.0,
            udp=True,
            broadcast=True,
        ) as connection:
            connection.list_identity()
            response = self.await_cpf_response(connection, "list_identity")

            identity = response["item"][0]["identity_object"]
            self.assertEqual(_TEST_PRODUCT_NAME, identity["product_name"])
            self.assertEqual(_TEST_PRODUCT_CODE, identity["product_code"])
            self.assertEqual(_TEST_VENDOR_ID, identity["vendor_id"])
            self.assertEqual(_TEST_DEVICE_TYPE, identity["device_type"])
            self.assertEqual(int(_TEST_SERIAL_NUMBER), identity["serial_number"])
            self.assertEqual(_TEST_PRODUCT_REV, identity["product_revision"])

    def test_list_interfaces_tcp(self):
        with client.connector(
            host=self.enip_server_tcp.addr,
            port=self.enip_server_tcp.port,
            timeout=4.0,
            udp=False,
            broadcast=False,
        ) as conn:
            conn.list_interfaces()
            conn.shutdown()
            response = self.await_cpf_response(conn, "list_interfaces")

            self.assertDictEqual({"count": 0}, response)

    def test_list_interfaces_udp(self):
        with client.connector(
            host=self.enip_server_udp.addr,
            port=self.enip_server_udp.port,
            timeout=4.0,
            udp=True,
            broadcast=True,
        ) as conn:
            conn.list_interfaces()
            response = self.await_cpf_response(conn, "list_interfaces")

            self.assertDictEqual({"count": 0}, response)

    # Tests related to restart of ENIP device..
    # def test_send_NOP(self):
    #     # test tcp
    #     pass

    def test_malformend_request_tcp(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(4.0)
            s.connect((self.enip_server_tcp.addr, self.enip_server_tcp.port))
            s.send(
                b"e\x00\x04\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                + b"x00\x00\x01\x00\x00\x00"
            )  # test the help command
            try:
                _ = s.recv(1024)
            except socket.timeout:
                pass
        finally:
            s.close()
        # TODO: verify data packet?

    def test_malformend_request_udp(self):
        pass
