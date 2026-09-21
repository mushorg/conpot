# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# OPC UA TCP framing + UaProcessor session loop. Framing follows asyncua 2.0.1
# OPCUAProtocol but keeps Conpot's multi-connection accept model and
# attack-session logging. Does not use BinaryServer.

from __future__ import annotations

import asyncio
import logging
from typing import Any

from asyncua import ua
from asyncua.common.connection import TransportLimits
from asyncua.common.utils import Buffer, NotEnoughData
from asyncua.server.internal_server import InternalServer
from asyncua.server.uaprocessor import UaProcessor
from asyncua.ua.ua_binary import header_from_binary, nodeid_from_binary

logger = logging.getLogger(__name__)

_PEER_DISCONNECT = (
    ConnectionResetError,
    ConnectionAbortedError,
    BrokenPipeError,
    asyncio.IncompleteReadError,
)

# ObjectIds for DefaultBinary request encodings → short service names.
_SERVICE_NAMES = {
    ua.ObjectIds.FindServersRequest_Encoding_DefaultBinary: "FindServers",
    ua.ObjectIds.GetEndpointsRequest_Encoding_DefaultBinary: "GetEndpoints",
    ua.ObjectIds.CreateSessionRequest_Encoding_DefaultBinary: "CreateSession",
    ua.ObjectIds.ActivateSessionRequest_Encoding_DefaultBinary: "ActivateSession",
    ua.ObjectIds.CloseSessionRequest_Encoding_DefaultBinary: "CloseSession",
    ua.ObjectIds.BrowseRequest_Encoding_DefaultBinary: "Browse",
    ua.ObjectIds.BrowseNextRequest_Encoding_DefaultBinary: "BrowseNext",
    ua.ObjectIds.ReadRequest_Encoding_DefaultBinary: "Read",
    ua.ObjectIds.WriteRequest_Encoding_DefaultBinary: "Write",
    ua.ObjectIds.CreateSubscriptionRequest_Encoding_DefaultBinary: "CreateSubscription",
    ua.ObjectIds.DeleteSubscriptionsRequest_Encoding_DefaultBinary: "DeleteSubscriptions",
    ua.ObjectIds.PublishRequest_Encoding_DefaultBinary: "Publish",
    ua.ObjectIds.CreateMonitoredItemsRequest_Encoding_DefaultBinary: "CreateMonitoredItems",
    ua.ObjectIds.DeleteMonitoredItemsRequest_Encoding_DefaultBinary: "DeleteMonitoredItems",
    ua.ObjectIds.CallRequest_Encoding_DefaultBinary: "Call",
    ua.ObjectIds.RegisterNodesRequest_Encoding_DefaultBinary: "RegisterNodes",
    ua.ObjectIds.UnregisterNodesRequest_Encoding_DefaultBinary: "UnregisterNodes",
}


def _is_peer_disconnect(exc: BaseException) -> bool:
    if isinstance(exc, _PEER_DISCONNECT):
        return True
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in (104, 32, 54):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return bool(exc.exceptions) and all(
            _is_peer_disconnect(inner) for inner in exc.exceptions
        )
    return False


class WriterTransport:
    """Duck-typed asyncio transport for UaProcessor over StreamWriter."""

    def __init__(self, writer: asyncio.StreamWriter):
        self._writer = writer

    def write(self, data: bytes) -> None:
        self._writer.write(data)

    def close(self) -> None:
        try:
            self._writer.close()
        except Exception:
            pass

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        return self._writer.get_extra_info(name, default)

    def is_closing(self) -> bool:
        return self._writer.is_closing()


class LoggingUaProcessor(UaProcessor):
    """UaProcessor that records service names on the Conpot attack session."""

    def __init__(
        self,
        internal_server: InternalServer,
        transport,
        limits: TransportLimits,
        session,
    ):
        super().__init__(internal_server, transport, limits)
        self._conpot_session = session

    async def process(self, header, body):
        if header.MessageType == ua.MessageType.Hello:
            self._conpot_session.log_event(event_type="REQUEST", request="Hello")
        elif header.MessageType == ua.MessageType.SecureOpen:
            self._conpot_session.log_event(
                event_type="REQUEST", request="OpenSecureChannel"
            )
        elif header.MessageType == ua.MessageType.SecureClose:
            self._conpot_session.log_event(
                event_type="REQUEST", request="CloseSecureChannel"
            )
        return await super().process(header, body)

    async def process_message(self, seqhdr, body):
        peek = body.copy()
        try:
            typeid = nodeid_from_binary(peek)
            service = _SERVICE_NAMES.get(typeid.Identifier, f"Service:{typeid}")
            self._conpot_session.log_event(event_type="REQUEST", request=service)
        except Exception:
            logger.debug("Could not peek OPC UA service typeid", exc_info=True)
        return await super().process_message(seqhdr, body)


async def run_opcua_session(
    *,
    iserver: InternalServer,
    policies: list,
    limits: TransportLimits,
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    session,
    read_timeout: float,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Read UA TCP frames and feed UaProcessor until disconnect or timeout."""
    transport = WriterTransport(writer)
    processor = LoggingUaProcessor(iserver, transport, limits, session)
    processor.set_policies(policies)
    buffer = b""

    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            try:
                chunk = await asyncio.wait_for(reader.read(65535), timeout=read_timeout)
            except asyncio.TimeoutError:
                logger.info("OPC UA idle timeout. (%s)", session.id)
                break
            except Exception as exc:
                if _is_peer_disconnect(exc):
                    break
                raise
            if not chunk:
                break

            buffer += chunk
            while buffer:
                try:
                    view = Buffer(buffer)
                    header = header_from_binary(view)
                except NotEnoughData:
                    break
                if header.header_size + header.body_size <= header.header_size:
                    logger.warning(
                        "Malformed OPC UA header from client (%s)", session.id
                    )
                    return
                needed = header.header_size + header.body_size
                if len(buffer) < needed:
                    break
                body = Buffer(buffer, header.header_size, header.body_size)
                try:
                    keep_going = await processor.process(header, body)
                except Exception as exc:
                    if _is_peer_disconnect(exc):
                        return
                    logger.exception("OPC UA processor error (%s)", session.id)
                    return
                buffer = buffer[needed:]
                if not keep_going:
                    return
                try:
                    await writer.drain()
                except Exception as exc:
                    if _is_peer_disconnect(exc):
                        return
                    raise
    finally:
        try:
            await processor.close()
        except Exception:
            logger.debug("OPC UA processor close failed", exc_info=True)
