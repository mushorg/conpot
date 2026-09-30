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

"""HART-IP TCP honeypot — session setup and scanner identity commands."""

from __future__ import annotations

import asyncio
import logging
import socket
import struct

import conpot.core as conpot_core
from conpot.core.protocol_wrapper import conpot_protocol
from conpot.protocols.hartip import hartip_codec as hartip
from conpot.utils.asyncio_serve import serve_tcp_sync_handler

logger = logging.getLogger(__name__)

MAX_PDU_LENGTH = 512


@conpot_protocol
class HartipServer(object):
    def __init__(self, template, template_directory, args):
        self.timeout = float(template.get("timeout", 5))
        self.template = template
        self.server = None
        self.identity = {
            "manufacturer_id": int(template.get("manufacturer_id", 176)),
            "private_label_distributor": int(
                template.get(
                    "private_label_distributor",
                    template.get("manufacturer_id", 176),
                )
            ),
            "expanded_device_type": int(template.get("expanded_device_type", 45075)),
            "device_id": template.get("device_id", "000001"),
            "long_tag": str(template.get("long_tag", "Conpot HART-IP Gateway")),
            "hart_revision": int(template.get("hart_revision", 7)),
            "device_revision": int(template.get("device_revision", 1)),
            "software_revision": int(template.get("software_revision", 1)),
            "hardware_revision": int(template.get("hardware_revision", 1)),
            "min_preambles": int(template.get("min_preambles", 5)),
            "min_preambles_slave": int(template.get("min_preambles_slave", 5)),
            "max_device_variables": int(template.get("max_device_variables", 1)),
            "config_change_counter": int(template.get("config_change_counter", 0)),
            "extended_device_status": int(template.get("extended_device_status", 0)),
            "flags": int(template.get("flags", 0)),
            "device_profile": int(template.get("device_profile", 1)),
        }
        logger.info("Conpot HART-IP initialized")

    def _recv_exact(self, sock, size: int) -> bytes:
        chunks = []
        remaining = size
        while remaining > 0:
            chunk = sock.recv(remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _recv_pdu(self, sock) -> bytes | None:
        header = self._recv_exact(sock, hartip.HEADER_LENGTH)
        if not header:
            return None
        if len(header) < hartip.HEADER_LENGTH:
            raise hartip.HartipError("incomplete HART-IP header")
        length = struct.unpack("!H", header[6:8])[0]
        if length < hartip.HEADER_LENGTH or length > MAX_PDU_LENGTH:
            raise hartip.HartipError(f"invalid HART-IP length {length}")
        rest = self._recv_exact(sock, length - hartip.HEADER_LENGTH)
        if len(rest) != length - hartip.HEADER_LENGTH:
            raise hartip.HartipError("incomplete HART-IP PDU")
        return header + rest

    def handle(self, sock, addr):
        # Idle scanners (e.g. nmap -A) often leave a TCP connection open with no
        # further data. Without a recv timeout the handler blocks forever and
        # the session never finishes (GitHub issue #441).
        sock.settimeout(self.timeout)
        session = conpot_core.get_session(
            "hartip",
            addr[0],
            addr[1],
            sock.getsockname()[0],
            sock.getsockname()[1],
        )
        logger.info(
            "New HART-IP connection from %s:%d. (%s)", addr[0], addr[1], session.id
        )
        session.log_event(event_type="NEW_CONNECTION")
        try:
            while True:
                try:
                    data = self._recv_pdu(sock)
                except hartip.HartipError as exc:
                    logger.warning("HART-IP framing error from %s: %s", addr, exc)
                    session.log_event(error=str(exc))
                    break
                if not data:
                    break

                try:
                    parsed = hartip.unpack_header(data)
                    response = hartip.handle_request(data, self.identity)
                except hartip.HartipError as exc:
                    logger.warning("HART-IP decode error from %s: %s", addr, exc)
                    session.log_event(error=str(exc), request=data.hex())
                    break

                if response is not None:
                    sock.sendall(response)

                session.log_event(
                    event_type="REQUEST",
                    request={
                        "message_id": parsed["message_name"],
                        "transaction_id": parsed["transaction_id"],
                        "raw": data.hex(),
                    },
                    response=response.hex() if response else None,
                )

                if parsed["message_id"] == hartip.MSG_ID_SESSION_CLOSE:
                    break
        except socket.timeout:
            logger.debug(
                "HART-IP timeout from %s:%d (%s)", addr[0], addr[1], session.id
            )
        except socket.error as exc:
            logger.debug(
                "HART-IP socket error from %s:%d (%s): %s",
                addr[0],
                addr[1],
                session.id,
                exc,
            )
        finally:
            logger.info(
                "HART-IP client disconnected %s:%d. (%s)",
                addr[0],
                addr[1],
                session.id,
            )
            session.log_event(event_type="CONNECTION_LOST")
            try:
                sock.close()
            except socket.error:
                pass

    async def start(self, host, port):
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        logger.info("HART-IP server starting on: %s", (host, port))
        await serve_tcp_sync_handler(
            host,
            port,
            self,
            stop_event=self._stop,
            ready_event=self._ready,
            name="HartipServer",
        )

    def stop(self):
        if hasattr(self, "_stop"):
            self._stop.set()
