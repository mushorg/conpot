# Copyright (C) 2014  Johnny Vestergaard <jkv@unixcluster.dk>
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

import abc
import asyncio
import codecs
import logging
import select
import socket
import ssl
import time

import conpot.core as conpot_core
from conpot.utils.asyncio_serve import serve_tcp_sync_handler

logger = logging.getLogger(__name__)

# Bounds every blocking socket operation: client TLS handshake, backend
# connect/handshake, and reads/writes on an already-readable socket.
DEFAULT_TIMEOUT = 5
# Close a proxied connection when neither side has sent data for this long.
DEFAULT_IDLE_TIMEOUT = 300
RECV_SIZE = 4096


class ProxyDecoder(abc.ABC):
    @abc.abstractmethod
    def decode_in(self, data):
        """Decode data that goes into the proxied device"""

    @abc.abstractmethod
    def decode_out(self, data):
        """Decode data that goes out from the proxied device to the connected client(attacker)."""


class Proxy(object):
    def __init__(
        self,
        name,
        proxy_host,
        proxy_port,
        decoder=None,
        keyfile=None,
        certfile=None,
        timeout=DEFAULT_TIMEOUT,
        idle_timeout=DEFAULT_IDLE_TIMEOUT,
    ):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.name = name
        self.proxy_id = self.name.lower().replace(" ", "_")
        self.host = None
        self.port = None
        self.server = None
        self.keyfile = keyfile
        self.certfile = certfile
        self.timeout = timeout
        self.idle_timeout = idle_timeout
        # Build TLS contexts once so a bad cert/key path fails at startup
        # instead of looking like a per-client handshake failure.
        self._server_ctx = None
        self._client_ctx = None
        if self.keyfile and self.certfile:
            self._server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self._server_ctx.load_cert_chain(
                certfile=self.certfile, keyfile=self.keyfile
            )
            self._client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self._client_ctx.check_hostname = False
            self._client_ctx.verify_mode = ssl.CERT_NONE
            self._client_ctx.load_cert_chain(
                certfile=self.certfile, keyfile=self.keyfile
            )
        if decoder:
            try:
                namespace, _classname = decoder.rsplit(".", 1)
                module = __import__(namespace, fromlist=[_classname])
                _class = getattr(module, _classname)
                self.decoder = _class()
                assert isinstance(self.decoder, ProxyDecoder)
            except AssertionError:
                logger.fatal(
                    "Invalid decoder: decoder must be an instance of ProxyDecoder."
                )
        else:
            self.decoder = None

    async def start(self, host, port):
        self.host = host
        self.port = port
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        logger.info(
            "%s proxy server started, listening on %s, proxy for: (%s, %s) using %s decoder.",
            self.name,
            (host, port),
            self.proxy_host,
            self.proxy_port,
            self.decoder,
        )
        # Incoming TLS is wrapped in handle() (same as StreamServer keyfile/certfile),
        # not via asyncio.start_server(ssl=...), so the sync handler owns the fd.
        await serve_tcp_sync_handler(
            host,
            port,
            self,
            stop_event=self._stop,
            ready_event=self._ready,
            name=self.name or "Proxy",
        )

    def handle(self, sock, address):
        # asyncio start_server hands over a non-blocking fd; SSL wrap and
        # blocking recv/select in this worker thread need a blocking socket.
        sock.setblocking(True)
        sock.settimeout(self.timeout)
        local_host, local_port = sock.getsockname()[:2]
        session = conpot_core.get_session(
            self.proxy_id, address[0], address[1], local_host, local_port
        )
        logger.info(
            "New connection from %s:%s on %s proxy. (%s)",
            address[0],
            address[1],
            self.proxy_id,
            session.id,
        )
        session.log_event(event_type="NEW_CONNECTION")
        proxy_socket = None
        try:
            if self._server_ctx is not None:
                try:
                    sock = self._server_ctx.wrap_socket(sock, server_side=True)
                except OSError as err:
                    # ssl.SSLError and socket.timeout are both OSError.
                    logger.info(
                        "TLS handshake with %s:%s on %s proxy failed: %s (%s)",
                        address[0],
                        address[1],
                        self.proxy_id,
                        err,
                        session.id,
                    )
                    session.log_event(event_type="TLS_HANDSHAKE_FAILED", error=str(err))
                    return

            try:
                proxy_socket = self._connect_backend()
            except OSError as err:
                logger.warning(
                    "Error while connecting to proxied service at (%s, %s): %s",
                    self.proxy_host,
                    self.proxy_port,
                    err,
                )
                session.log_event(event_type="CONNECTION_FAILED", error=str(err))
                return

            self._relay(sock, proxy_socket, address, session)
        finally:
            logger.info(
                "Connection from %s:%s on %s proxy closed. (%s)",
                address[0],
                address[1],
                self.proxy_id,
                session.id,
            )
            session.log_event(event_type="CONNECTION_LOST")
            session.set_ended()
            self._close([proxy_socket, sock])

    def _connect_backend(self):
        backend = socket.create_connection(
            (self.proxy_host, self.proxy_port), timeout=self.timeout
        )
        if self._client_ctx is not None:
            try:
                backend = self._client_ctx.wrap_socket(backend)
            except OSError:
                backend.close()
                raise
        return backend

    def _recv(self, sock):
        """Read what select() reported as readable.

        Returns the data, ``b""`` when the peer closed, or ``None`` when a TLS
        socket was readable but carried no application data (e.g. a TLS 1.3
        session ticket). A blocking read in that case would stall the relay
        while the other direction still has data to forward.
        """
        if not isinstance(sock, ssl.SSLSocket):
            return sock.recv(RECV_SIZE)
        sock.settimeout(0)
        try:
            try:
                data = sock.recv(RECV_SIZE)
            except ssl.SSLWantReadError:
                return None
            # A TLS record can decrypt to more than one recv() worth of data;
            # the rest sits in the SSL object where select() cannot see it.
            pending = sock.pending()
            while data and pending:
                data += sock.recv(pending)
                pending = sock.pending()
            return data
        finally:
            sock.settimeout(self.timeout)

    def _relay(self, sock, proxy_socket, address, session):
        sockets = [proxy_socket, sock]
        last_activity = time.monotonic()
        while True:
            remaining = self.idle_timeout - (time.monotonic() - last_activity)
            if remaining <= 0:
                logger.info(
                    "Closing idle connection from %s:%s on %s proxy after %ss.",
                    address[0],
                    address[1],
                    self.proxy_id,
                    self.idle_timeout,
                )
                return
            sockets_read, _, sockets_err = select.select(
                sockets, [], sockets, remaining
            )
            if sockets_err:
                return

            for s in sockets_read:
                if s is proxy_socket:
                    peer = "proxied service (%s, %s)" % (
                        self.proxy_host,
                        self.proxy_port,
                    )
                else:
                    peer = "remote (%s, %s)" % (address[0], address[1])
                try:
                    data = self._recv(s)
                except OSError as socket_err:
                    logger.warning(
                        "Error while receiving from %s: %s.", peer, socket_err
                    )
                    return
                if data is None:
                    continue
                if not data:
                    logger.info("Connection closed by %s.", peer)
                    return

                last_activity = time.monotonic()
                try:
                    if s is proxy_socket:
                        self.handle_out_data(data, sock, session)
                    else:
                        self.handle_in_data(data, proxy_socket, session)
                except OSError as socket_err:
                    logger.warning(
                        "Error while forwarding data from %s: %s.", peer, socket_err
                    )
                    return

    def handle_in_data(self, data, sock, session):
        # convert the data from bytes to hex string
        hex_data = codecs.encode(data, "hex_codec")
        session.log_event(raw_request=hex_data, raw_response="")
        logger.debug(
            "Received %s bytes from outside to proxied service: %s", len(data), hex_data
        )
        if self.decoder:
            # TODO: data could be chunked, proxy needs to handle this
            decoded = self.decoder.decode_in(data)
            logger.debug("Decoded request: %s", decoded)
            session.log_event(request=decoded)
        sock.sendall(data)

    def handle_out_data(self, data, sock, session):
        hex_data = codecs.encode(data, "hex_codec")
        session.log_event(raw_request="", raw_response=hex_data)
        logger.debug("Received %s bytes from proxied service: %s", len(data), hex_data)
        if self.decoder:
            # TODO: data could be chunked, proxy needs to handle this
            decoded = self.decoder.decode_out(data)
            logger.debug("Decoded response: %s", decoded)
            session.log_event(response=decoded)
        sock.sendall(data)

    def _close(self, sockets):
        for s in sockets:
            if s is None:
                continue
            try:
                s.close()
            except OSError:
                pass

    def stop(self):
        if hasattr(self, "_stop"):
            self._stop.set()
