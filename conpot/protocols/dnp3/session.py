# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# Async DNP3 link/transport session loop. Framing follows dnp3py 0.4.0
# OutstationTcpRunner._handle_connection but keeps Conpot's multi-connection
# accept model and attack-session logging.

from __future__ import annotations

import asyncio
import logging

from dnp3.application.header import ApplicationControl
from dnp3.core.enums import FunctionCode, LinkFunctionCode
from dnp3.datalink.builder import (
    build_ack,
    build_link_status,
    build_unconfirmed_user_data,
)
from dnp3.datalink.parser import FrameParser
from dnp3.outstation.outstation import Outstation
from dnp3.transport.reassembler import Reassembler
from dnp3.transport.segment import TransportSegment
from dnp3.transport.segmenter import Segmenter

logger = logging.getLogger(__name__)

# Scanners (nmap -sV) RST idle sockets. Python 3.14 can raise that from
# wait_closed() / read() as ConnectionResetError or an ExceptionGroup.
_PEER_DISCONNECT = (
    ConnectionResetError,
    ConnectionAbortedError,
    BrokenPipeError,
    asyncio.IncompleteReadError,
)


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


class StreamChannel:
    """Asyncio StreamReader/Writer adapter matching dnp3py channel shape."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        read_timeout: float,
    ):
        self._reader = reader
        self._writer = writer
        self._read_timeout = read_timeout

    async def read(self, n: int = 4096) -> bytes:
        try:
            return await asyncio.wait_for(
                self._reader.read(n), timeout=self._read_timeout
            )
        except Exception as exc:
            if _is_peer_disconnect(exc):
                return b""
            raise

    async def write_all(self, data: bytes) -> None:
        try:
            self._writer.write(data)
            await self._writer.drain()
        except Exception as exc:
            if _is_peer_disconnect(exc):
                return
            raise

    async def close(self) -> None:
        try:
            self._writer.close()
        except Exception:
            pass
        # Skip wait_closed(): nmap RSTs surface there as ConnectionResetError
        # on the transport callback and can escape a local try/except.


def _function_code_name(app_data: bytes) -> str:
    if len(app_data) < 2:
        return "UNKNOWN"
    try:
        return FunctionCode(app_data[1]).name
    except ValueError:
        return f"FC_{app_data[1]}"


def _object_groups(app_data: bytes) -> list[int]:
    """Best-effort object group list from a request fragment body."""
    groups = []
    offset = 2
    while offset + 3 <= len(app_data):
        group = app_data[offset]
        groups.append(group)
        # Skip header (group, variation, qualifier); ignore range/data bytes.
        # Enough for honeypot logging of typical class/static polls.
        offset += 3
        if offset >= len(app_data):
            break
        # Qualifier-driven lengths vary; stop after a few headers to stay safe.
        if len(groups) >= 16:
            break
        # For integrity polls (qualifier 0x06) there is no range; next header
        # starts immediately. Heuristic: if remaining looks like another
        # group header, continue; else stop.
        if offset + 3 > len(app_data):
            break
    return groups


async def run_outstation_session(
    *,
    outstation: Outstation,
    channel: StreamChannel,
    session,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Drive one client connection through the DNP3 stack.

    Args:
        outstation: Shared dnp3py Outstation (point database + app logic).
        channel: Stream adapter for this TCP client.
        session: Conpot AttackSession for event logging.
        stop_event: Optional server-wide stop signal.
    """
    parser = FrameParser()
    reassembler = Reassembler(max_fragment_size=outstation.config.max_fragment_size)
    segmenter = Segmenter()
    outstation_addr = outstation.config.address
    master_addr = outstation.config.master_address
    learned_master_addr = 0

    try:
        while stop_event is None or not stop_event.is_set():
            try:
                data = await channel.read(4096)
            except asyncio.TimeoutError:
                logger.info("DNP3 session read timeout. (%s)", session.id)
                break
            if not data:
                break

            try:
                frames = list(parser.feed(data))
            except Exception:
                logger.debug(
                    "DNP3 ignored malformed input (%s)", session.id, exc_info=True
                )
                session.log_event(event_type="MALFORMED", request=data[:64].hex())
                continue

            for frame in frames:
                if frame.header.destination != outstation_addr:
                    continue

                if learned_master_addr == 0:
                    learned_master_addr = frame.header.source

                effective_master = (
                    master_addr if master_addr != 0 else learned_master_addr
                )

                if not frame.header.control.prm:
                    continue

                fc = frame.header.control.function_code

                if fc == LinkFunctionCode.PRI_RESET_LINK_STATE:
                    ack = build_ack(effective_master, outstation_addr, False)
                    await channel.write_all(ack.to_bytes())
                    session.log_event(
                        event_type="LINK",
                        request="RESET_LINK_STATE",
                        response="ACK",
                    )
                    continue

                if fc == LinkFunctionCode.PRI_REQUEST_LINK_STATUS:
                    status = build_link_status(effective_master, outstation_addr, False)
                    await channel.write_all(status.to_bytes())
                    session.log_event(
                        event_type="LINK",
                        request="REQUEST_LINK_STATUS",
                        response="LINK_STATUS",
                    )
                    continue

                if fc == LinkFunctionCode.PRI_TEST_LINK_STATE:
                    ack = build_ack(effective_master, outstation_addr, False)
                    await channel.write_all(ack.to_bytes())
                    session.log_event(
                        event_type="LINK",
                        request="TEST_LINK_STATE",
                        response="ACK",
                    )
                    continue

                if fc == LinkFunctionCode.PRI_CONFIRMED_USER_DATA:
                    ack = build_ack(effective_master, outstation_addr, False)
                    await channel.write_all(ack.to_bytes())
                elif fc == LinkFunctionCode.PRI_UNCONFIRMED_USER_DATA:
                    pass
                else:
                    continue

                if not frame.user_data:
                    continue

                segment = TransportSegment.from_bytes(frame.user_data)
                result = reassembler.add(segment)
                if result is None:
                    continue

                app_data = result.data
                fc_name = _function_code_name(app_data)
                groups = _object_groups(app_data)
                session.log_event(
                    event_type="REQUEST",
                    request=fc_name,
                    object_groups=groups,
                    request_raw=app_data.hex(),
                )

                responses = outstation.process_request(app_data)
                is_multi = len(responses) > 1

                for i, response in enumerate(responses):
                    is_last_fragment = i == len(responses) - 1
                    if is_multi and not is_last_fragment:
                        resp_bytes = bytearray(response.to_bytes())
                        resp_bytes[0] |= 0x20
                        resp_bytes = bytes(resp_bytes)
                    else:
                        resp_bytes = response.to_bytes()

                    for seg in segmenter.segment(resp_bytes):
                        resp_frame = build_unconfirmed_user_data(
                            destination=effective_master,
                            source=outstation_addr,
                            dir_from_master=False,
                            user_data=seg.to_bytes(),
                        )
                        await channel.write_all(resp_frame.to_bytes())

                    if is_multi and not is_last_fragment:
                        confirm_received = await _wait_for_confirm(
                            channel,
                            parser,
                            outstation,
                            outstation_addr,
                            effective_master,
                            expected_seq=response.sequence,
                            timeout=outstation.config.confirm_timeout,
                        )
                        if not confirm_received:
                            logger.warning(
                                "Timed out waiting for application confirm "
                                "after fragment %d of %d (%s)",
                                i + 1,
                                len(responses),
                                session.id,
                            )
                            break

                session.log_event(
                    event_type="RESPONSE",
                    request=fc_name,
                    response_fragments=len(responses),
                )
    finally:
        try:
            await channel.close()
        except Exception:
            pass


