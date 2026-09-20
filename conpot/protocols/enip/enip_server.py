# Copyright (C) 2017  Yuru Shao <shaoyuru@gmail.com>
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

import asyncio
import logging
import socket

import conpot.core as conpot_core
from conpot.core.protocol_wrapper import conpot_protocol
from conpot.protocols.enip.enip_protocol import (
    EnipProtocol,
    build_dispatcher,
    identity_from_config,
)
from conpot.utils.asyncio_serve import serve_tcp_sync_handler, serve_udp_datagram

logger = logging.getLogger(__name__)


class EnipConfig(object):
    """Configurations parsed from template."""

    def __init__(self, template):
        self.template = template
        self.parse_template()

    class Tag(object):
        """Device tag setting parsed from template."""

        def __init__(self, name, type, size, value, addr=None):
            self.name = name
            self.type = str(type).upper()
            self.size = size
            self.value = value
            self.addr = addr

    def parse_template(self):
        cfg = self.template
        self.server_addr = cfg["host"]
        self.server_port = int(cfg["port"])
        info = cfg["device_info"]
        self.vendor_id = int(info["VendorId"])
        self.device_type = int(info["DeviceType"])
        self.product_rev = int(info["ProductRevision"])
        self.product_code = int(info["ProductCode"])
        self.product_name = info["ProductName"]
        self.serial_number = str(info["SerialNumber"])
        self.mode = cfg["mode"]
        self.timeout = float(cfg["timeout"])
        self.latency = float(cfg["latency"])

        self.dtags = []
        for t in cfg.get("tags", []):
            name = t["name"]
            type = t["type"]
            value = t["value"]
            addr = t["addr"]
            try:
                size = int(t["size"])
            except Exception:
                raise AssertionError("Invalid tag size")
            self.dtags.append(self.Tag(name, type, size, value, addr))


@conpot_protocol
class EnipServer(object):
    """Ethernet/IP server (Conpot-owned I/O; cm-ethernetip CIP/encapsulation)."""

    def __init__(self, template, template_directory, args):
        self.config = EnipConfig(template)
        self.addr = self.config.server_addr
        self.port = self.config.server_port
        self.server = None
        self.protocol = None
        logger.debug("ENIP server serial number: %s", self.config.serial_number)
        logger.debug("ENIP server product name: %s", self.config.product_name)

    def _build_protocol(self, port):
        identity = identity_from_config(self.config)
        dispatcher = build_dispatcher(identity, self.config.dtags)
        return EnipProtocol(dispatcher, identity, port)

    def handle_tcp(self, sock, address):
        sock.settimeout(self.config.timeout)
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError as exc:
            logger.error("Unable to set TCP_NODELAY for %r: %s", address, exc)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except OSError as exc:
            logger.error("Unable to set SO_KEEPALIVE for %r: %s", address, exc)

        local = sock.getsockname()
        session = conpot_core.get_session(
            "enip", address[0], address[1], local[0], local[1]
        )
        logger.info(
            "New ENIP connection from %s:%s. (%s)", address[0], address[1], session.id
        )
        session.log_event(event_type="NEW_CONNECTION")

        protocol = self.protocol
        session_handle = 0
        accum = bytearray()
        try:
            while True:
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    logger.debug("ENIP TCP timeout from %s:%s", address[0], address[1])
                    break
                except OSError as exc:
                    logger.debug(
                        "ENIP TCP error from %s:%s: %s", address[0], address[1], exc
                    )
                    break
                if not chunk:
                    break
                accum.extend(chunk)
                while True:
                    msg, consumed = protocol.try_parse(bytes(accum), address)
                    if msg is None:
                        break
                    del accum[:consumed]
                    response, session_handle, is_nop = protocol.dispatch_message(
                        msg, session_handle, local[0]
                    )
                    if is_nop:
                        session.log_event(event_type="ENIP_NOP")
                        logger.info("Discarded EtherNet/IP NOP from %s", address)
                    if response is not None:
                        try:
                            sock.sendall(response)
                        except OSError as exc:
                            logger.debug(
                                "ENIP send failed to %s:%s: %s",
                                address[0],
                                address[1],
                                exc,
                            )
                            return
                        session.log_event(event_type="CONNECTION_CLOSED")
        finally:
            sock.close()

    def handle_udp(self, data, address):
        protocol = self.protocol
        local_addr = self.addr if self.addr not in ("0.0.0.0", "") else "127.0.0.1"
        try:
            sockname = self.server.socket.getsockname()
            local_addr = sockname[0]
            local_port = sockname[1]
        except Exception:
            local_port = self.port

        session = conpot_core.get_session(
            "enip", address[0], address[1], local_addr, local_port
        )
        session.log_event(event_type="NEW_CONNECTION")

        session_handle = 0
        accum = bytearray(data)
        try:
            while accum:
                msg, consumed = protocol.try_parse(bytes(accum), address)
                if msg is None:
                    # Incomplete / garbage datagram — drop remainder.
                    session.log_event(event_type="CONNECTION_FAILED")
                    return
                del accum[:consumed]
                response, session_handle, is_nop = protocol.dispatch_message(
                    msg, session_handle, local_addr
                )
                if is_nop:
                    session.log_event(event_type="ENIP_NOP")
                    logger.info("Discarded EtherNet/IP NOP from %s", address)
                    continue
                if response is not None:
                    self.server.sendto(response, address)
                    session.log_event(event_type="CONNECTION_CLOSED")
        except Exception:
            logger.exception("ENIP UDP handling failed for %s", address)
            session.log_event(event_type="CONNECTION_FAILED")

    def handle(self, *args):
        if getattr(self, "_mode", None) == "udp":
            return self.handle_udp(*args)
        return self.handle_tcp(*args)

    async def start(self, host, port):
        self.addr = host
        self.port = port
        self.protocol = self._build_protocol(port)
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()

        mode = (self.config.mode or "tcp").lower()
        self._mode = mode
        logger.info("ENIP server started on: %s:%d, mode: %s", host, port, mode)
        if mode == "udp":
            await serve_udp_datagram(
                host,
                port,
                self,
                stop_event=self._stop,
                ready_event=self._ready,
                name="EnipServer",
            )
        else:
            await serve_tcp_sync_handler(
                host,
                port,
                self,
                stop_event=self._stop,
                ready_event=self._ready,
                name="EnipServer",
            )

    def stop(self):
        logger.debug("Stopping ENIP server")
        if hasattr(self, "_stop"):
            self._stop.set()
