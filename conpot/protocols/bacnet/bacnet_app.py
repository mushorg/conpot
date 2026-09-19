# Copyright (C) 2015  Peter Sooky <xsooky00@stud.fit.vubtr.cz>
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

# Author: Peter Sooky <xsooky00@stud.fit.vubtr.cz>
# Brno University of Technology, Faculty of Information Technology

import logging
import re
import sys

import bacpypes3.object
from bacpypes3.apdu import (
    APCISequence,
    ConfirmedServiceChoice,
    Error,
    ErrorPDU,
    IAmRequest,
    IHaveRequest,
    ReadPropertyACK,
    RejectPDU,
    UnconfirmedServiceChoice,
)
from bacpypes3.basetypes import PropertyIdentifier
from bacpypes3.errors import DecodingError, ExecutionError, PropertyError
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import ObjectIdentifier, ObjectType

from conpot.protocols.bacnet.bacnet_ip import encode_bacnet_ip, peer_address

logger = logging.getLogger(__name__)

# BACnet "any device" / wild-card instance used by scanners such as nmap
DEVICE_INSTANCE_WILDCARD = 4194303


class BACnetApp(object):
    """
    BACnet device emulation class. BACnet properties are populated from the template file. Services are defined.
    Conpot implements a smart sensor and hence
    - DM-RP-B (execute ReadProperty)
    - DM-DDB-B (execute Who-Is, initiate I-Am)
    - DM-DOB-B (execute Who-Has, initiate I-Have)
    services are supported.
    """

    def __init__(self, device, datagram_server):
        self._request = None
        self._response = None
        self._response_service = None
        self.localDevice = device
        self.objectName = {str(device.objectName): device}
        self.objectIdentifier = {device.objectIdentifier: device}
        self.datagram_server = datagram_server
        self.deviceIdentifier = device.objectIdentifier

    def get_objects_and_properties(self, dom):
        """
        parse the bacnet template for objects and their properties
        """
        device_property_list = dom.xpath("//bacnet/device_info/*")
        for prop in device_property_list:
            prop_key = self._property_key(prop.tag)
            if prop_key in ["deviceIdentifier", "deviceName"]:
                continue
            self.add_property(prop_key, prop.text)

        object_list = dom.xpath("//bacnet/object_list/object/@name")
        for obj in object_list:
            property_list = dom.xpath(
                '//bacnet/object_list/object[@name="%s"]/properties/*' % obj
            )
            object_type = None
            for prop in property_list:
                if prop.tag == "object_type":
                    object_type = re.sub("-", " ", prop.text).lower().title()
                    object_type = re.sub(" ", "", object_type) + "Object"
            try:
                object_class = getattr(bacpypes3.object, object_type)
            except AttributeError, TypeError:
                logger.critical("Non-existent BACnet object type")
                sys.exit(3)
            try:
                device_object = object_class()
            except Exception:
                logger.critical("Non-existent BACnet object type")
                sys.exit(3)
            for prop in property_list:
                prop_key = self._property_key(prop.tag)
                prop_val = prop.text
                if prop_key == "objectType":
                    prop_val = prop_val.lower().title()
                    prop_val = re.sub(" ", "", prop_val)
                    prop_val = prop_val[0].lower() + prop_val[1:]
                try:
                    if prop_key == "objectIdentifier":
                        device_object.objectIdentifier = (
                            device_object.objectType,
                            int(prop_val),
                        )
                    else:
                        setattr(device_object, prop_key, prop_val)
                except AttributeError, PropertyError, ValueError:
                    logger.critical("Non-existent BACnet property type: %s", prop_key)
                    sys.exit(3)
            self.add_object(device_object)
        self.deviceIdentifier = self.localDevice.objectIdentifier

    @staticmethod
    def _property_key(tag):
        prop_key = tag.lower().title()
        prop_key = re.sub("['_','-']", "", prop_key)
        return prop_key[0].lower() + prop_key[1:]

    def add_object(self, obj):
        object_name = obj.objectName
        if not object_name:
            raise RuntimeError("object name required")
        object_identifier = obj.objectIdentifier
        if not object_identifier:
            raise RuntimeError("object identifier required")
        object_name = str(object_name)
        if object_name in self.objectName:
            raise RuntimeError("object already added with the same name")
        if object_identifier in self.objectIdentifier:
            raise RuntimeError("object already added with the same identifier")

        self.objectName[object_name] = obj
        self.objectIdentifier[object_identifier] = obj

    def add_property(self, prop_name, prop_value):
        if not prop_name:
            raise RuntimeError("property name required")
        if not prop_value:
            raise RuntimeError("property value required")

        try:
            setattr(self.localDevice, prop_name, prop_value)
        except AttributeError, PropertyError, ValueError:
            logger.critical("Non-existent BACnet property type: %s", prop_name)
            sys.exit(3)

    def _in_instance_range(self, low, high):
        # Limits are optional (but if used, must be paired). The comparison is
        # inverted on purpose: it matches the historical Who-Is/Who-Has filter.
        if low is None or high is None:
            return True
        instance = int(self.deviceIdentifier[1])
        if low > instance > high:
            return False
        return True

    def iAm(self, *args):
        self._response = None
        return

    def iHave(self, *args):
        self._response = None
        return

    def whoIs(self, request, address, invoke_key, device):
        low = getattr(request, "deviceInstanceRangeLowLimit", None)
        high = getattr(request, "deviceInstanceRangeHighLimit", None)
        if not self._in_instance_range(low, high):
            logger.info("Bacnet WhoIsRequest out of range")
            self._response = None
            return

        self._response_service = "IAmRequest"
        self._response = IAmRequest(
            iAmDeviceIdentifier=self.deviceIdentifier,
            maxAPDULengthAccepted=int(self.localDevice.maxApduLengthAccepted),
            segmentationSupported=self.localDevice.segmentationSupported,
            vendorID=int(self.localDevice.vendorIdentifier),
        )
        self._response.pduDestination = peer_address(address)

    def whoHas(self, request, address, invoke_key, device):
        limits = getattr(request, "limits", None)
        if limits is not None:
            low = limits.deviceInstanceRangeLowLimit
            high = limits.deviceInstanceRangeHighLimit
        else:
            low = getattr(request, "deviceInstanceRangeLowLimit", None)
            high = getattr(request, "deviceInstanceRangeHighLimit", None)
        if not self._in_instance_range(low, high):
            logger.info("Bacnet WhoHasRequest out of range")
            self._response = None
            return

        wanted = getattr(request.object, "objectIdentifier", None)
        if wanted is None:
            logger.info("Bacnet WhoHasRequest: no object found")
            self._response = None
            return
        wanted = ObjectIdentifier(wanted)

        for obj, target in self.objectIdentifier.items():
            if obj != wanted:
                continue
            self._response_service = "IHaveRequest"
            self._response = IHaveRequest(
                deviceIdentifier=self.deviceIdentifier,
                objectIdentifier=obj,
                objectName=str(target.objectName),
            )
            self._response.pduDestination = peer_address(address)
            return

        logger.info("Bacnet WhoHasRequest: no object found")
        self._response = None

    def _read_property_value(self, obj, request):
        prop = PropertyIdentifier(request.propertyIdentifier)
        datatype = obj.get_property_type(prop)
        if datatype is None:
            raise PropertyError("unknownProperty")
        try:
            value = getattr(obj, prop.attr)
        except AttributeError:
            raise PropertyError("unknownProperty")
        # bacpypes3 rejects encoding an unset property as a typed null. Reply
        # with unknownProperty instead of a ComplexACK that cannot be encoded.
        if value is None:
            raise PropertyError("unknownProperty")
        array_index = getattr(request, "propertyArrayIndex", None)
        if array_index is not None:
            index = int(array_index)
            if index == 0:
                value = len(value)
            else:
                value = value[index]
        return value

    def readProperty(self, request, address, invoke_key, device):
        # Read Property — include the local device object and honor the
        # BACnet wild-card device instance (4194303) used by nmap bacnet-info.
        request_identifier = ObjectIdentifier(request.objectIdentifier)
        request_type = request_identifier[0]
        request_instance = int(request_identifier[1])

        for obj, target in self.objectIdentifier.items():
            obj_type = obj[0]
            matches_id = request_instance == int(obj[1]) and request_type == obj_type
            matches_wildcard = (
                request_type == ObjectType("device")
                and request_instance == DEVICE_INSTANCE_WILDCARD
                and obj_type == ObjectType("device")
            )
            if not (matches_id or matches_wildcard):
                continue

            try:
                property_value = self._read_property_value(target, request)
            except ExecutionError as error:
                self._response_service = "Error"
                self._response = Error(
                    errorClass=error.errorClass,
                    errorCode=error.errorCode,
                    context=request,
                    service_choice=request.apduService,
                )
                self._response.pduDestination = peer_address(address)
                return

            self._response_service = "ComplexAckPDU"
            self._response = ReadPropertyACK(
                objectIdentifier=obj,
                propertyIdentifier=request.propertyIdentifier,
                propertyValue=property_value,
            )
            if request.propertyArrayIndex is not None:
                self._response.propertyArrayIndex = request.propertyArrayIndex
            self._response.apduInvokeID = invoke_key
            self._response.pduDestination = peer_address(address)
            return

        logger.info(
            "Bacnet ReadProperty: object %s doesn't exist",
            request.objectIdentifier,
        )
        self._response_service = "Error"
        self._response = Error(
            errorClass="object",
            errorCode="unknownObject",
            context=request,
            service_choice=request.apduService,
        )
        self._response.pduDestination = peer_address(address)

    def _dispatch(self, request, address, invoke_key, device, choice_map):
        method_name = choice_map.get(request.apduService)
        if method_name is None:
            return False
        handler = getattr(self, method_name, None)
        if handler is None:
            logger.error("Not implemented Bacnet command")
            self._response = None
            return True
        handler(request, address, invoke_key, device)
        return True

    def indication(self, apdu, address, device):
        """logging the received PDU type and Service request"""
        self._response = None
        self._response_service = None
        invoke_key = getattr(apdu, "apduInvokeID", None)
        logger.info(
            "Bacnet PDU received from %s:%d. (%s)",
            address[0],
            address[1],
            type(apdu).__name__,
        )
        if apdu.apduType == 0x0:
            try:
                request = APCISequence.decode(apdu)
            except (
                AttributeError,
                RuntimeError,
                DecodingError,
                TypeError,
                ValueError,
            ):
                logger.warning("Bacnet indication: Invalid service.")
                return
            logger.info(
                "Bacnet indication from %s:%d. (%s)",
                address[0],
                address[1],
                type(request).__name__,
            )
            if not self._dispatch(
                request, address, invoke_key, device, ConfirmedServiceChoice._attr_map
            ):
                logger.info(
                    "Bacnet indication: Invalid confirmed service choice (%s)",
                    type(request).__name__,
                )
            return

        if apdu.apduType == 0x1:
            try:
                request = APCISequence.decode(apdu)
            except (
                AttributeError,
                RuntimeError,
                DecodingError,
                TypeError,
                ValueError,
            ):
                logger.exception("Bacnet indication: Invalid service.")
                return
            logger.info(
                "Bacnet indication from %s:%d. (%s)",
                address[0],
                address[1],
                type(request).__name__,
            )
            if self._dispatch(
                request,
                address,
                invoke_key,
                device,
                UnconfirmedServiceChoice._attr_map,
            ):
                return
            logger.info(
                "Bacnet indication: Invalid unconfirmed service choice (%s)",
                type(request).__name__,
            )
            self._response_service = "ErrorPDU"
            self._response = ErrorPDU()
            self._response.pduDestination = peer_address(address)
            return

        # simple ack, complex ack, segment ack, error, reject, abort, reserved
        if 0x2 <= apdu.apduType <= 0xF:
            return

        logger.info("Bacnet Unrecognized service")

    def response(self, response_apdu, address):
        if response_apdu is None:
            return
        if response_apdu.pduDestination is None:
            response_apdu.pduDestination = peer_address(address)
        payload = encode_bacnet_ip(response_apdu)
        destination = response_apdu.pduDestination
        if isinstance(response_apdu, (RejectPDU, ErrorPDU)):
            self.datagram_server.sendto(payload, address)
        elif destination.addrType in (
            Address.localBroadcastAddr,
            Address.globalBroadcastAddr,
        ):
            self.datagram_server.sendto(payload, ("", address[1]))
        else:
            self.datagram_server.sendto(payload, address)
        logger.info(
            "Bacnet response sent to %s (%s:%s)",
            destination,
            type(response_apdu).__name__,
            self._response_service,
        )
