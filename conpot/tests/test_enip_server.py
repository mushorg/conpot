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

from conpot.protocols.enip.enip_server import EnipServer
from cpppo.server import enip
from cpppo.server.enip import client

class TestBase(unittest.TestCase):
    def setUp(self):
        template = reduce(os.path.join, 'conpot/templates/default/enip/enip.xml'.split('/'))
        self.enip_server = EnipServer(template, None, None)
        self.server_greenlet = gevent.spawn(self.enip_server.start, self.enip_server.addr, self.enip_server.port)
        self.server_greenlet.start()

    def tearDown(self):
        self.enip_server.stop()

    def test_list_services(self):
        with client.connector(host=self.enip_server.addr,
                              port=self.enip_server.port, timeout=5.0,
                              udp=False, broadcast=False) as connection:
            connection.list_services()
            connection.shutdown()
            while True:
                response, ela = client.await(connection, timeout=5.0)
                if response:
                    self.assertEqual("Communications",
                                     response['enip']['CIP']['list_services']['CPF']['item'][0]['communications_service']['service_name'])
                else:
                    break

    def test_list_identity(self):
        with client.connector(host=self.enip_server.addr,
                              port=self.enip_server.port, timeout=5.0,
                              udp=False, broadcast=False) as connection:
            connection.list_identity()
            connection.shutdown()
            while True:
                response, ela = client.await(connection, timeout=5.0)
                if response:
                    expected = self.enip_server.config.product_name
                    self.assertEqual(expected, response['enip']['CIP']['list_identity']['CPF']['item'][0]['identity_object']['product_name'])
                else:
                    break

    def attribute_operations(self, paths, int_type=None, **kwds):
        for op in client.parse_operations(paths, int_type=int_type or 'SINT', **kwds):
            path_end = op['path'][-1]
            if 'instance' in path_end:
                op['method'] = 'get_attributes_all'
                assert 'data' not in op, "All Attributes cannot be operated on using Set Attribute services"
            elif 'symbolic' in path_end or 'attribute' in path_end or 'element':
                op['method'] = 'set_attribute_single' if 'data' in op else 'get_attribute_single'
            else:
                raise AssertionError("Path invalid for Attribute services: %r", op['path'])
            yield op

    def test_read_tags(self):
        with client.connector(host=self.enip_server.addr,
                              port=self.enip_server.port, timeout=5.0) as connection:
            tags = ['@22/1/1']
            ops = self.attribute_operations(tags)
            for idx, dsc, op, rpy, sts, val in connection.pipeline(operations=ops):
                self.assertEqual(100, val[0])

    def test_write_tags(self):
        with client.connector(host=self.enip_server.addr,
                              port=self.enip_server.port, timeout=5.0) as connection:
            tags = ['@22/1/1=(SINT)50', '@22/1/1']
            ops = self.attribute_operations(tags)
            for idx, dsc, op, rpy, sts, val in connection.pipeline(operations=ops):
                if idx == 0:
                    self.assertEqual(True, val)
                elif idx == 1:
                    self.assertEqual(50, val[0])
