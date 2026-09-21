# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""DNP3 outstation honeypot protocol (IEEE 1815 via dnp3py)."""

from __future__ import annotations

import asyncio
import logging

from dnp3.core.flags import AnalogQuality, BinaryQuality
from dnp3.database import AnalogInputConfig, BinaryInputConfig, Database, EventClass
from dnp3.outstation import Outstation, OutstationConfig
from dnp3.outstation.config import UnsolicitedConfig

import conpot.core as conpot_core
from conpot.core.protocol_wrapper import conpot_protocol
from conpot.protocols.dnp3.session import (
    StreamChannel,
    _is_peer_disconnect,
    run_outstation_session,
)
from conpot.utils.asyncio_serve import serve_tcp_async_handler

logger = logging.getLogger(__name__)


@conpot_protocol
class DNP3Server(object):
    """DNP3/TCP honeypot.

    Conpot owns accept / session / timeouts. dnp3py Outstation owns application
    PDUs. Multiple concurrent clients share one Outstation/Database (same as a
    real RTU exposing one point table).
    """

    def __init__(self, template, template_directory, args):
        self.timeout = float(template.get("timeout", 5))
        self.host = None
        self.port = None
        self.server = None
        self.template = template
        self.databus = conpot_core.get_databus()

        outstation_address = int(template.get("outstation_address", 1))
        master_address = int(template.get("master_address", 0))
        unsolicited_enabled = bool(template.get("unsolicited_enabled", False))

        self.database = Database()
        self._configure_points(template)

        config = OutstationConfig(
            address=outstation_address,
            master_address=master_address,
            unsolicited=UnsolicitedConfig(enabled=unsolicited_enabled),
            time_sync_required=False,
        )
        self.outstation = Outstation(config=config, database=self.database)
        logger.info(
            "DNP3 outstation initialized (address=%s, master=%s)",
            outstation_address,
            master_address,
        )

    def _configure_points(self, template):
        for point in template.get("binary_inputs", []) or []:
            index = int(point["index"])
            value = bool(point.get("value", False))
            self.database.add_binary_input(
                index,
                BinaryInputConfig(event_class=EventClass.NONE),
                value=value,
                quality=BinaryQuality.ONLINE,
            )
            logger.debug("Added binary input %s value=%s", index, value)

        for point in template.get("analog_inputs", []) or []:
            index = int(point["index"])
            value = float(point.get("value", 0.0))
            self.database.add_analog_input(
                index,
                AnalogInputConfig(event_class=EventClass.NONE),
                value=value,
                quality=AnalogQuality.ONLINE,
            )
            logger.debug("Added analog input %s value=%s", index, value)

        if not template.get("binary_inputs") and not template.get("analog_inputs"):
            self.database.add_binary_input(
                0,
                BinaryInputConfig(event_class=EventClass.NONE),
                value=False,
                quality=BinaryQuality.ONLINE,
            )
            self.database.add_analog_input(
                0,
                AnalogInputConfig(event_class=EventClass.NONE),
                value=0.0,
                quality=AnalogQuality.ONLINE,
            )

    async def handle(self, reader, writer):
        peer = writer.get_extra_info("peername") or ("unknown", 0)
        sockname = writer.get_extra_info("sockname") or (self.host, self.port)

        session = conpot_core.get_session(
            "dnp3",
            peer[0],
            peer[1],
            sockname[0],
            sockname[1],
        )
        logger.info(
            "New DNP3 connection from %s:%s. (%s)", peer[0], peer[1], session.id
        )
        session.log_event(event_type="NEW_CONNECTION")

        channel = StreamChannel(reader, writer, read_timeout=self.timeout)
        try:
            await run_outstation_session(
                outstation=self.outstation,
                channel=channel,
                session=session,
                stop_event=getattr(self, "_stop", None),
            )
        except Exception as exc:
            if _is_peer_disconnect(exc):
                logger.info("DNP3 peer reset. (%s)", session.id)
            else:
                logger.exception("DNP3 session error (%s)", session.id)
        finally:
            logger.info("DNP3 client disconnected. (%s)", session.id)
            session.log_event(event_type="CONNECTION_LOST")

    async def start(self, host, port):
        self.host = host
        self.port = port
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        await serve_tcp_async_handler(
            host,
            port,
            self,
            stop_event=self._stop,
            ready_event=self._ready,
            name="DNP3Server",
        )

    def stop(self):
        if hasattr(self, "_stop"):
            self._stop.set()
