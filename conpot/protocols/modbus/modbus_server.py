# modified by Sooky Peter <xsooky00@stud.fit.vutbr.cz>
# Brno University of Technology, Faculty of Information Technology
import asyncio
import codecs
import logging
import socket
import struct
import sys
import time

from lxml import etree

import conpot.core as conpot_core
from conpot.core.protocol_wrapper import conpot_protocol
from conpot.protocols.modbus import slave_db
from conpot.protocols.modbus.slave import BLOCK_TYPES, ModbusInvalidRequestError
from conpot.utils.asyncio_serve import serve_tcp_sync_handler

logger = logging.getLogger(__name__)


@conpot_protocol
class ModbusServer(object):
    """Modbus/TCP honeypot.

    pymodbus decodes and encodes PDUs. Accept / session / MBAP checks stay in
    Conpot (stock ModbusTcpServer would hide unit-id 255 and address layout).
    """

    def __init__(self, template, template_directory, args):
        self.timeout = 5
        self.delay = None
        self.mode = None
        self.host = None
        self.port = None
        self.server = None
        self._databank = slave_db.SlaveBase(template)

        self._get_mode_and_delay(template)
        self._configure_slaves(template)

    def _get_mode_and_delay(self, template):
        dom = etree.parse(template)
        self.mode = dom.xpath("//modbus/mode/text()")[0].lower()
        if self.mode not in ["tcp", "serial"]:
            logger.error(
                "Conpot modbus initialization failed due to incorrect"
                " settings. Check the modbus template file"
            )
            sys.exit(3)
        try:
            self.delay = int(dom.xpath("//modbus/delay/text()")[0])
        except ValueError:
            logger.error(
                "Conpot modbus initialization failed due to incorrect"
                " settings. Check the modbus template file"
            )
            sys.exit(3)

    def _configure_slaves(self, template):
        dom = etree.parse(template)
        slaves = dom.xpath("//modbus/slaves/*")
        try:
            for slave_xml in slaves:
                slave_id = int(slave_xml.attrib["id"])
                slave = self._databank.add_slave(slave_id)
                logger.debug("Added slave with id %s.", slave_id)
                for block in slave_xml.xpath("./blocks/*"):
                    name = block.attrib["name"]
                    block_type_name = block.xpath("./type/text()")[0]
                    request_type = BLOCK_TYPES[block_type_name]
                    start_addr = int(block.xpath("./starting_address/text()")[0])
                    size = int(block.xpath("./size/text()")[0])
                    slave.add_block(name, request_type, start_addr, size)
                    logger.debug(
                        "Added block %s to slave %s. (type=%s, start=%s, size=%s)",
                        name,
                        slave_id,
                        request_type,
                        start_addr,
                        size,
                    )

            logger.info("Conpot modbus initialized")
        except Exception as exc:
            logger.error(exc)

    def handle(self, sock, address):
        sock.settimeout(self.timeout)

        session = conpot_core.get_session(
            "modbus",
            address[0],
            address[1],
            sock.getsockname()[0],
            sock.getsockname()[1],
        )

        logger.info(
            "New Modbus connection from %s:%s. (%s)",
            address[0],
            address[1],
            session.id,
        )
        session.add_event({"type": "NEW_CONNECTION"})

        try:
            while True:
                request = None
                try:
                    request = sock.recv(7)
                except socket.timeout:
                    raise
                except Exception as exc:
                    logger.error(
                        "Exception occurred in ModbusServer.handle() "
                        "at sock.recv(): %s",
                        str(exc),
                    )

                if not request:
                    logger.info("Modbus client disconnected. (%s)", session.id)
                    session.add_event({"type": "CONNECTION_LOST"})
                    break
                if request.strip().lower() == b"quit.":
                    logger.info("Modbus client quit. (%s)", session.id)
                    session.add_event({"type": "CONNECTION_QUIT"})
                    break
                if len(request) < 7:
                    logger.info(
                        "Modbus client provided data %s but invalid.", session.id
                    )
                    session.add_event({"type": "CONNECTION_TERMINATED"})
                    break
                _transaction, _protocol, length = struct.unpack(">HHH", request[:6])
                # MBAP length covers unit id + PDU. Legal minimum is 2
                # (unit id + function code). Length 0/1 are reserved/malformed;
                # scanners (e.g. nmap modbus-info) often send length 0, and
                # length 1 yields an empty PDU that used to crash the greenlet
                # (issue #511).
                if length < 2:
                    logger.info(
                        "Modbus client %s declared an invalid length %s, "
                        "dropping connection. (%s)",
                        address[0],
                        length,
                        session.id,
                    )
                    session.add_event({"type": "CONNECTION_TERMINATED"})
                    break
                # A conforming Modbus/TCP frame never needs more than 254
                # bytes here (1-byte unit id + up to 253 bytes of PDU, the
                # limit inherited from serial Modbus). An unauthenticated
                # client can otherwise declare up to 0xFFFF and force this
                # handler to read that much, which - since Conpot runs every
                # protocol as greenlets on one shared event loop - can stall
                # every other emulated service for the duration of the read.
                if length > 254:
                    logger.info(
                        "Modbus client %s declared an oversized length %s, "
                        "dropping connection. (%s)",
                        address[0],
                        length,
                        session.id,
                    )
                    session.add_event({"type": "CONNECTION_TERMINATED"})
                    break
                while len(request) < (length + 6):
                    try:
                        remaining = (length + 6) - len(request)
                        new_bytes = sock.recv(remaining)
                        if not new_bytes:
                            break
                        request += new_bytes
                    except socket.timeout:
                        break
                    except Exception:
                        break
                # Peer closed or timed out before the declared body arrived.
                if len(request) < (length + 6):
                    logger.info(
                        "Modbus client %s sent incomplete request "
                        "(got %s bytes, expected %s). (%s)",
                        address[0],
                        len(request),
                        length + 6,
                        session.id,
                    )
                    session.add_event({"type": "CONNECTION_TERMINATED"})
                    break

                try:
                    response, logdata = self._databank.handle_request(
                        request, self.mode
                    )
                except ModbusInvalidRequestError as exc:
                    logger.info(
                        "Modbus client %s sent invalid MBAP: %s (%s)",
                        address[0],
                        exc,
                        session.id,
                    )
                    session.add_event({"type": "CONNECTION_TERMINATED"})
                    break
                logdata["request"] = codecs.encode(request, "hex")
                session.add_event(logdata)

                logger.info(
                    "Modbus traffic from %s: %s (%s)", address[0], logdata, session.id
                )

                if response:
                    sock.sendall(response)
                    logger.info("Modbus response sent to %s", address[0])
                else:
                    # response is None for a serial broadcast (slave id 0) and
                    # for frames we refuse to answer (empty PDU, bad address).
                    if (self.mode == "serial") and (logdata["slave_id"] == 0):
                        time.sleep(self.delay / 1000)
                        logger.debug("Modbus server's turnaround delay expired.")
                        logger.info(
                            "Modbus connection terminated with client %s.", address[0]
                        )
                        session.add_event({"type": "CONNECTION_TERMINATED"})
                        sock.shutdown(socket.SHUT_RDWR)
                        sock.close()
                        break
                    else:
                        logger.info(
                            "Modbus client ignored due to invalid addressing. (%s)",
                            session.id,
                        )
                        session.add_event({"type": "CONNECTION_TERMINATED"})
                        sock.shutdown(socket.SHUT_RDWR)
                        sock.close()
                        break
        except socket.timeout:
            logger.debug("Socket timeout, remote: %s. (%s)", address[0], session.id)
            session.add_event({"type": "CONNECTION_LOST"})
        finally:
            try:
                sock.close()
            except Exception:
                pass

    async def start(self, host, port):
        self.host = host
        self.port = port
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        logger.info("Modbus server starting on: %s:%s", host, port)
        await serve_tcp_sync_handler(
            host,
            port,
            self,
            stop_event=self._stop,
            ready_event=self._ready,
            name="ModbusServer",
        )

    def stop(self):
        if hasattr(self, "_stop"):
            self._stop.set()
