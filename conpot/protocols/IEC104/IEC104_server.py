# Copyright (C) 2017  Patrick Reichenberger (University of Passau) <patrick.reichenberger@t-online.de>
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
import asyncio
import errno
import logging
import socket
import struct

import conpot.core as conpot_core

from conpot.core.protocol_wrapper import conpot_protocol
from conpot.protocols.IEC104.DeviceDataController import DeviceDataController
from conpot.protocols.IEC104.IEC104 import IEC104, ProtocolTimeout
from conpot.utils.asyncio_serve import serve_tcp_sync_handler
from .errors import Timeout_t1, Timeout_t3
from .frames import TESTFR_act

logger = logging.getLogger(__name__)


@conpot_protocol
class IEC104Server(object):
    def __init__(self, template, template_directory, args):
        self.timeout = conpot_core.get_databus().get_value("T_0")
        self.device_data_controller = DeviceDataController(template)
        self.server_active = True
        self.server = None
        logger.info("IEC 104 Server up")
        self.template = template

    def _next_recv_timeout(self, iec104_handler, timeout_t3):
        waits = [float(self.timeout)]
        if timeout_t3 is not None:
            remaining = timeout_t3.remaining()
            if remaining is not None:
                waits.append(remaining)
        t1_remaining = iec104_handler.earliest_t1_remaining()
        if t1_remaining is not None:
            waits.append(t1_remaining)
        return max(0.01, min(waits))

    def _recv_or_timeout(self, sock, nbytes, iec104_handler, timeout_t3):
        sock.settimeout(self._next_recv_timeout(iec104_handler, timeout_t3))
        try:
            return sock.recv(nbytes)
        except socket.timeout:
            iec104_handler.raise_if_t1_expired()
            if timeout_t3 is not None and timeout_t3.expired():
                raise Timeout_t3()
            return None

    def handle(self, sock, address):
        sock.settimeout(self.timeout)
        session = conpot_core.get_session(
            "IEC104",
            address[0],
            address[1],
            sock.getsockname()[0],
            sock.getsockname()[1],
        )
        logger.info(
            "New IEC 104 connection from %s:%s. (%s)",
            address[0],
            address[1],
            session.id,
        )
        session.add_event({"type": "NEW_CONNECTION"})
        iec104_handler = IEC104(self.device_data_controller, sock, address, session.id)
        try:
            while True:
                timeout_t3 = ProtocolTimeout(
                    conpot_core.get_databus().get_value("T_3"), Timeout_t3
                )
                timeout_t3.start()
                try:
                    try:
                        request = None
                        while request is None:
                            request = self._recv_or_timeout(
                                sock, 6, iec104_handler, timeout_t3
                            )
                        if not request:
                            logger.info("IEC104 Station disconnected. (%s)", session.id)
                            session.add_event({"type": "CONNECTION_LOST"})
                            iec104_handler.disconnect()
                            break
                        # Gather start + length bytes. An empty recv is EOF; without
                        # this check a single-byte write followed by close busy-loops
                        # (issue #482) and never yields to T_3.
                        while len(request) < 2:
                            new_byte = self._recv_or_timeout(
                                sock, 1, iec104_handler, timeout_t3
                            )
                            if new_byte is None:
                                continue
                            if not new_byte:
                                break
                            request += new_byte
                        if len(request) < 2:
                            logger.info(
                                "IEC104 Station disconnected with incomplete "
                                "header. (%s)",
                                session.id,
                            )
                            session.add_event({"type": "CONNECTION_LOST"})
                            iec104_handler.disconnect()
                            break

                        _, length = struct.unpack(">BB", request[:2])
                        while len(request) < (length + 2):
                            new_byte = self._recv_or_timeout(
                                sock, 1, iec104_handler, timeout_t3
                            )
                            if new_byte is None:
                                continue
                            if not new_byte:
                                break
                            request += new_byte

                        if len(request) < (length + 2):
                            logger.info(
                                "IEC104 Station disconnected with incomplete "
                                "APDU. (%s)",
                                session.id,
                            )
                            session.add_event({"type": "CONNECTION_LOST"})
                            iec104_handler.disconnect()
                            break

                        # check if IEC 104 packet or for the first occurrence of the indication 0x68 for IEC 104
                        for elem in list(request):
                            if 0x68 == elem:
                                index = request.index(elem)

                                iec_request = request[index:]
                                timeout_t3.cancel()
                                response = None
                                # check which frame type
                                if not (iec_request[2] & 0x01):  # i_frame
                                    response = iec104_handler.handle_i_frame(
                                        iec_request
                                    )
                                elif iec_request[2] & 0x01 and not (
                                    iec_request[2] & 0x02
                                ):  # s_frame
                                    iec104_handler.handle_s_frame(iec_request)
                                elif iec_request[2] & 0x03:  # u_frame
                                    response = iec104_handler.handle_u_frame(
                                        iec_request
                                    )
                                else:
                                    logger.warning(
                                        "%s ---> No valid IEC104 type (%s)",
                                        address,
                                        session.id,
                                    )

                                if response:
                                    for resp_packet in response:
                                        if resp_packet:
                                            sock.send(resp_packet)
                                break

                    except Timeout_t3:
                        pkt = iec104_handler.send_104frame(TESTFR_act)
                        if pkt:
                            sock.send(pkt)
                    finally:
                        timeout_t3.cancel()
                except Timeout_t1:
                    logger.warning("T1 timed out. (%s)", session.id)
                    logger.info("IEC104 Station disconnected. (%s)", session.id)
                    session.add_event({"type": "CONNECTION_LOST"})
                    iec104_handler.disconnect()
                    break
        except socket.timeout:
            logger.debug("Socket timeout, remote: %s. (%s)", address[0], session.id)
            session.add_event({"type": "CONNECTION_LOST"})
            iec104_handler.disconnect()
        except socket.error as err:
            if isinstance(err.args, tuple):
                if err.errno == errno.EPIPE:
                    # remote peer disconnected
                    logger.info("IEC104 Station disconnected. (%s)", session.id)
                    session.add_event({"type": "CONNECTION_LOST"})
                else:
                    # determine and handle different error
                    pass
            else:
                print(("socket error ", err))
            iec104_handler.disconnect()
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
        logger.info("IEC 60870-5-104 protocol server started on: %s", (host, port))
        await serve_tcp_sync_handler(
            host,
            port,
            self,
            stop_event=self._stop,
            ready_event=self._ready,
            name="IEC104Server",
        )

    def stop(self):
        if hasattr(self, "_stop"):
            self._stop.set()
