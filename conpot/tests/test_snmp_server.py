# Copyright (C) 2013  Lukas Rist <glaslos@gmail.com>
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
import tempfile
import shutil

import gevent

from pysnmp.proto import rfc1902

import conpot.core as conpot_core
from conpot.tests.helpers import snmp_client
from conpot.protocols.snmp.snmp_server import SNMPServer


class TestBase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.host = '127.0.0.1'
        databus = conpot_core.get_databus()
        databus.initialize('conpot/templates/default.xml')
        self.snmp_server = SNMPServer(self.host, 0, 'conpot/templates/default.xml', [self.tmp_dir], [self.tmp_dir])
        self.port = self.snmp_server.get_port()
        self.server_greenlet = gevent.spawn(self.snmp_server.start)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_snmp_get(self):
        """
        Objective: Test if we can get data via snmp_get
        """
        client = snmp_client.SNMPClient(self.host, self.port)
        OID = ((1, 3, 6, 1, 2, 1, 1, 1, 0), None)
        client.get_command(OID, callback=self.mock_callback)
        self.assertEqual("Siemens, SIMATIC, S7-200", self.result)

    def test_snmp_set(self):
        """
        Objective: Test if we can set data via snmp_set
        """
        client = snmp_client.SNMPClient(self.host, self.port)
        # syslocation
        OID = ((1, 3, 6, 1, 2, 1, 1, 6, 0), rfc1902.OctetString('TESTVALUE'))
        client.set_command(OID, callback=self.mock_callback)
        databus = conpot_core.get_databus()
        self.assertEqual('TESTVALUE', databus.get_value('sysLocation'))

    def mock_callback(self, sendRequestHandle, errorIndication, errorStatus, errorIndex, varBindTable, cbCtx):
        self.result = None
        if errorIndication:
            self.result = errorIndication
        elif errorStatus:
            self.result = errorStatus.prettyPrint()
        else:
            for oid, val in varBindTable:
                self.result = val.prettyPrint()
