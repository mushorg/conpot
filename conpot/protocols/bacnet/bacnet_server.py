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

import asyncio
import logging

from bacpypes3.errors import DecodingError
from bacpypes3.object import DeviceObject
from lxml import etree

import conpot.core as conpot_core
from conpot.core.protocol_wrapper import conpot_protocol
from conpot.protocols.bacnet.bacnet_app import BACnetApp
from conpot.protocols.bacnet.bacnet_ip import decode_bacnet_ip
from conpot.utils.asyncio_serve import serve_udp_datagram
from conpot.utils.networking import get_interface_ip

logger = logging.getLogger(__name__)


def build_device_object(dom):
    """Build the local device object from a BACnet template DOM."""
    device_info_root = dom.xpath("//bacnet/device_info")[0]
    name_key = device_info_root.xpath("./device_name/text()")[0]
    id_key = device_info_root.xpath("./device_identifier/text()")[0]
    vendor_name_key = device_info_root.xpath("./vendor_name/text()")[0]
    vendor_identifier_key = device_info_root.xpath("./vendor_identifier/text()")[0]
    apdu_length_key = device_info_root.xpath("./max_apdu_length_accepted/text()")[0]
    segmentation_key = device_info_root.xpath("./segmentation_supported/text()")[0]
    return DeviceObject(
        objectName=name_key,
        objectIdentifier=("device", int(id_key)),
        maxApduLengthAccepted=int(apdu_length_key),
        segmentationSupported=segmentation_key,
        vendorName=vendor_name_key,
        vendorIdentifier=int(vendor_identifier_key),
    )


@conpot_protocol
class BacnetServer(object):
    def __init__(self, template, template_directory, args):
        self.dom = etree.parse(template)
        self.thisDevice = build_device_object(self.dom)
        self.bacnet_app = None
        self.server = None  # Initialize later
        logger.info("Conpot Bacnet initialized using the %s template.", template)

    def sendto(self, data, address):
        """BACnetApp sends replies through the bound UDP facade."""
        self.server.sendto(data, address)

    def handle(self, data, address):
        # I'm not sure if the UDP server handles issues where the
        # received data is over the MTU -> fragmentation
        if not data or data[0] != 0x81:
            # Ignore non-BACnet/IP traffic (empty UDP probes, unrelated scanners)
            logger.debug(
                "Ignoring non-BACnet/IP datagram from %s:%d (%d bytes)",
                address[0],
                address[1],
                len(data) if data else 0,
            )
            return

        session = conpot_core.get_session(
            "bacnet",
            address[0],
            address[1],
            get_interface_ip(address[0]),
            self.server.server_port,
        )
        logger.info(
            "New Bacnet connection from %s:%d. (%s)", address[0], address[1], session.id
        )
        session.add_event({"type": "NEW_CONNECTION"})
        try:
            apdu = decode_bacnet_ip(data, address)
        except DecodingError:
            logger.warning("DecodingError - BACnet/IP PDU: %s", data.hex())
            return
        except Exception:
            logger.exception("Failed to decode BACnet/IP datagram")
            return
        self.bacnet_app.indication(apdu, address, self.thisDevice)
        # send an appropriate response from BACnet app to the attacker
        self.bacnet_app.response(self.bacnet_app._response, address)
        logger.info(
            "Bacnet client disconnected %s:%d. (%s)", address[0], address[1], session.id
        )

    async def start(self, host, port):
        self._stop = asyncio.Event()
        self.ready = asyncio.Event()
        self._ready = self.ready
        # BACnetApp needs .sendto on its datagram_server; we expose it on self
        # and the UDP facade (self.server) is assigned before ready is set.
        self.bacnet_app = BACnetApp(self.thisDevice, self)
        self.bacnet_app.get_objects_and_properties(self.dom)
        logger.info("Bacnet server started on: %s", (host, port))
        # Exclusive bind (reuse_address=False) so scanners such as nmap
        # bacnet-info cannot also bind UDP/47808 and read their own probes.
        await serve_udp_datagram(
            host,
            port,
            self,
            stop_event=self._stop,
            ready_event=self._ready,
            name="BacnetServer",
            reuse_address=False,
            broadcast=True,
        )

    def stop(self):
        if hasattr(self, "_stop"):
            self._stop.set()
