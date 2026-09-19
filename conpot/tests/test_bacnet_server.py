# Copyright (C) 2015  Peter Sooky <xsooky00@stud.fit.vutbr.cz>
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

import os
import struct
import unittest

import conpot
from bacpypes3.apdu import (
    APCISequence,
    AbortPDU,
    ErrorPDU,
    IAmRequest,
    IHaveRequest,
    ReadPropertyACK,
    ReadPropertyRequest,
    RejectPDU,
    SimpleAckPDU,
    WhoHasObject,
    WhoHasRequest,
    WhoIsRequest,
)
from bacpypes3.primitivedata import ObjectIdentifier, ObjectType, Real
from gevent import Timeout, socket

from conpot.protocols.bacnet import bacnet_server
from conpot.protocols.bacnet.bacnet_app import BACnetApp
from conpot.protocols.bacnet.bacnet_ip import decode_bacnet_ip, encode_bacnet_ip
from conpot.utils.greenlet import spawn_test_server, teardown_test_server


def nmap_read_property_query(property_id):
    """Build the BACnet/IP ReadProperty query used by nmap bacnet-info.nse."""
    return struct.pack(
        ">BBH7BIBB",
        0x81,  # BACnet/IP
        0x0A,  # Original-Unicast-NPDU
        0x0011,  # BVLC length
        0x01,  # NPDU version
        0x04,  # expecting reply
        0x00,  # Confirmed-REQ
        0x05,  # max APDU
        0x01,  # invoke id
        0x0C,  # readProperty
        0x0C,  # context tag 0, LVT 4
        0x023FFFFF,  # device, instance 4194303
        0x19,  # context tag 1, LVT 1
        property_id,
    )


class TestBACnetServer(unittest.TestCase):
    """
    All tests are executed in a similar way. We initiate a service request to the BACnet server and wait for response.
    Responses are decoded with bacpypes3 and checked field by field.
    """

    def setUp(self):
        self.bacnet_server, self.greenlet = spawn_test_server(
            bacnet_server.BacnetServer, "default", "bacnet"
        )
        self.assertTrue(self.bacnet_server.ready.wait(2))
        self.address = (self.bacnet_server.host, self.bacnet_server.port)

    def tearDown(self):
        teardown_test_server(self.bacnet_server, self.greenlet)

    def _exchange(self, request):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.sendto(encode_bacnet_ip(request), self.address)
        data = s.recvfrom(1024)[0]
        s.close()
        return data

    def _decode_service(self, data):
        return APCISequence.decode(decode_bacnet_ip(data, self.address))

    def test_whoIs(self):
        request = WhoIsRequest(
            deviceInstanceRangeLowLimit=500, deviceInstanceRangeHighLimit=50000
        )
        iam = self._decode_service(self._exchange(request))

        self.assertIsInstance(iam, IAmRequest)
        self.assertEqual(iam.iAmDeviceIdentifier[0], ObjectType("device"))
        self.assertEqual(int(iam.iAmDeviceIdentifier[1]), 36113)
        self.assertEqual(int(iam.maxAPDULengthAccepted), 1024)
        self.assertEqual(iam.segmentationSupported.attr, "segmentedBoth")
        self.assertEqual(int(iam.vendorID), 15)

    def test_whoHas(self):
        request = WhoHasRequest(
            object=WhoHasObject(objectIdentifier=("binary-input", 12))
        )
        ihave = self._decode_service(self._exchange(request))

        self.assertIsInstance(ihave, IHaveRequest)
        self.assertEqual(int(ihave.deviceIdentifier[1]), 36113)
        self.assertEqual(ihave.objectIdentifier[0], ObjectType("binary-input"))
        self.assertEqual(int(ihave.objectIdentifier[1]), 12)
        self.assertEqual(str(ihave.objectName), "BI 01")

    def test_readProperty(self):
        request = ReadPropertyRequest(
            objectIdentifier=("analog-input", 14), propertyIdentifier=85
        )
        request.apduInvokeID = 101
        ack = self._decode_service(self._exchange(request))

        self.assertIsInstance(ack, ReadPropertyACK)
        self.assertEqual(ack.apduInvokeID, 101)
        self.assertEqual(ack.objectIdentifier[0], ObjectType("analog-input"))
        self.assertEqual(int(ack.objectIdentifier[1]), 14)
        self.assertEqual(int(ack.propertyIdentifier), 85)
        self.assertEqual(float(ack.propertyValue.cast_out(Real)), 68.0)

    def test_nmap_vendor_id_query(self):
        """nmap bacnet-info ReadProperty(vendorIdentifier) against device/*."""
        query = nmap_read_property_query(0x78)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.sendto(query, self.address)
        response = s.recvfrom(1024)[0]
        s.close()

        self.assertEqual(response[0], 0x81)
        # APDU type Complex-ACK at BVLC(4) + NPDU(2) offset
        self.assertEqual(response[6] & 0xF0, 0x30)
        # vendorIdentifier is unsigned; tag 0x21 (1-byte) or 0x22 (2-byte)
        self.assertIn(response[17], (0x21, 0x22))
        if response[17] == 0x21:
            self.assertEqual(response[18], 15)
        else:
            self.assertEqual(struct.unpack(">H", response[18:20])[0], 15)

    def test_exclusive_bind_rejects_reuse(self):
        """BACnet must not share UDP port (nmap bacnet-info binds 47808)."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        with self.assertRaises(OSError):
            s.bind(self.address)
        s.close()

    def test_no_response_requests(self):
        """When the request has apduType not 0x01, no reply should be returned from Conpot"""
        payloads = [
            encode_bacnet_ip(SimpleAckPDU(service_choice=8, invoke_id=101)),
            encode_bacnet_ip(ErrorPDU(service_choice=8, invoke_id=101)),
            encode_bacnet_ip(RejectPDU(invoke_id=101, reason=9)),
            encode_bacnet_ip(AbortPDU(invoke_id=101, reason=9)),
        ]
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        buf_size = 1024
        for payload in payloads:
            s.sendto(payload, self.address)
        results = None
        with Timeout(1, False):
            results = [s.recvfrom(buf_size) for _ in payloads]
        self.assertIsNone(results)
        s.close()


class TestBACnetTemplate(unittest.TestCase):
    def test_objects_load_without_binding(self):
        conpot_dir = os.path.dirname(conpot.__file__)
        template_dir = os.path.join(conpot_dir, "templates", "default")
        protocol_xml = os.path.join(template_dir, "bacnet.xml")
        server = bacnet_server.BacnetServer(protocol_xml, template_dir, None)
        app = BACnetApp(server.thisDevice, None)
        app.get_objects_and_properties(server.dom)

        self.assertEqual(str(server.thisDevice.objectName), "SystemName")
        self.assertEqual(int(server.thisDevice.objectIdentifier[1]), 36113)
        self.assertEqual(int(server.thisDevice.vendorIdentifier), 15)

        analog = app.objectIdentifier[ObjectIdentifier(("analog-input", 14))]
        self.assertEqual(float(analog.presentValue), 68.0)
        binary = app.objectIdentifier[ObjectIdentifier(("binary-input", 12))]
        self.assertEqual(str(binary.objectName), "BI 01")
        door = app.objectIdentifier[ObjectIdentifier(("access-door", 16))]
        self.assertEqual(str(door.objectName), "Door 01")
