# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# Shared asyncio TCP/UDP helpers for Conpot protocol servers.
# Sync handle(sock, addr) methods run in a thread-pool executor so existing
# protocol logic stays unchanged; the event loop only owns accept/listen.

from __future__ import annotations

import asyncio
import logging
import socket
from types import SimpleNamespace

logger = logging.getLogger(__name__)


def _set_listener_addrs(server_obj, host: str, port: int) -> None:
    """Expose legacy server_host/server_port on server_obj.server."""
    info = getattr(server_obj, "server", None)
    if info is None or not hasattr(info, "server_host"):
        info = SimpleNamespace(server_host=host, server_port=port)
        server_obj.server = info
    else:
        info.server_host = host
        info.server_port = port
    server_obj.server_host = host
    server_obj.server_port = port
    server_obj.host = host
    server_obj.port = port


async def serve_tcp_sync_handler(
    host: str,
    port: int,
    handler_obj,
    *,
    stop_event: asyncio.Event,
    ready_event: asyncio.Event | None = None,
    name: str = "TCPServer",
    ssl_context=None,
):
    """Accept TCP connections and run handler_obj.handle(sock, addr) in an executor.

    Client sockets are accepted via ``sock_accept`` and handed exclusively to the
    worker thread (no StreamReader/Writer). Sharing an asyncio transport socket
    with a sync ``recv``/``send`` loop races and resets connections under load.
    """
    if ssl_context is not None:
        raise NotImplementedError(
            "ssl_context is not supported with sock_accept handoff; "
            "use an asyncio TLS protocol server instead"
        )

    loop = asyncio.get_running_loop()

    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen_sock.bind((host, port))
    listen_sock.listen(100)
    listen_sock.setblocking(False)

    bound_host, bound_port = listen_sock.getsockname()[:2]
    _set_listener_addrs(handler_obj, bound_host, bound_port)
    logger.info("%s listening on %s:%s", name, bound_host, bound_port)
    if ready_event is not None:
        ready_event.set()

    client_tasks: set[asyncio.Task] = set()

    async def _run_handler(conn: socket.socket, peer) -> None:
        # Blocking recv/send/timeouts belong in the worker thread.
        conn.setblocking(True)
        try:
            await loop.run_in_executor(None, handler_obj.handle, conn, peer)
        except Exception:
            logger.exception("%s connection handler crashed for %s", name, peer)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    async def _accept_loop() -> None:
        while not stop_event.is_set():
            try:
                conn, peer = await asyncio.wait_for(
                    loop.sock_accept(listen_sock), timeout=0.5
                )
            except asyncio.TimeoutError:
                continue
            except OSError:
                if stop_event.is_set():
                    break
                raise
            task = asyncio.create_task(_run_handler(conn, peer), name=f"{name}-client")
            client_tasks.add(task)
            task.add_done_callback(client_tasks.discard)

    accept_task = asyncio.create_task(_accept_loop(), name=f"{name}-accept")
    try:
        await stop_event.wait()
    finally:
        # Closing the listener unblocks sock_accept immediately.
        try:
            listen_sock.close()
        except OSError:
            pass
        accept_task.cancel()
        try:
            await accept_task
        except asyncio.CancelledError:
            pass
        for task in list(client_tasks):
            task.cancel()
        if client_tasks:
            await asyncio.gather(*client_tasks, return_exceptions=True)


class _DatagramProtocol(asyncio.DatagramProtocol):
    def __init__(self, handler_obj, loop: asyncio.AbstractEventLoop):
        self.handler_obj = handler_obj
        self.loop = loop
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr):
        try:
            result = self.handler_obj.handle(data, addr)
            if asyncio.iscoroutine(result):
                self.loop.create_task(result)
        except Exception:
            logger.exception(
                "UDP handler crashed for %s (%s)",
                addr,
                type(self.handler_obj).__name__,
            )

    def error_received(self, exc):
        logger.debug("UDP error_received: %s", exc)

    def sendto(self, data: bytes, addr):
        if self.transport is not None:
            self.transport.sendto(data, addr)


async def serve_udp_datagram(
    host: str,
    port: int,
    handler_obj,
    *,
    stop_event: asyncio.Event,
    ready_event: asyncio.Event | None = None,
    name: str = "UDPServer",
    reuse_address: bool = False,
    broadcast: bool = False,
):
    """Bind a UDP endpoint and dispatch datagrams to handler_obj.handle(data, addr).

    Sets ``handler_obj.server`` to an object with ``sendto``, ``server_host``,
    ``server_port``, and ``socket`` (for SO_* tweaks already applied at bind).
    """
    loop = asyncio.get_running_loop()
    protocol = _DatagramProtocol(handler_obj, loop)

    # Exclusive bind for BACnet-style scanners (see bacnet_server comments).
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if reuse_address:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    else:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    if broadcast:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setblocking(False)
    sock.bind((host, port))

    transport, _proto = await loop.create_datagram_endpoint(lambda: protocol, sock=sock)
    bound_host, bound_port = sock.getsockname()[:2]

    class _ServerFacade:
        def __init__(self):
            self.server_host = bound_host
            self.server_port = bound_port
            self.socket = sock

        def sendto(self, data, addr):
            transport.sendto(data, addr)

    facade = _ServerFacade()
    handler_obj.server = facade
    handler_obj.server_host = bound_host
    handler_obj.server_port = bound_port
    handler_obj.host = bound_host
    handler_obj.port = bound_port

    logger.info("%s listening on %s:%s", name, bound_host, bound_port)
    if ready_event is not None:
        ready_event.set()

    try:
        await stop_event.wait()
    finally:
        transport.close()
