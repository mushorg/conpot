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

import gevent.monkey
gevent.monkey.patch_all()

import unittest
from collections import namedtuple

from gevent import monkey

from bacpypes.pdu import GlobalBroadcast, PDU

from bacpypes.apdu import APDU, WhoIsRequest, IAmRequest, IHaveRequest,  WhoHasObject,  WhoHasRequest, \
    ReadPropertyRequest, ReadPropertyACK

from conpot.protocols.bacnet import bacnet_server
import conpot.core as conpot_core

from bacpypes.constructeddata import Any
from bacpypes.primitivedata import Real

import socket

monkey.patch_all()


class TestBase(unittest.TestCase):

    """
        All tests are executed in a similar way. We initiate a service request to the BACnet server and wait for response.
        Instead of decoding the response, we create an expected response. We encode the expected response and compare the
        two encoded data.
    """

    def setUp(self):

        # clean up before we start...
        conpot_core.get_sessionManager().purge_sessions()

        self.databus = conpot_core.get_databus()
        self.databus.initialize('conpot/templates/default/template.xml')
        args = namedtuple('FakeArgs', '')
        self.bacnet_server = bacnet_server.BacnetServer('conpot/templates/default/bacnet/bacnet.xml', 'none', args)
        self.server_greenlet = gevent.spawn(self.bacnet_server.start, '0.0.0.0', 0)
        gevent.sleep(1)
        assert self.bacnet_server.server.server_port

    def tearDown(self):
        self.bacnet_server.stop()
        gevent.joinall([self.server_greenlet,])
        # tidy up (again)...
        conpot_core.get_sessionManager().purge_sessions()

    def test_whoIs(self):
        request = WhoIsRequest(deviceInstanceRangeLowLimit=500, deviceInstanceRangeHighLimit=50000)
        apdu = APDU()
        request.encode(apdu)
        pdu = PDU()
        apdu.encode(pdu)
        buf_size = 1024
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(pdu.pduData, ('127.0.0.1', self.bacnet_server.server.server_port))
        data = s.recvfrom(buf_size)

        received_data = data[0]

        expected = IAmRequest()
        expected.pduDestination = GlobalBroadcast()
        expected.iAmDeviceIdentifier = 36113
        expected.maxAPDULengthAccepted = 1024
        expected.segmentationSupported = 'segmentedBoth'
        expected.vendorID = 15

        exp_apdu = APDU()
        expected.encode(exp_apdu)
        exp_pdu = PDU()
        exp_apdu.encode(exp_pdu)

        self.assertEquals(exp_pdu.pduData, received_data)

    def test_whoHas(self):
        request_object = WhoHasObject()
        request_object.objectIdentifier = ('binaryInput', 12)
        request = WhoHasRequest(object=request_object)
        apdu = APDU()
        request.encode(apdu)
        pdu = PDU()
        apdu.encode(pdu)
        buf_size = 1024
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(pdu.pduData, ('127.0.0.1', self.bacnet_server.server.server_port))
        data = s.recvfrom(buf_size)

        received_data = data[0]

        expected = IHaveRequest()
        expected.pduDestination = GlobalBroadcast()
        expected.deviceIdentifier = 36113
        expected.objectIdentifier = 12
        expected.objectName = 'BI 01'

        exp_apdu = APDU()
        expected.encode(exp_apdu)
        exp_pdu = PDU()
        exp_apdu.encode(exp_pdu)

        self.assertEquals(exp_pdu.pduData, received_data)

    def test_readProperty(self):

        request = ReadPropertyRequest(objectIdentifier=('analogInput', 14), propertyIdentifier=85)
        request.apduMaxResp = 1024
        request.apduInvokeID = 101
        apdu = APDU()
        request.encode(apdu)
        pdu = PDU()
        apdu.encode(pdu)
        buf_size = 1024
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(pdu.pduData, ('127.0.0.1', self.bacnet_server.server.server_port))
        data = s.recvfrom(buf_size)

        received_data = data[0]

        expected = ReadPropertyACK()
        expected.pduDestination = GlobalBroadcast()
        expected.apduInvokeID = 101
        expected.objectIdentifier = 14
        expected.objectName = 'AI 01'
        expected.propertyIdentifier = 85
        expected.propertyValue = Any(Real(68.0))

        exp_apdu = APDU()
        expected.encode(exp_apdu)
        exp_pdu = PDU()
        exp_apdu.encode(exp_pdu)

        self.assertEquals(exp_pdu.pduData, received_data)

if __name__ == "__main__":
    unittest.main()
