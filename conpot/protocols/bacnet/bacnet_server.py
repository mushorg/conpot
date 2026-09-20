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

import conpot.core as conpot_core
from conpot.core.protocol_wrapper import conpot_protocol
from conpot.protocols.bacnet.bacnet_app import BACnetApp
from conpot.protocols.bacnet.bacnet_ip import decode_bacnet_ip
from conpot.utils.asyncio_serve import serve_udp_datagram
from conpot.utils.networking import get_interface_ip

logger = logging.getLogger(__name__)


def build_device_object(template):
    """Build the local device object from a BACnet template dict."""
    device_info = template["device_info"]
    return DeviceObject(
        objectName=str(device_info["device_name"]),
        objectIdentifier=("device", int(device_info["device_identifier"])),
        maxApduLengthAccepted=int(device_info["max_apdu_length_accepted"]),
        segmentationSupported=str(device_info["segmentation_supported"]),
        vendorName=str(device_info["vendor_name"]),
        vendorIdentifier=int(device_info["vendor_identifier"]),
    )


@conpot_protocol
class BacnetServer(object):
    def __init__(self, template, template_directory, args):
        self.template = template
        self.thisDevice = build_device_object(template)
        self.bacnet_app = None
        self.server = None  # Initialize later
        logger.info("Conpot Bacnet initialized")

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
        session.log_event(event_type="NEW_CONNECTION")
        try:
            apdu = decode_bacnet_ip(data, address)
        except DecodingError:
            logger.warning("DecodingError - BACnet/IP PDU: %s", data.hex())
            session.log_event(error="DecodingError")
            return
        except Exception:
            logger.exception("Failed to decode BACnet/IP datagram")
            return
        self.bacnet_app.indication(apdu, address, self.thisDevice)
        # send an appropriate response from BACnet app to the attacker
        self.bacnet_app.response(self.bacnet_app._response, address)
        session.log_event(request=data.hex())
        logger.info(
            "Bacnet client disconnected %s:%d. (%s)", address[0], address[1], session.id
        )
        session.log_event(event_type="CONNECTION_LOST")

    async def start(self, host, port):
        self._stop = asyncio.Event()
        self.ready = asyncio.Event()
        self._ready = self.ready
        # BACnetApp needs .sendto on its datagram_server; we expose it on self
        # and the UDP facade (self.server) is assigned before ready is set.
        self.bacnet_app = BACnetApp(self.thisDevice, self)
        self.bacnet_app.get_objects_and_properties(self.template)
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
