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

import logging
import socket
import cpppo
import contextlib
import time
import sys
import traceback

from lxml import etree
from cpppo.server import network
from cpppo.server.enip import logix
from cpppo.server.enip import parser

logger = logging.getLogger(__name__)


class EnipConfig(object):
    """
    Configurations parsed from template
    """

    def __init__(self, template):
        self.template = template
        self.parse_template()

    def parse_template(self):
        dom = etree.parse(self.template)
        self.server_addr    = dom.xpath('//enip/@host')[0]
        self.server_port    = int(dom.xpath('//enip/@port')[0])
        self.vendor_id      = int(dom.xpath('//enip/device_info/VendorId/text()')[0])
        self.device_type    = int(dom.xpath('//enip/device_info/DeviceType/text()')[0])
        self.product_rev    = int(dom.xpath('//enip/device_info/ProductRevision/text()')[0])
        self.product_code   = int(dom.xpath('//enip/device_info/ProductCode/text()')[0])
        self.product_name   = dom.xpath('//enip/device_info/ProductName/text()')[0]
        self.serial_number  = dom.xpath('//enip/device_info/SerialNumber/text()')[0]
        self.mode           = dom.xpath('//enip/mode/text()')[0]
        self.timeout        = float(dom.xpath('//enip/timeout/text()')[0])
        self.latency        = float(dom.xpath('//enip/latency/text()')[0])


