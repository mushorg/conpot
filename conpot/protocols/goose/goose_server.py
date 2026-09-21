# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""IEC 61850-90-5 Routed-GOOSE (R-GOOSE) UDP honeypot server."""

from __future__ import annotations

import asyncio
import logging
import socket
import struct

import conpot.core as conpot_core
from conpot.core.protocol_wrapper import conpot_protocol
from conpot.protocols.goose.goose_apdu import decode_goose_apdu, encode_goose_apdu
from conpot.protocols.goose.session90_5 import (
    SI_R_GOOSE,
    Session90_5Error,
    pack_rgoose,
    unpack_rgoose,
)
from conpot.utils.asyncio_serve import serve_udp_datagram
from conpot.utils.networking import get_interface_ip

logger = logging.getLogger(__name__)


def _parse_all_data(entries) -> list:
    values = []
    for entry in entries or []:
        if isinstance(entry, dict):
            if "boolean" in entry:
                values.append(bool(entry["boolean"]))
            elif "integer" in entry:
                values.append(int(entry["integer"]))
            else:
                raise ValueError(f"all_data entry needs boolean or integer: {entry}")
        elif isinstance(entry, bool):
            values.append(entry)
        elif isinstance(entry, int):
            values.append(entry)
        else:
            raise ValueError(f"unsupported all_data entry: {entry!r}")
    return values


@conpot_protocol
class GooseServer(object):
    def __init__(self, template, template_directory, args):
        self.template = template
        self.server = None
        self.appid = int(template.get("appid", 1)) & 0xFFFF
        self.gocb_ref = str(template.get("gocb_ref", "IED1/LLN0$GO$gcb01"))
        self.dat_set = str(template.get("dat_set", "IED1/LLN0$dataset1"))
        self.go_id = str(template.get("go_id", "GOOSE1"))
        self.conf_rev = int(template.get("conf_rev", 1))
        self.time_allowed_to_live = int(template.get("time_allowed_to_live", 10000))
        self.publish_interval_ms = float(template.get("publish_interval_ms", 1000))
        self.publish_dest = str(template.get("publish_dest", "127.0.0.1"))
        self.publish_dest_port = int(template.get("publish_dest_port", 0))
        self.multicast_group = template.get("multicast_group")
        self.st_num = int(template.get("st_num", 1))
        self.sq_num = int(template.get("sq_num", 0))
        self.spdu_number = int(template.get("spdu_number", 1))
        self.all_data = _parse_all_data(template.get("all_data", [{"boolean": False}]))
        self._publish_task = None
        logger.info("Conpot R-GOOSE (UDP) initialized")

    def handle(self, data, address):
        if not data or data[0] != SI_R_GOOSE:
            logger.debug(
                "Ignoring non-R-GOOSE datagram from %s:%d (%d bytes)",
                address[0],
                address[1],
                len(data) if data else 0,
            )
            return

        session = conpot_core.get_session(
            "goose",
            address[0],
            address[1],
            get_interface_ip(address[0]),
            self.server.server_port,
        )
        logger.info(
            "New R-GOOSE datagram from %s:%d. (%s)",
            address[0],
            address[1],
            session.id,
        )
        session.log_event(event_type="NEW_CONNECTION")
        try:
            try:
                framed = unpack_rgoose(data)
                apdu = decode_goose_apdu(framed["goose_apdu"])
            except (Session90_5Error, ValueError) as exc:
                logger.warning(
                    "R-GOOSE decode error from %s:%d: %s",
                    address[0],
                    address[1],
                    exc,
                )
                session.log_event(error=str(exc), request=data.hex())
                return

            request = {
                "appid": framed["appid"],
                "spdu_number": framed["spdu_number"],
                "simulation": framed["simulation"],
                "gocb_ref": apdu["gocb_ref"],
                "go_id": apdu["go_id"],
                "dat_set": apdu["dat_set"],
                "st_num": apdu["st_num"],
                "sq_num": apdu["sq_num"],
                "conf_rev": apdu["conf_rev"],
                "time_allowed_to_live": apdu["time_allowed_to_live"],
                "all_data": apdu["all_data"],
            }
            session.log_event(event_type="REQUEST", request=request)
        finally:
            logger.info(
                "R-GOOSE client done %s:%d. (%s)",
                address[0],
                address[1],
                session.id,
            )
            session.log_event(event_type="CONNECTION_LOST")

    def _build_publish_packet(self) -> bytes:
        apdu = encode_goose_apdu(
            gocb_ref=self.gocb_ref,
            time_allowed_to_live=self.time_allowed_to_live,
            dat_set=self.dat_set,
            go_id=self.go_id,
            st_num=self.st_num,
            sq_num=self.sq_num,
            conf_rev=self.conf_rev,
            all_data=self.all_data,
        )
        packet = pack_rgoose(
            apdu,
            appid=self.appid,
            spdu_number=self.spdu_number,
        )
        self.sq_num = (self.sq_num + 1) & 0xFFFFFFFF
        self.spdu_number = (self.spdu_number + 1) & 0xFFFFFFFF
        return packet

    async def _publish_loop(self):
        interval = max(self.publish_interval_ms, 50.0) / 1000.0
        while not self._stop.is_set():
            try:
                dest_port = self.publish_dest_port or self.server.server_port
                dest = (self.publish_dest, int(dest_port))
                packet = self._build_publish_packet()
                self.server.sendto(packet, dest)
                logger.debug(
                    "Published R-GOOSE to %s:%d (appid=0x%04x sqNum=%d)",
                    dest[0],
                    dest[1],
                    self.appid,
                    (self.sq_num - 1) & 0xFFFFFFFF,
                )
            except Exception:
                logger.exception("R-GOOSE publish failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue

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
            logger.info("Joined multicast group %s on %s", group, host)
        except OSError:
            logger.exception("Failed to join multicast group %s", group)

    async def start(self, host, port):
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        logger.info("R-GOOSE server starting on: %s", (host, port))

        serve_task = asyncio.create_task(
            serve_udp_datagram(
                host,
                port,
                self,
                stop_event=self._stop,
                ready_event=self._ready,
                name="GooseServer",
                reuse_address=True,
                broadcast=False,
            )
        )
        await self._ready.wait()

        join_host = "0.0.0.0" if host in ("0.0.0.0", "") else host
        self._maybe_join_multicast(join_host)

        self._publish_task = asyncio.create_task(
            self._publish_loop(), name="GooseServer-publish"
        )
        try:
            await serve_task
        finally:
            if self._publish_task is not None:
                self._publish_task.cancel()
                try:
                    await self._publish_task
                except asyncio.CancelledError:
                    pass

    def stop(self):
        if hasattr(self, "_stop"):
            self._stop.set()
