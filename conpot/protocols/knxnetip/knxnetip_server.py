# Copyright (C) 2026 MushMush Foundation
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

"""KNXnet/IP UDP honeypot — SEARCH and DESCRIPTION gateway subset."""

from __future__ import annotations

import asyncio
import logging
import socket
import struct

import conpot.core as conpot_core
from conpot.core.protocol_wrapper import conpot_protocol
from conpot.protocols.knxnetip import knxip_codec as knxip
from conpot.utils.asyncio_serve import serve_udp_datagram
from conpot.utils.networking import get_interface_ip

logger = logging.getLogger(__name__)


@conpot_protocol
class KnxnetipServer(object):
    def __init__(self, template, template_directory, args):
        self.template = template
        self.server = None
        self.multicast_group = str(
            template.get("multicast_group", knxip.DEFAULT_MULTICAST)
        )
        self.identity = {
            "friendly_name": str(template.get("friendly_name", "Conpot KNX IP")),
            "individual_address": str(template.get("individual_address", "1.1.1")),
            "serial_number": str(template.get("serial_number", "00fa00000001")),
            "mac_address": str(template.get("mac_address", "00:fa:00:00:00:01")),
            "medium": int(template.get("medium", knxip.KNX_MEDIUM_TP1)),
            "device_status": int(template.get("device_status", 0)),
            "project_installation_id": int(template.get("project_installation_id", 0)),
            "multicast_group": self.multicast_group,
            "manufacturer_id": int(template.get("manufacturer_id", 0x00FA)),
        }
        logger.info("Conpot KNXnet/IP initialized")

    def _control_endpoint(self, peer_ip: str) -> tuple[str, int]:
        host = self.server.server_host
        if host in ("0.0.0.0", "", "::"):
            host = get_interface_ip(peer_ip)
        return host, int(self.server.server_port)

    def handle(self, data, address):
        if not data or len(data) < knxip.HEADER_SIZE:
            logger.debug(
                "Ignoring short datagram from %s:%d (%d bytes)",
                address[0],
                address[1],
                len(data) if data else 0,
            )
            return
        if data[0] != knxip.HEADER_LENGTH or data[1] != knxip.PROTOCOL_VERSION:
            logger.debug(
                "Ignoring non-KNXnet/IP datagram from %s:%d (%d bytes)",
                address[0],
                address[1],
                len(data),
            )
            return

        session = conpot_core.get_session(
            "knxnetip",
            address[0],
            address[1],
            get_interface_ip(address[0]),
            self.server.server_port,
        )
        logger.info(
            "New KNXnet/IP datagram from %s:%d. (%s)",
            address[0],
            address[1],
            session.id,
        )
        session.log_event(event_type="NEW_CONNECTION")
        try:
            try:
                parsed = knxip.unpack_header(data)
            except knxip.KnxipError as exc:
                logger.warning("KNXnet/IP decode error from %s: %s", address, exc)
                session.log_event(error=str(exc), request=data.hex())
                return

            service = parsed["service_type"]
            service_name = parsed["service_name"]
            response = None
            if service == knxip.SERVICE_SEARCH_REQUEST:
                ctrl_ip, ctrl_port = self._control_endpoint(address[0])
                response = knxip.build_search_response(
                    ctrl_ip, ctrl_port, self.identity
                )
            elif service == knxip.SERVICE_DESCRIPTION_REQUEST:
                response = knxip.build_description_response(self.identity)
            else:
                logger.debug(
                    "Ignoring unsupported KNXnet/IP service %s from %s:%d",
                    service_name,
                    address[0],
                    address[1],
                )

            if response is not None:
                self.server.sendto(response, address)

            session.log_event(
                event_type="REQUEST",
                request={
                    "service": service_name,
                    "service_type": f"0x{service:04X}",
                    "raw": data.hex(),
                },
                response=response.hex() if response else None,
            )
        finally:
            logger.info(
                "KNXnet/IP client done %s:%d. (%s)",
                address[0],
                address[1],
                session.id,
            )
            session.log_event(event_type="CONNECTION_LOST")

    def _maybe_join_multicast(self, host: str):
        group = self.multicast_group
        if not group:
            return
        sock = self.server.socket
        try:
            mreq = struct.pack(
                "!4s4s", socket.inet_aton(str(group)), socket.inet_aton(host)
            )
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            logger.info("Joined KNXnet/IP multicast group %s on %s", group, host)
        except OSError:
            logger.exception("Failed to join multicast group %s", group)

    async def start(self, host, port):
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        logger.info("KNXnet/IP server starting on: %s", (host, port))

        serve_task = asyncio.create_task(
            serve_udp_datagram(
                host,
                port,
                self,
                stop_event=self._stop,
                ready_event=self._ready,
                name="KnxnetipServer",
                reuse_address=False,
                broadcast=True,
            )
        )
        await self._ready.wait()

        join_host = "0.0.0.0" if host in ("0.0.0.0", "") else host
        self._maybe_join_multicast(join_host)

        try:
            await serve_task
        finally:
            if not serve_task.done():
                serve_task.cancel()

    def stop(self):
        if hasattr(self, "_stop"):
            self._stop.set()
