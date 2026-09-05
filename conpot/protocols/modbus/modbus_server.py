# modified by Sooky Peter <xsooky00@stud.fit.vutbr.cz>
# Brno University of Technology, Faculty of Information Technology
import struct
import socket
import time
import logging
import sys
import codecs
from lxml import etree
from gevent.server import StreamServer

import modbus_tk.modbus_tcp as modbus_tcp
from modbus_tk import modbus

# Following imports are required for modbus template evaluation
import modbus_tk.defines as mdef
from conpot.core.protocol_wrapper import conpot_protocol
from conpot.protocols.modbus import slave_db
import conpot.core as conpot_core

logger = logging.getLogger(__name__)


@conpot_protocol
class ModbusServer(modbus.Server):
    def __init__(self, template, template_directory, args):
        self.timeout = 5
        self.delay = None
        self.mode = None
        self.host = None
        self.port = None
        self.server = None

        databank = slave_db.SlaveBase(template)

        # Constructor: initializes the server settings
        modbus.Server.__init__(self, databank if databank else modbus.Databank())

        # retrieve mode of connection and turnaround delay from the template
        self._get_mode_and_delay(template)

        # not sure how this class remember slave configuration across
        # instance creation, i guess there are some
        # well hidden away class variables somewhere.
        self.remove_all_slaves()
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
            for s in slaves:
                slave_id = int(s.attrib["id"])
                slave = self.add_slave(slave_id)
                logger.debug("Added slave with id %s.", slave_id)
                for b in s.xpath("./blocks/*"):
                    name = b.attrib["name"]
                    request_type = eval("mdef." + b.xpath("./type/text()")[0])
                    start_addr = int(b.xpath("./starting_address/text()")[0])
                    size = int(b.xpath("./size/text()")[0])
                    slave.add_block(name, request_type, start_addr, size)
                    logger.debug(
                        "Added block %s to slave %s. " "(type=%s, start=%s, size=%s)",
                        name,
                        slave_id,
                        request_type,
                        start_addr,
                        size,
                    )

            logger.info("Conpot modbus initialized")
        except Exception as e:
            logger.error(e)

    def handle(self, sock, address):
        sock.settimeout(self.timeout)

        session = conpot_core.get_session(
            "modbus",
            address[0],
            address[1],
            sock.getsockname()[0],
            sock.getsockname()[1],
        )

        self.start_time = time.time()
        logger.info(
            "New Modbus connection from %s:%s. (%s)", address[0], address[1], session.id
        )
        session.log_event(event_type="NEW_CONNECTION")

        try:
            while True:
                request = None
                try:
                    request = sock.recv(7)
                except Exception as e:
                    logger.error(
                        "Exception occurred in ModbusServer.handle() "
                        "at sock.recv(): %s",
                        str(e),
                    )

                if not request:
                    logger.info("Modbus client disconnected. (%s)", session.id)
                    session.log_event(event_type="CONNECTION_LOST")
                    break
                if request.strip().lower() == "quit.":
                    logger.info("Modbus client quit. (%s)", session.id)
                    session.log_event(event_type="CONNECTION_QUIT")
                    break
                if len(request) < 7:
                    logger.info(
                        "Modbus client provided data {} but invalid.".format(session.id)
                    )
                    session.log_event(event_type="CONNECTION_TERMINATED")
                    break
                _, _, length = struct.unpack(">HHH", request[:6])
                # MBAP length covers unit id + PDU and must be at least 1.
                # Scanners (e.g. nmap modbus-info) often send length 0; that
                # fails modbus_tk's MBAP check and used to kill this greenlet.
                if length < 1:
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
                # handler to read up to ~64KB one byte at a time via
                # sock.recv(1) below, which - since Conpot runs every
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
                    session.log_event(event_type="CONNECTION_TERMINATED")
                    break
                while len(request) < (length + 6):
                    try:
                        remaining = (length + 6) - len(request)
                        new_bytes = sock.recv(remaining)
                        if not new_bytes:
                            break
                        request += new_bytes
                    except Exception:
                        break
                # Peer closed or timed out before the declared body arrived.
                # Do not hand a truncated frame to modbus_tk - parse_request
                # raises ModbusInvalidMbapError and would crash the greenlet.
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
                query = modbus_tcp.TcpQuery()

                # logdata is a dictionary containing request, slave_id,
                # function_code and response
                try:
                    response, logdata = self._databank.handle_request(
                        query, request, self.mode
                    )
                except modbus_tcp.ModbusInvalidMbapError as e:
                    logger.info(
                        "Modbus client %s sent invalid MBAP: %s (%s)",
                        address[0],
                        e,
                        session.id,
                    )
                    session.add_event({"type": "CONNECTION_TERMINATED"})
                    break
                logdata["request"] = codecs.encode(request, "hex")
                session.log_event(
                    request=logdata.get("request"),
                    response=logdata.get("response"),
                    **{
                        k: v
                        for k, v in logdata.items()
                        if k not in ("request", "response", "type")
                    },
                )

                logger.info(
                    "Modbus traffic from %s: %s (%s)", address[0], logdata, session.id
                )

                if response:
                    sock.sendall(response)
                    logger.info("Modbus response sent to %s", address[0])
                else:
                    # TODO:
                    # response could be None under several different cases

                    # MB serial connection addressing UID=0
                    if (self.mode == "serial") and (logdata["slave_id"] == 0):
                        # delay is in milliseconds
                        time.sleep(self.delay / 1000)
                        logger.debug("Modbus server's turnaround delay expired.")
                        logger.info(
                            "Modbus connection terminated with client %s.", address[0]
                        )
                        session.log_event(event_type="CONNECTION_TERMINATED")
                        sock.shutdown(socket.SHUT_RDWR)
                        sock.close()
                        break
                    # Invalid addressing
                    else:
                        logger.info(
                            "Modbus client ignored due to invalid addressing." " (%s)",
                            session.id,
                        )
                        session.log_event(event_type="CONNECTION_TERMINATED")
                        sock.shutdown(socket.SHUT_RDWR)
                        sock.close()
                        break
        except socket.timeout:
            logger.debug("Socket timeout, remote: %s. (%s)", address[0], session.id)
            session.log_event(event_type="CONNECTION_LOST")

    def start(self, host, port):
        self.host = host
        self.port = port
        connection = (host, port)
        self.server = StreamServer(connection, self.handle)
        logger.info("Modbus server started on: %s", connection)
        self.server.serve_forever()

    def stop(self):
        self.server.stop()
