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

"""Beckhoff ADS/AMS TCP honeypot — device info, state, index-group R/W."""

from __future__ import annotations

import asyncio
import logging
import socket
import struct

import conpot.core as conpot_core
from conpot.core.protocol_wrapper import conpot_protocol
from conpot.protocols.ads import ads_codec as ads
from conpot.utils.asyncio_serve import serve_tcp_sync_handler

logger = logging.getLogger(__name__)


@conpot_protocol
class AdsServer(object):
    def __init__(self, template, template_directory, args):
        self.timeout = float(template.get("timeout", 5))
        self.template = template
        self.server = None
        self.ams_net_id = ads.parse_ams_net_id(
            str(template.get("ams_net_id", "192.168.1.1.1.1"))
        )
        self.ams_port = int(template.get("ams_port", 851))
        self.device = {
            "ams_net_id": self.ams_net_id,
            "ams_port": self.ams_port,
            "device_name": str(template.get("device_name", "Conpot TwinCAT")),
            "version_major": int(template.get("version_major", 3)),
            "version_minor": int(template.get("version_minor", 1)),
            "version_build": int(template.get("version_build", 0)),
            "ads_state": int(template.get("ads_state", 5)),
            "device_state": int(template.get("device_state", 0)),
            "symbols": self._load_symbols(template),
        }
        logger.info(
            "Conpot ADS initialized (NetId=%s port=%s)",
            ads.format_ams_net_id(self.ams_net_id),
            self.ams_port,
        )

    @staticmethod
    def _load_symbols(template) -> list[dict]:
        symbols = []
        for entry in template.get("symbols", []) or []:
            value_hex = str(entry.get("value_hex", "")).replace(" ", "")
            try:
                value = bytearray.fromhex(value_hex) if value_hex else bytearray()
            except ValueError:
                logger.warning(
                    "Invalid value_hex for symbol %s; using empty",
                    entry.get("name"),
                )
                value = bytearray()
            symbols.append(
                {
                    "name": str(entry.get("name", "")),
                    "index_group": int(entry["index_group"]),
                    "index_offset": int(entry["index_offset"]),
                    "value": value,
                }
            )
        return symbols

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

    def _recv_frame(self, sock) -> bytes | None:
        header = self._recv_exact(sock, ads.AMS_TCP_HEADER_LENGTH)
        if not header:
            return None
        if len(header) < ads.AMS_TCP_HEADER_LENGTH:
            raise ads.AdsError("incomplete AMS/TCP header")
        reserved, length = struct.unpack_from("<HI", header, 0)
        if reserved != 0:
            raise ads.AdsError(f"unexpected AMS/TCP reserved field {reserved}")
        if length < ads.AMS_HEADER_LENGTH or length > ads.MAX_FRAME_LENGTH:
            raise ads.AdsError(f"invalid AMS length {length}")
        body = self._recv_exact(sock, length)
        if len(body) != length:
            raise ads.AdsError("incomplete AMS packet")
        return header + body

    def handle(self, sock, addr):
        # Idle scanners (e.g. nmap -A) often leave a TCP connection open with no
        # further data. Without a recv timeout the handler blocks forever and
        # the session never finishes (GitHub issue #441).
        sock.settimeout(self.timeout)
        session = conpot_core.get_session(
            "ads",
            addr[0],
            addr[1],
            sock.getsockname()[0],
            sock.getsockname()[1],
        )
        logger.info("New ADS connection from %s:%d. (%s)", addr[0], addr[1], session.id)
        session.log_event(event_type="NEW_CONNECTION")
        try:
            while True:
                try:
                    data = self._recv_frame(sock)
                except ads.AdsError as exc:
                    logger.warning("ADS framing error from %s: %s", addr, exc)
                    session.log_event(error=str(exc))
                    break
                if not data:
                    break

                try:
                    parsed = ads.unpack_ams_tcp_frame(data)
                    response = ads.handle_request(data, self.device)
                except ads.AdsError as exc:
                    logger.warning("ADS decode error from %s: %s", addr, exc)
                    session.log_event(error=str(exc), request=data.hex())
                    break

                sock.sendall(response)
                session.log_event(
                    event_type="REQUEST",
                    request={
                        "command": parsed["command_name"],
                        "command_id": parsed["command_id"],
                        "invoke_id": parsed["invoke_id"],
                        "source_net_id": ads.format_ams_net_id(parsed["source_net_id"]),
                        "source_port": parsed["source_port"],
                        "target_net_id": ads.format_ams_net_id(parsed["target_net_id"]),
                        "target_port": parsed["target_port"],
                        "raw": data.hex(),
                    },
                    response=response.hex(),
                )
        except socket.timeout:
            logger.debug("ADS timeout from %s:%d (%s)", addr[0], addr[1], session.id)
        except socket.error as exc:
            logger.debug(
                "ADS socket error from %s:%d (%s): %s",
                addr[0],
                addr[1],
                session.id,
                exc,
            )
        finally:
            logger.info(
                "ADS client disconnected %s:%d. (%s)",
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
        logger.info("ADS server starting on: %s", (host, port))
        await serve_tcp_sync_handler(
            host,
            port,
            self,
            stop_event=self._stop,
            ready_event=self._ready,
            name="AdsServer",
        )

    def stop(self):
        if hasattr(self, "_stop"):
            self._stop.set()