class EnipServer(object):
    """
    ENIP server
    """

    def __init__(self, template, template_directory, args):
        self.config = EnipConfig(template)
        self.addr = self.config.server_addr
        self.port = self.config.server_port
        self.stopped = False
        self.connections = cpppo.dotdict()
        logger.debug('ENIP server serial number: ' + self.config.serial_number)
        logger.debug('ENIP server product name: ' + self.config.product_name)

    def stats_for(self, peer):
        if peer is None:
            return None, None
        connkey = "%s_%d" % (peer[0].replace('.', '_'), peer[1])
        stats = self.connections.get(connkey)
        if stats is not None:
            return stats, connkey
        stats = cpppo.apidict(timeout=self.config.timeout)
        self.connections[connkey] = stats
        stats['requests'] = 0
        stats['received'] = 0
        stats['eof'] = False
        stats['interface'] = peer[0]
        stats['port'] = peer[1]
        return stats, connkey

    def handle(self, conn, address, enip_process=None, delay=None, **kwds):
        """
        Handle an incoming connection
        """
        name = "ENIP_%s" % (address[1] if address else "UDP")
        logger.debug("ENIP server %s begins serving client %s", name, address)

        tcp = (conn.family == socket.AF_INET and conn.type == socket.SOCK_STREAM)
        udp = (conn.family == socket.AF_INET and conn.type == socket.SOCK_DGRAM)

        if tcp:
            try:
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception as e:
                logger.error("%s unable to set TCP_NODELAY for client %r: %s", name, address, e)
            try:
                conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            except Exception as e:
                logger.error("%s unable to set SO_KEEPALIVE for client %r: %s", name, address, e)
            self.handle_tcp(conn, address, name=name, enip_process=enip_process, delay=delay, **kwds)
        elif udp:
            self.handle_udp(conn, name=name, enip_process=enip_process, **kwds)
        else:
            raise NotImplemented("Unknown socket protocol for EtherNet/IP CIP")

    def handle_tcp(self, conn, address, name, enip_process, delay=None, **kwds):
        """
        Handle a TCP client
        """
        source = cpppo.rememberable()
        with parser.enip_machine(name=name, context='enip') as machine:
            try:
                assert address, "EtherNet/IP CIP server for TCP/IP must be provided a peer address"
                stats, connkey = self.stats_for(address)
                while not stats.eof:
                    data = cpppo.dotdict()
                    source.forget()
                    # If no/partial EtherNet/IP header received, parsing will fail with a NonTerminal
                    # Exception (dfa exits in non-terminal state).  Build data.request.enip:
                    begun = cpppo.timer()
                    with contextlib.closing(machine.run(path='request', source=source, data=data)) as engine:
                        # PyPy compatibility; avoid deferred destruction of generators
                        for mch, sta in engine:
                            if sta is not None:
                                continue
                            # No more transitions available.  Wait for input.  EOF (b'') will lead to
                            # termination.  We will simulate non-blocking by looping on None (so we can
                            # check our options, in case they've been changed).  If we still have input
                            # available to process right now in 'source', we'll just check (0 timeout);
                            # otherwise, use the specified server.control.latency.
                            msg = None
                            while msg is None and not stats.eof:
                                wait = (kwds['server']['control']['latency'] if source.peek() is None else 0)
                                brx = cpppo.timer()
                                msg = network.recv(conn, timeout=wait)
                                now = cpppo.timer()
                                (logger.info if msg else logger.debug)(
                                    "Transaction receive after %7.3fs (%5s bytes in %7.3f/%7.3fs)",
                                    now - begun,
                                    len(msg) if msg is not None else "None",
                                    now - brx, wait)

                                # After each block of input (or None), check if the server is being
                                # signalled done/disabled; we need to shut down so signal eof.  Assumes
                                # that (shared) server.control.{done,disable} dotdict be in kwds.  We do
                                # *not* read using attributes here, to avoid reporting completion to
                                # external APIs (eg. web) awaiting reception of these signals.
                                if kwds['server']['control']['done'] or  kwds['server']['control']['disable']:
                                    logger.info("%s done, due to server done/disable", machine.name_centered())
                                    stats['eof'] = True
                                if msg is not None:
                                    stats['received'] += len(msg)
                                    stats['eof'] = stats['eof'] or not len(msg)
                                    if logger.getEffectiveLevel() <= logging.INFO:
                                        logger.info("%s recv: %5d: %s", machine.name_centered(), len(msg), cpppo.reprlib.repr(msg))
                                    source.chain(msg)
                                else:
                                    # No input.  If we have symbols available, no problem; continue.
                                    # This can occur if the state machine cannot make a transition on
                                    # the input symbol, indicating an unacceptable sentence for the
                                    # grammar.  If it cannot make progress, the machine will terminate
                                    # in a non-terminal state, rejecting the sentence.
                                    if source.peek() is not None:
                                        break
                                        # We're at a None (can't proceed), and no input is available.  This
                                        # is where we implement "Blocking"; just loop.

                    logger.info("Transaction parsed  after %7.3fs", cpppo.timer() - begun)
                    # Terminal state and EtherNet/IP header recognized, or clean EOF (no partial
                    # message); process and return response
                    if 'request' in data:
                        stats['requests'] += 1
                    try:
                        # enip_process must be able to handle no request (empty data), indicating the
                        # clean termination of the session if closed from this end (not required if
                        # enip_process returned False, indicating the connection was terminated by
                        # request.)
                        delayseconds = 0  # response delay (if any)
                        if enip_process(address, data=data, **kwds):
                            # Produce an EtherNet/IP response carrying the encapsulated response data.
                            # If no encapsulated data, ensure we also return a non-zero EtherNet/IP
                            # status.  A non-zero status indicates the end of the session.
                            assert 'response.enip' in data, "Expected EtherNet/IP response; none found"
                            if 'input' not in data.response.enip or not data.response.enip.input:
                                logger.warning("Expected EtherNet/IP response encapsulated message; none found")
                                assert data.response.enip.status, "If no/empty response payload, expected non-zero EtherNet/IP status"

                            rpy = parser.enip_encode(data.response.enip)
                            if logger.getEffectiveLevel() <= logging.INFO:
                                logger.info("%s send: %5d: %s %s", machine.name_centered(), len(rpy),
                                            cpppo.reprlib.repr(rpy), ("delay: %r" % delay) if delay else "")
                            if delay:
                                # A delay (anything with a delay.value attribute) == #[.#] (converible
                                # to float) is ok; may be changed via web interface.
                                try:
                                    delayseconds = float( delay.value if hasattr(delay, 'value') else delay)
                                    if delayseconds > 0:
                                        time.sleep(delayseconds)
                                except Exception as exc:
                                    logger.info( "Unable to delay; invalid seconds: %r", delay)
                            try:
                                conn.send(rpy)
                            except socket.error as exc:
                                logger.info("Session ended (client abandoned): %s", exc)
                                stats['eof'] = True
                            if data.response.enip.status:
                                logger.warning( "Session ended (server EtherNet/IP status: 0x%02x == %d)",
                                                data.response.enip.status, data.response.enip.status)
                                stats['eof'] = True
                        else:
                            # Session terminated.  No response, just drop connection.
                            if logger.getEffectiveLevel() <= logging.INFO:
                                logger.info("Session ended (client initiated): %s", parser.enip_format(data))
                            stats['eof'] = True
                        logger.info( "Transaction complete after %7.3fs (w/ %7.3fs delay)", cpppo.timer() - begun, delayseconds)
                    except:
                        logger.error("Failed request: %s", parser.enip_format(data))
                        enip_process(address, data=cpppo.dotdict())  # Terminate.
                        raise

                stats['processed'] = source.sent
            except:
                # Parsing failure.
                stats['processed'] = source.sent
                memory = bytes(bytearray(source.memory))
                pos = len(source.memory)
                future = bytes(bytearray(b for b in source))
                where = "at %d total bytes:\n%s\n%s (byte %d)" % (stats.processed, repr(memory + future), '-' * (len(repr(memory)) - 1) + '^', pos)
                logger.error("EtherNet/IP error %s\n\nFailed with exception:\n%s\n", where, ''.join(traceback.format_exception(*sys.exc_info())))
                raise
            finally:
                # Not strictly necessary to close (network.server_main will discard the socket,
                # implicitly closing it), but we'll do it explicitly here in case the thread doesn't die
                # for some other reason.  Clean up the connections entry for this connection address.
                self.connections.pop(connkey, None)
                logger.info( "%s done; processed %3d request%s over %5d byte%s/%5d received (%d connections remain)",
                    name, stats.requests, " " if stats.requests == 1  else "s",
                    stats.processed, " " if stats.processed == 1 else "s",
                    stats.received, len(self.connections))
                sys.stdout.flush()
                conn.close()

    def handle_udp(self, conn, name, enip_process, **kwds):
        """
        Process UDP packets from multiple clients
        """
        with parser.enip_machine(name=name, context='enip') as machine:
            while not kwds['server']['control']['done'] and not kwds['server']['control']['disable']:
                try:
                    source = cpppo.rememberable()
                    data = cpppo.dotdict()

                    # If no/partial EtherNet/IP header received, parsing will fail with a NonTerminal
                    # Exception (dfa exits in non-terminal state).  Build data.request.enip:
                    begun = cpppo.timer()  # waiting for next transaction
                    addr, stats = None, None
                    with contextlib.closing(machine.run(
                            path='request', source=source, data=data)) as engine:
                        # PyPy compatibility; avoid deferred destruction of generators
                        for mch, sta in engine:
                            if sta is not None:
                                # No more transitions available.  Wait for input.
                                continue
                            assert not addr, "Incomplete UDP request from client %r" % (addr)
                            msg = None
                            while msg is None:
                                # For UDP, we'll allow no input only at the start of a new request parse
                                # (addr is None); anything else will be considered a failed request Back
                                # to the trough for more symbols, after having already received a packet
                                # from a peer?  No go!
                                wait = (kwds['server']['control']['latency']
                                        if source.peek() is None else 0)
                                brx = cpppo.timer()
                                msg, frm = network.recvfrom(conn, timeout=wait)
                                now = cpppo.timer()
                                (logger.info if msg else logger.debug)(
                                    "Transaction receive after %7.3fs (%5s bytes in %7.3f/%7.3fs): %r",
                                    now - begun, len(msg) if msg is not None else "None",
                                    now - brx, wait, self.stats_for(frm)[0])
                                # If we're at a None (can't proceed), and we haven't yet received input,
                                # then this is where we implement "Blocking"; we just loop for input.

                            # We have received exactly one packet from an identified peer!
                            begun = now
                            addr = frm
                            stats, _ = self.stats_for(addr)
                            # For UDP, we don't ever receive incoming EOF, or set stats['eof'].
                            # However, we can respond to a manual eof (eg. from web interface) by
                            # ignoring the peer's packets.
                            assert stats and not stats.get('eof'), \
                                "Ignoring UDP request from client %r: %r" % (addr, msg)
                            stats['received'] += len(msg)
                            logger.debug("%s recv: %5d: %s", machine.name_centered(), len(msg), cpppo.reprlib.repr(msg))
                            source.chain(msg)

                    # Terminal state and EtherNet/IP header recognized; process and return response
                    assert stats
                    if 'request' in data:
                        stats['requests'] += 1
                    # enip_process must be able to handle no request (empty data), indicating the
                    # clean termination of the session if closed from this end (not required if
                    # enip_process returned False, indicating the connection was terminated by
                    # request.)
                    if enip_process(addr, data=data, **kwds):
                        # Produce an EtherNet/IP response carrying the encapsulated response data.
                        # If no encapsulated data, ensure we also return a non-zero EtherNet/IP
                        # status.  A non-zero status indicates the end of the session.
                        assert 'response.enip' in data, "Expected EtherNet/IP response; none found"
                        if 'input' not in data.response.enip or not data.response.enip.input:
                            logger.warning("Expected EtherNet/IP response encapsulated message; none found")
                            assert data.response.enip.status, "If no/empty response payload, expected non-zero EtherNet/IP status"

                        rpy = parser.enip_encode(data.response.enip)
                        logger.debug("%s send: %5d: %s", machine.name_centered(),
                                       len(rpy), cpppo.reprlib.repr(rpy))
                        conn.sendto(rpy, addr)

                    logger.debug("Transaction complete after %7.3fs", cpppo.timer() - begun)

                    stats['processed'] = source.sent
                except:
                    # Parsing failure.  Suck out some remaining input to give us some context, but don't re-raise
                    if stats:
                        stats['processed'] = source.sent
                    memory = bytes(bytearray(source.memory))
                    pos = len(source.memory)
                    future = bytes(bytearray(b for b in source))
                    where = "at %d total bytes:\n%s\n%s (byte %d)" % (
                        stats.get('processed', 0) if stats else 0,
                        repr(memory + future), '-' * (len(repr(memory)) - 1) + '^', pos)
                    logger.error("Client %r EtherNet/IP error %s\n\nFailed with exception:\n%s\n", addr, where,
                              ''.join(traceback.format_exception(*sys.exc_info())))


    def start(self, host, port):
        srv_ctl = cpppo.dotdict()
        srv_ctl.control = cpppo.apidict(timeout=self.config.timeout)
        srv_ctl.control['done'] = False
        srv_ctl.control['disable'] = False
        srv_ctl.control.setdefault('latency', self.config.latency)

        tags = cpppo.dotdict()
        options = cpppo.dotdict()
        options.setdefault('enip_process', logix.process)
        kwargs = dict(options, tags=tags, server=srv_ctl)

        tcp_mode = True if self.config.mode == 'tcp' else False
        udp_mode = True if self.config.mode == 'udp' else False

        logger.debug('ENIP server started on: %s:%d, mode: %s' % (
        host, port, self.config.mode))
        while not self.stopped:
            logger.debug('Server loop')

            network.server_main(address=(host, port), target=self.handle,
                                kwargs=kwargs, idle_service=None,
                                udp=udp_mode, tcp=tcp_mode,
                                thread_factory=network.server_thread)

    def stop(self):
        logger.debug('Stopping ENIP server')
        self.stopped = True