async def _wait_for_confirm(
    channel: StreamChannel,
    parser: FrameParser,
    outstation: Outstation,
    outstation_addr: int,
    master_addr: int,
    *,
    expected_seq: int,
    timeout: float = 5.0,
) -> bool:
    confirm_reassembler = Reassembler(
        max_fragment_size=outstation.config.max_fragment_size
    )
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout

    while loop.time() < deadline:
        remaining = deadline - loop.time()
        if remaining <= 0:
            return False
        try:
            data = await asyncio.wait_for(channel.read(4096), timeout=remaining)
        except asyncio.TimeoutError:
            return False
        if not data:
            return False

        for frame in parser.feed(data):
            if frame.header.destination != outstation_addr:
                continue
            if not frame.header.control.prm:
                continue

            fc = frame.header.control.function_code
            if fc == LinkFunctionCode.PRI_RESET_LINK_STATE:
                await channel.write_all(
                    build_ack(master_addr, outstation_addr, False).to_bytes()
                )
                continue
            if fc == LinkFunctionCode.PRI_REQUEST_LINK_STATUS:
                await channel.write_all(
                    build_link_status(master_addr, outstation_addr, False).to_bytes()
                )
                continue
            if fc == LinkFunctionCode.PRI_TEST_LINK_STATE:
                await channel.write_all(
                    build_ack(master_addr, outstation_addr, False).to_bytes()
                )
                continue
            if fc == LinkFunctionCode.PRI_CONFIRMED_USER_DATA:
                await channel.write_all(
                    build_ack(master_addr, outstation_addr, False).to_bytes()
                )
            elif fc != LinkFunctionCode.PRI_UNCONFIRMED_USER_DATA:
                continue

            if not frame.user_data:
                continue

            segment = TransportSegment.from_bytes(frame.user_data)
            result = confirm_reassembler.add(segment)
            if result is not None and len(result.data) >= 2:
                if result.data[1] == 0x00:
                    confirm_seq = ApplicationControl.from_byte(result.data[0]).seq
                    if confirm_seq == expected_seq:
                        return True
                    logger.warning(
                        "Discarding CONFIRM with sequence %d, expected %d",
                        confirm_seq,
                        expected_seq,
                    )
    return False
