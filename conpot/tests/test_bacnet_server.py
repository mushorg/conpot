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

import unittest
from gevent import socket, Timeout

from bacpypes.pdu import GlobalBroadcast, PDU
from bacpypes.apdu import (
    APDU,
    WhoIsRequest,
    IAmRequest,
    IHaveRequest,
    WhoHasObject,
    WhoHasRequest,
    ReadPropertyRequest,
    ReadPropertyACK,
)
from bacpypes.constructeddata import Any
from bacpypes.primitivedata import Real

from conpot.protocols.bacnet import bacnet_server
from conpot.utils.greenlet import spawn_test_server, teardown_test_server


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

    def test_whoIs(self):
        request = WhoIsRequest(
            deviceInstanceRangeLowLimit=500, deviceInstanceRangeHighLimit=50000
        )
        apdu = APDU()
        request.encode(apdu)
        pdu = PDU()
        apdu.encode(pdu)
        buf_size = 1024
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(pdu.pduData, self.address)
        data = s.recvfrom(buf_size)
        s.close()
        received_data = data[0]

        expected = IAmRequest()
        expected.pduDestination = GlobalBroadcast()
        expected.iAmDeviceIdentifier = 36113
        expected.maxAPDULengthAccepted = 1024
        expected.segmentationSupported = "segmentedBoth"
        expected.vendorID = 15

        exp_apdu = APDU()
        expected.encode(exp_apdu)
        exp_pdu = PDU()
        exp_apdu.encode(exp_pdu)

        self.assertEqual(exp_pdu.pduData, received_data)

    def test_whoHas(self):
        request_object = WhoHasObject()
        request_object.objectIdentifier = ("binaryInput", 12)
        request = WhoHasRequest(object=request_object)
        apdu = APDU()
        request.encode(apdu)
        pdu = PDU()
        apdu.encode(pdu)
        buf_size = 1024
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(pdu.pduData, self.address)
        data = s.recvfrom(buf_size)
        s.close()
        received_data = data[0]

        expected = IHaveRequest()
        expected.pduDestination = GlobalBroadcast()
        expected.deviceIdentifier = 36113
        expected.objectIdentifier = 12
        expected.objectName = "BI 01"

        exp_apdu = APDU()
        expected.encode(exp_apdu)
        exp_pdu = PDU()
        exp_apdu.encode(exp_pdu)
        self.assertEqual(exp_pdu.pduData, received_data)

    def test_readProperty(self):
        request = ReadPropertyRequest(
            objectIdentifier=("analogInput", 14), propertyIdentifier=85
        )
        request.apduMaxResp = 1024
        request.apduInvokeID = 101
        apdu = APDU()
        request.encode(apdu)
        pdu = PDU()
        apdu.encode(pdu)
        buf_size = 1024
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(pdu.pduData, self.address)
        data = s.recvfrom(buf_size)
        s.close()
        received_data = data[0]

        expected = ReadPropertyACK()
        expected.pduDestination = GlobalBroadcast()
        expected.apduInvokeID = 101
        expected.objectIdentifier = 14
        expected.objectName = "AI 01"
        expected.propertyIdentifier = 85
        expected.propertyValue = Any(Real(68.0))

        exp_apdu = APDU()
        expected.encode(exp_apdu)
        exp_pdu = PDU()
        exp_apdu.encode(exp_pdu)

        self.assertEqual(exp_pdu.pduData, received_data)

    def test_no_response_requests(self):
        """When the request has apduType not 0x01, no reply should be returned from Conpot"""
        request = ReadPropertyRequest(
            objectIdentifier=("analogInput", 14), propertyIdentifier=85
        )
        request.pduData = bytearray(b"test_data")
        request.apduMaxResp = 1024
        request.apduInvokeID = 101
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
                    # set the apduInvokeID and apduAbortRejectReason
                    request.apduAbortRejectReason = 9
                else:
                    # when apdu.apduType is 7 - we have AbortPDU
                    # set the apduInvokeID and apduAbortRejectReason
                    request.apduAbortRejectReason = 9

                test_requests.append(request)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        buf_size = 1024
        [s.sendto(i.pduData, self.address) for i in test_requests]
        results = None
        with Timeout(1, False):
            results = [s.recvfrom(buf_size) for i in range(len(test_requests))]
        self.assertIsNone(results)
