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

import gevent.monkey

gevent.monkey.patch_all()
import unittest
import os
from gevent import socket
import conpot
from conpot.protocols.enip.enip_server import EnipServer
from cpppo.server.enip import client


class TestENIPServer(unittest.TestCase):
    def setUp(self):
        # get the current directory
        self.dir_name = os.path.dirname(conpot.__file__)
        template = self.dir_name + "/templates/default/enip/enip.xml"
        # start the tcp server
        self.enip_server_tcp = EnipServer(template, None, None)
        self.enip_server_tcp.port = 50002
        self.server_greenlet_tcp = gevent.spawn(
            self.enip_server_tcp.start,
            self.enip_server_tcp.addr,
            self.enip_server_tcp.port,
        )
        self.enip_server_tcp.start_event.wait()
        self.assertFalse(self.server_greenlet_tcp.exception)

        # start the udp server
        self.enip_server_udp = EnipServer(template, None, None)
        self.enip_server_udp.config.mode = "udp"
        self.enip_server_udp.port = 60002
        self.server_greenlet_udp = gevent.spawn(
            self.enip_server_udp.start,
            self.enip_server_udp.addr,
            self.enip_server_udp.port,
        )
        self.enip_server_udp.start_event.wait()
        self.assertFalse(self.server_greenlet_udp.exception)

    def tearDown(self):
        self.enip_server_tcp.stop()
        self.enip_server_udp.stop()
        self.server_greenlet_tcp.join()
        self.server_greenlet_udp.join()

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

            expected = self.enip_server_tcp.config.product_name
            self.assertEqual(
                expected, response["item"][0]["identity_object"]["product_name"]
            )

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

            expected = self.enip_server_tcp.config.product_name
            self.assertEqual(
                expected, response["item"][0]["identity_object"]["product_name"]
            )

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
        s.connect((self.enip_server_tcp.addr, self.enip_server_tcp.port))
        s.send(
            b"e\x00\x04\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            + b"x00\x00\x01\x00\x00\x00"
        )  # test the help command
        _ = s.recv(1024)
        s.close()
        # TODO: verify data packet?

    def test_malformend_request_udp(self):
        pass


if __name__ == "__main__":
    unittest.main()
