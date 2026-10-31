# Copyright (C) 2013 MushMush Foundation
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

import shutil
import socket
import struct
import tempfile
import unittest
from collections import namedtuple

from pysnmp.proto import rfc1902

import conpot.core as conpot_core
from conpot.protocols.snmp.snmp_server import SNMPServer
from conpot.tests.helpers import snmp_client
from conpot.utils.server_tasks import spawn_test_server, teardown_test_server


class TestSNMPServer(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

        args = namedtuple("FakeArgs", "mibcache")
        args.mibcache = self.tmp_dir

        self.snmp_server, self.handle = spawn_test_server(
            SNMPServer, template="default", protocol="snmp", args=args
        )

        self.host = "127.0.0.1"
        self.port = self.snmp_server.get_port()

    def tearDown(self):
        teardown_test_server(self.snmp_server, self.handle)
        shutil.rmtree(self.tmp_dir)

    def test_snmp_get(self):
        """
        Objective: Test if we can get data via snmp_get
        """
        client = snmp_client.SNMPClient(self.host, self.port)
        oid = ((1, 3, 6, 1, 2, 1, 1, 1, 0), None)
        client.get_command(oid, callback=self.mock_callback)
        self.assertEqual("Siemens, SIMATIC, S7-200", self.result)

    def test_snmp_set(self):
        """
        Objective: Test if we can set data via snmp_set
        """
        client = snmp_client.SNMPClient(self.host, self.port)
        # syslocation
        oid = ((1, 3, 6, 1, 2, 1, 1, 6, 0), rfc1902.OctetString("TESTVALUE"))
        client.set_command(oid, callback=self.mock_callback)
        databus = conpot_core.get_databus()
        self.assertEqual("TESTVALUE", databus.get_value("sysLocation"))

    def test_sys_object_id_is_not_pysnmp(self):
        """
        Objective: sysObjectID must not be PySNMP's own enterprise OID.
        """
        client = snmp_client.SNMPClient(self.host, self.port)
        oid = ((1, 3, 6, 1, 2, 1, 1, 2, 0), None)
        client.get_command(oid, callback=self.mock_callback)
        self.assertEqual("1.3.6.1.4.1.4329.6", self.result)

    def test_engine_id_hides_pysnmp_and_host(self):
        """
        Objective: snmpEngineID leaks neither PySNMP's enterprise nor the host name.
        """
        engine_id = bytes(self.snmp_server.cmd_responder.snmpEngine.snmpEngineID)
        self.assertEqual(struct.pack(">I", 0x80000000 | 4329), engine_id[:4])
        self.assertNotIn(b"\x4f\xb8", engine_id[:4])
        self.assertNotIn(socket.gethostname().encode(), engine_id)

    def mock_callback(
        self,
        snmpEngine,
        sendRequestHandle,
        errorIndication,
        errorStatus,
        errorIndex,
        varBindTable,
        cbCtx,
    ):
        self.result = None
        if errorIndication:
            self.result = errorIndication
        elif errorStatus:
            self.result = errorStatus.prettyPrint()
        else:
            for oid, val in varBindTable:
                self.result = val.prettyPrint()


class _RecordingResponder(object):
    def __init__(self):
        self.registered = []

    def register(self, mibname, symbolname, instance, value, profile_map_name):
        self.registered.append((mibname, symbolname, instance, value))


class TestSNMPIdentity(unittest.TestCase):
    """Unit tests for engine ID derivation and the sysObjectID fallback."""

    def setUp(self):
        args = namedtuple("FakeArgs", "mibcache")
        args.mibcache = None
        self.args = args

    def tearDown(self):
        conpot_core.get_databus().reset()

    def _server(self, template, **databus):
        conpot_core.get_databus().initialize(
            {"core": {"databus": {"key_value_mappings": databus}}}
        )
        return SNMPServer(template, "", self.args)

    def test_explicit_engine_id_is_used(self):
        server = self._server({"engine_id": "80:00:10:e9:05:01:02:03:04"})
        self.assertEqual(bytes.fromhex("800010e90501020304"), server.engine_id())

    def test_invalid_engine_id_is_rejected(self):
        for bad in ("zz", "8000"):
            server = self._server({"engine_id": bad})
            with self.assertRaises(ValueError):
                server.engine_id()

    def test_derived_engine_id_is_stable_and_uses_enterprise(self):
        template = {
            "mibs": [
                {
                    "name": "SNMPv2-MIB",
                    "symbols": [{"name": "sysObjectID", "value": "oid"}],
                }
            ]
        }
        first = self._server(template, oid="1.3.6.1.4.1.9.1.1", sysName="a")
        engine_id = first.engine_id()
        self.assertEqual(struct.pack(">IB", 0x80000000 | 9, 0x05), engine_id[:5])
        self.assertEqual(13, len(engine_id))
        second = self._server(template, oid="1.3.6.1.4.1.9.1.1", sysName="a")
        self.assertEqual(engine_id, second.engine_id())

    def test_unmapped_sys_object_id_gets_fallback(self):
        # @conpot_protocol wraps the class; set attributes on the real server.
        server = self._server({"mibs": []}).wrapped
        server.cmd_responder = _RecordingResponder()
        server.apply_mib_config()
        self.assertEqual(
            [("SNMPv2-MIB", "sysObjectID", (0,), "1.3.6.1.4.1.4329.6")],
            server.cmd_responder.registered,
        )
