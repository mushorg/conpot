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

import struct
import unittest
from copy import deepcopy

from bacpypes import bvll
from bacpypes.apdu import (
    APDU,
    IAmRequest,
    IHaveRequest,
    ReadPropertyACK,
    ReadPropertyRequest,
    WhoHasObject,
    WhoHasRequest,
    WhoIsRequest,
)
from bacpypes.bvll import BVLPDU, OriginalBroadcastNPDU, OriginalUnicastNPDU
from bacpypes.constructeddata import Any
from bacpypes.npdu import NPDU
from bacpypes.pdu import Address as PduAddress
from bacpypes.pdu import GlobalBroadcast, PDU
from bacpypes.primitivedata import Real
from gevent import Timeout, socket

from conpot.protocols.bacnet import bacnet_server
from conpot.utils.greenlet import spawn_test_server, teardown_test_server


def encode_bacnet_ip(request):
    """Wrap a bacpypes request/APDU in a BACnet/IP (BVLC+NPDU) datagram."""
    apdu = APDU()
    request.encode(apdu)
    npdu = NPDU()
    apdu.encode(npdu)
    pdu = PDU(user_data=npdu.pduUserData)
    npdu.encode(pdu)
    if pdu.pduDestination.addrType == PduAddress.localStationAddr:
        xpdu = OriginalUnicastNPDU(
            pdu, destination=pdu.pduDestination, user_data=pdu.pduUserData
        )
    elif pdu.pduDestination.addrType == PduAddress.localBroadcastAddr:
        xpdu = OriginalBroadcastNPDU(
            pdu, destination=pdu.pduDestination, user_data=pdu.pduUserData
        )
    else:
        raise RuntimeError("invalid destination address: {}".format(pdu.pduDestination))
    bvlpdu = BVLPDU()
    xpdu.encode(bvlpdu)
    out = PDU()
    bvlpdu.encode(out)
    return bytes(out.pduData)


def decode_bacnet_ip(data, address):
    """Decode a BACnet/IP datagram down to an APDU."""
    pdu = PDU(bytearray(data), source=PduAddress(address))
    bvlpdu = bvll.BVLPDU()
    bvlpdu.decode(pdu)
    rpdu = bvll.bvl_pdu_types[bvlpdu.bvlciFunction]()
    rpdu.decode(bvlpdu)
    npdu = NPDU(user_data=rpdu.pduUserData)
    npdu.decode(rpdu)
    apdu = APDU()
    apdu.decode(deepcopy(npdu))
    return apdu


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
    Instead of decoding the response, we create an expected response. We encode the expected response and compare the
    two encoded data.
    """

    def setUp(self):
        self.bacnet_server, self.greenlet = spawn_test_server(
            bacnet_server.BacnetServer, "default", "bacnet"
        )

        self.address = (self.bacnet_server.host, self.bacnet_server.port)

    def tearDown(self):
        teardown_test_server(self.bacnet_server, self.greenlet)

    def _exchange(self, request):
        request.pduDestination = PduAddress(self.address)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.sendto(encode_bacnet_ip(request), self.address)
        data = s.recvfrom(1024)[0]
        s.close()
        return data

    def test_whoIs(self):
        request = WhoIsRequest(
            deviceInstanceRangeLowLimit=500, deviceInstanceRangeHighLimit=50000
        )
        received_data = self._exchange(request)

        expected = IAmRequest()
        expected.pduDestination = GlobalBroadcast()
        expected.iAmDeviceIdentifier = ("device", 36113)
        expected.maxAPDULengthAccepted = 1024
        expected.segmentationSupported = "segmentedBoth"
        expected.vendorID = 15

        exp_apdu = APDU()
        expected.encode(exp_apdu)
        exp_pdu = PDU()
        exp_apdu.encode(exp_pdu)

        rec_pdu = PDU()
        decode_bacnet_ip(received_data, self.address).encode(rec_pdu)

        self.assertEqual(exp_pdu.pduData, rec_pdu.pduData)

    def test_whoHas(self):
        request_object = WhoHasObject()
        request_object.objectIdentifier = ("binaryInput", 12)
        request = WhoHasRequest(object=request_object)
        received_data = self._exchange(request)

        expected = IHaveRequest()
        expected.pduDestination = GlobalBroadcast()
        expected.deviceIdentifier = ("device", 36113)
        expected.objectIdentifier = ("binaryInput", 12)
        expected.objectName = "BI 01"

        exp_apdu = APDU()
        expected.encode(exp_apdu)
        exp_pdu = PDU()
        exp_apdu.encode(exp_pdu)

        rec_pdu = PDU()
        decode_bacnet_ip(received_data, self.address).encode(rec_pdu)

        self.assertEqual(exp_pdu.pduData, rec_pdu.pduData)

    def test_readProperty(self):
        request = ReadPropertyRequest(
            objectIdentifier=("analogInput", 14), propertyIdentifier=85
        )
        request.apduMaxResp = 1024
        request.apduInvokeID = 101
        received_data = self._exchange(request)

        expected = ReadPropertyACK()
        expected.pduDestination = GlobalBroadcast()
        expected.apduInvokeID = 101
        expected.objectIdentifier = ("analogInput", 14)
        expected.propertyIdentifier = 85
        expected.propertyValue = Any(Real(68.0))

        exp_apdu = APDU()
        expected.encode(exp_apdu)
        exp_pdu = PDU()
        exp_apdu.encode(exp_pdu)

        rec_pdu = PDU()
        decode_bacnet_ip(received_data, self.address).encode(rec_pdu)

        self.assertEqual(exp_pdu.pduData, rec_pdu.pduData)

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
        request = ReadPropertyRequest(
            objectIdentifier=("analogInput", 14), propertyIdentifier=85
        )
        request.apduMaxResp = 1024
        request.apduInvokeID = 101
        request.pduDestination = PduAddress(self.address)
        # Build requests - Confirmed, simple ack pdu, complex ack pdu, error pdu - etc.
        test_requests = list()

        for i in range(2, 8):
            if i not in {1, 3, 4}:
                request.apduType = i
                if i == 2:
                    # when apdu.apduType is 2 - we have SimpleAckPDU
                    # set the apduInvokeID and apduService
                    request.apduService = 8
                elif i == 5:
                    # when apdu.apduType is 5 - we have ErrorPDU
                    # set the apduInvokeID and apduService
                    request.apduService = 8
                elif i == 6:
                    # when apdu.apduType is 6 - we have RejectPDU
                    # set the apduAbortRejectReason
                    request.apduAbortRejectReason = 9
                else:
                    # when apdu.apduType is 7 - we have AbortPDU
                    # set the apduAbortRejectReason
                    request.apduAbortRejectReason = 9

                test_requests.append(encode_bacnet_ip(request))
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        buf_size = 1024
        [s.sendto(payload, self.address) for payload in test_requests]
        results = None
        with Timeout(1, False):
            results = [s.recvfrom(buf_size) for i in range(len(test_requests))]
        self.assertIsNone(results)
