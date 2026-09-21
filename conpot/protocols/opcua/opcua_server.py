# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""OPC UA honeypot protocol (IEC 62541 via asyncua, Conpot-owned TCP)."""

from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from types import SimpleNamespace

from asyncua import Server, ua

import conpot.core as conpot_core
from conpot.core.protocol_wrapper import conpot_protocol
from conpot.protocols.opcua.session import run_opcua_session
from conpot.utils.asyncio_serve import _set_listener_addrs

logger = logging.getLogger(__name__)


@contextmanager
def _quiet_nodeset_load():
    """Mute asyncua's per-node INFO chatter while the standard nodeset loads.

    The bundled nodeset references parents that are not present yet, which
    logs ~1100 lines per start. Node management at runtime stays at INFO.
    """
    aspace_logger = logging.getLogger("asyncua.server.address_space")
    previous = aspace_logger.level
    aspace_logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        aspace_logger.setLevel(previous)


@conpot_protocol
class OPCUAServer(object):
    """OPC UA / opc.tcp honeypot.

    Conpot owns accept / session / timeouts. asyncua InternalServer +
    UaProcessor own application PDUs and the address space. BinaryServer is
    not used so scanners share Conpot's multi-connection accept model.
    """

    def __init__(self, template, template_directory, args):
        self.timeout = float(template.get("timeout", 5))
        self.host = None
        self.port = None
        self.server = None
        self.template = template
        self.databus = conpot_core.get_databus()

        self.endpoint_path = str(template.get("endpoint_path", "/conpot/server/"))
        if not self.endpoint_path.startswith("/"):
            self.endpoint_path = "/" + self.endpoint_path
        self.server_name = str(template.get("server_name", "Conpot OPC UA Server"))
        self.namespace_uri = str(
            template.get("namespace_uri", "http://conpot.org/OPCUA/")
        )
        self.application_uri = str(template.get("application_uri", "urn:conpot:opcua"))
        self._variables = list(template.get("variables", []) or [])

        self._ua: Server | None = None
        self._ua_started = False
        # Startup waits on _ready right after scheduling start(), so the Events
        # must exist before then and must not be replaced in start().
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        logger.info(
            "OPC UA server configured (name=%s, path=%s)",
            self.server_name,
            self.endpoint_path,
        )

    def _coerce_value(self, entry: dict):
        kind = str(entry.get("type", "float"))
        if kind == "boolean":
            return bool(entry.get("value", False))
        if kind == "integer":
            return int(entry.get("value", 0))
        if kind == "string":
            return str(entry.get("value", ""))
        return float(entry.get("value", 0.0))

    async def _init_address_space(self) -> None:
        assert self._ua is not None
        self._ua.set_server_name(self.server_name)
        await self._ua.set_application_uri(self.application_uri)
        self._ua.set_security_policy([ua.SecurityPolicyType.NoSecurity])

        idx = await self._ua.register_namespace(self.namespace_uri)
        folder = await self._ua.nodes.objects.add_object(idx, "Plant")
        if not self._variables:
            var = await folder.add_variable(idx, "Temperature", 25.0)
            await var.set_writable()
            logger.debug("Seeded default OPC UA variable Temperature=25.0")
            return

        for entry in self._variables:
            name = str(entry["name"])
            value = self._coerce_value(entry)
            var = await folder.add_variable(idx, name, value)
            await var.set_writable()
            logger.debug("Added OPC UA variable %s=%r", name, value)

    async def _bootstrap_ua(self, host: str, port: int) -> None:
        """Init address space + endpoints for the bound host:port (no listen)."""
        with _quiet_nodeset_load():
            self._ua = Server()
            await self._ua.init()
        endpoint = f"opc.tcp://{host}:{port}{self.endpoint_path}"
        self._ua.set_endpoint(endpoint)
        await self._init_address_space()
        await self._ua._setup_server_nodes()
        await self._ua.iserver.start()
        self._ua_started = True
        logger.info("OPC UA address space ready at %s", endpoint)

    async def _shutdown_ua(self) -> None:
        # Bound shutdown so Conpot stop()/test join(0.2) stays responsive;
        # asyncua InternalServer.stop can otherwise take ~1s.
        ua_server = self._ua
        self._ua = None
        started = self._ua_started
        self._ua_started = False
        if ua_server is None or not started:
            return
        try:
            await asyncio.wait_for(ua_server.iserver.stop(), timeout=0.05)
        except asyncio.TimeoutError:
            logger.debug("OPC UA InternalServer stop timed out")
        except Exception:
            logger.exception("Error stopping OPC UA InternalServer")

    async def handle(self, reader, writer):
        peer = writer.get_extra_info("peername") or ("unknown", 0)
        sockname = writer.get_extra_info("sockname") or (self.host, self.port)

        session = conpot_core.get_session(
            "opcua",
            peer[0],
            peer[1],
            sockname[0],
            sockname[1],
        )
        logger.info(
            "New OPC UA connection from %s:%s. (%s)",
            peer[0],
            peer[1],
            session.id,
        )
        session.log_event(event_type="NEW_CONNECTION")

        try:
            if self._ua is None or not self._ua_started:
                logger.warning(
                    "OPC UA stack not ready; closing connection (%s)",
                    session.id,
                )
                return
            await run_opcua_session(
                iserver=self._ua.iserver,
                policies=self._ua._policies,
                limits=self._ua.limits,
                reader=reader,
                writer=writer,
                session=session,
                read_timeout=self.timeout,
                stop_event=self._stop,
            )
        except Exception as exc:
            from conpot.protocols.opcua.session import _is_peer_disconnect

            if _is_peer_disconnect(exc):
                logger.info("OPC UA peer reset. (%s)", session.id)
            else:
                logger.exception("OPC UA session error (%s)", session.id)
        finally:
            logger.info("OPC UA client disconnected. (%s)", session.id)
            session.log_event(event_type="CONNECTION_LOST")

    async def start(self, host, port):
        """Bind TCP, bootstrap asyncua for the real port, then accept clients.

        Endpoint URLs are built after bind so ephemeral ``port=0`` (tests)
        still advertises a correct GetEndpoints URL.
        """
        self.host = host
        self.port = port
        self._stop.clear()
        self._ready.clear()

        client_tasks: set[asyncio.Task] = set()

        async def _on_client(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            task = asyncio.current_task()
            if task is not None:
                client_tasks.add(task)
            peer = writer.get_extra_info("peername")
            try:
                await self.handle(reader, writer)
            except Exception:
                logger.exception("OPCUAServer connection handler crashed for %s", peer)
            finally:
                if task is not None:
                    client_tasks.discard(task)
                try:
                    writer.close()
                except Exception:
                    pass
                try:
                    await writer.wait_closed()
                except Exception, BaseExceptionGroup:
                    pass

        listener = await asyncio.start_server(
            _on_client, host=host, port=port, reuse_address=True
        )
        bound_host, bound_port = listener.sockets[0].getsockname()[:2]
        _set_listener_addrs(self, bound_host, bound_port)
        # Keep a SimpleNamespace for tests that expect .server.server_port
        if self.server is None:
            self.server = SimpleNamespace(
                server_host=bound_host, server_port=bound_port
            )

        try:
            await self._bootstrap_ua(bound_host, bound_port)
            logger.info("OPCUAServer listening on %s:%s", bound_host, bound_port)
            self._ready.set()
            await self._stop.wait()
        finally:
            listener.close()
            await listener.wait_closed()
            for task in list(client_tasks):
                task.cancel()
            if client_tasks:
                await asyncio.gather(*client_tasks, return_exceptions=True)
            await self._shutdown_ua()

    def stop(self):
        self._stop.set()
