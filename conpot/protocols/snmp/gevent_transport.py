# Gevent UDP transport + dispatcher for PySNMP 7.x (asyncio is default; conpot uses gevent).
import socket

from pysnmp.carrier.asyncio.dgram.udp import UdpTransportAddress
from pysnmp.carrier.base import AbstractTransport, AbstractTransportDispatcher


class GeventDispatcher(AbstractTransportDispatcher):
    """Drive PySNMP with a blocking gevent-cooperative UDP recv loop."""

    def __init__(self):
        super().__init__()
        self.socket = None
        self._running = False
        self._udp_transport = None

    def register_transport(self, tDomain, transport):
        super().register_transport(tDomain, transport)
        self._udp_transport = transport
        self.socket = transport.sock

    def register_timer_callback(self, timerCbFun, tickInterval=None):
        # Match legacy conpot/pysnmp4 behavior: timers were not wired to the gevent loop.
        pass

    def unregister_timer_callback(self, timerCbFun=None):
        pass

    def run_dispatcher(self, timeout=0.0):
        self._running = True
        sock = self._udp_transport.sock
        while self._running:
            try:
                msg, addr = sock.recvfrom(65507)
            except OSError:
                break
            self._callback_function(self._udp_transport, UdpTransportAddress(addr), msg)

    def close_dispatcher(self):
        self._running = False
        super().close_dispatcher()

    def serve_forever(self):
        self.run_dispatcher()

    def stop(self):
        self._running = False
        if self.socket:
            try:
                self.socket.close()
            except OSError:
                pass


class ClientGeventDispatcher(GeventDispatcher):
    """Like GeventDispatcher but stops when the SNMP engine has no pending jobs (client I/O)."""

    def run_dispatcher(self, timeout=0.0):
        self._running = True
        sock = self._udp_transport.sock
        # SNMPv3 may need multiple round-trips (e.g. discovery + command); drain until idle.
        for _ in range(32):
            if not self._running:
                break
            try:
                msg, addr = sock.recvfrom(65507)
            except OSError:
                break
            self._callback_function(self._udp_transport, UdpTransportAddress(addr), msg)
            if not self.jobs_are_pending():
                break


class GeventUdpTransport(AbstractTransport):
    """UDP transport using an already-bound gevent socket."""

    PROTO_TRANSPORT_DISPATCHER = GeventDispatcher
    ADDRESS_TYPE = UdpTransportAddress

    def __init__(self, sock: socket.socket):
        super().__init__()
        self.sock = sock

    def open_server_mode(self, iface=None, sock=None):
        return self

    def send_message(self, outgoingMessage, transportAddress):
        if isinstance(transportAddress, UdpTransportAddress):
            addr = tuple(transportAddress[:2])
        else:
            addr = tuple(transportAddress[:2])
        self.sock.sendto(outgoingMessage, addr)

    def close_transport(self):
        try:
            self.sock.close()
        except OSError:
            pass
        super().close_transport()


class GeventClientUdpTransport(GeventUdpTransport):
    """UDP client transport: dispatcher exits after one request/response cycle."""

    PROTO_TRANSPORT_DISPATCHER = ClientGeventDispatcher
