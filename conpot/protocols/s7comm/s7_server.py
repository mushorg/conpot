# Copyright (C) 2013  Johnny Vestergaard <jkv@unixcluster.dk>
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

import time

import codecs
import socket
from struct import unpack
from conpot.protocols.s7comm.tpkt import TPKT
from conpot.protocols.s7comm.cotp import COTP as COTP_BASE_packet
from conpot.protocols.s7comm.cotp import COTP_ConnectionRequest
from conpot.protocols.s7comm.cotp import COTP_ConnectionConfirm
from conpot.protocols.s7comm.s7 import S7
from conpot.protocols.s7comm.s7_memory_map import S7MemoryMap
import conpot.core as conpot_core
from conpot.core.protocol_wrapper import conpot_protocol
from conpot.utils.asyncio_serve import serve_tcp_sync_handler

import asyncio
import logging

logger = logging.getLogger(__name__)


@conpot_protocol
class S7Server(object):
    def __init__(self, template, template_directory, args):
        self.timeout = 5
        self.ssl_lists = {}
        self.memory_map = S7MemoryMap()
        self.server = None
        S7.ssl_lists = self.ssl_lists
        S7.memory_map = self.memory_map
        self.start_time = None  # Initialize later

        for ssl in template.get("system_status_lists", []):
            ssl_id = ssl["id"]
            ssl_dict = {}
            self.ssl_lists[ssl_id] = ssl_dict
            for item in ssl.get("items", []):
                ssl_dict[item["id"]] = item.get("value", "")

        self.memory_map.load_config(template.get("memory_areas", []))

        logger.debug("Conpot debug info: S7 SSL/SZL: {0}".format(self.ssl_lists))
        logger.info("Conpot S7Comm initialized")

    def handle(self, sock, address):
        sock.settimeout(self.timeout)
        session = conpot_core.get_session(
            "s7comm",
            address[0],
            address[1],
            sock.getsockname()[0],
            sock.getsockname()[1],
        )
        self.start_time = time.time()
        logger.info(
            "New S7 connection from {0}:{1}. ({2})".format(
                address[0], address[1], session.id
            )
        )
        session.log_event(event_type="NEW_CONNECTION")

        try:
            while True:
                data = sock.recv(4, socket.MSG_WAITALL)
                if len(data) == 0:
                    session.log_event(event_type="CONNECTION_LOST")
                    break

                _, _, length = unpack("!BBH", data[:4])
                # check for length
                if length <= 4:
                    logger.info("S7 error: Invalid length")
                    session.log_event(error="S7 error: Invalid length")
                    break
                data += sock.recv(length - 4, socket.MSG_WAITALL)

                tpkt_packet = TPKT().parse(data)
                cotp_base_packet = COTP_BASE_packet().parse(tpkt_packet.payload)
                if cotp_base_packet.tpdu_type == 0xE0:
                    # connection request
                    cotp_cr_request = COTP_ConnectionRequest().dissect(
                        cotp_base_packet.payload
                    )
                    logger.info(
                        "Received COTP Connection Request: dst-ref:{0} src-ref:{1} dst-tsap:{2} src-tsap:{3} "
                        "tpdu-size:{4}. ({5})".format(
                            cotp_cr_request.dst_ref,
                            cotp_cr_request.src_ref,
                            cotp_cr_request.dst_tsap,
                            cotp_cr_request.src_tsap,
                            cotp_cr_request.tpdu_size,
                            session.id,
                        )
                    )

                    # confirm connection response
                    cotp_cc_response = COTP_ConnectionConfirm(
                        cotp_cr_request.src_ref,
                        cotp_cr_request.dst_ref,
                        0,
                        cotp_cr_request.src_tsap,
                        cotp_cr_request.dst_tsap,
                        0x0A,
                    ).assemble()

                    # encapsulate and transmit
                    cotp_resp_base_packet = COTP_BASE_packet(
                        0xD0, 0, cotp_cc_response
                    ).pack()
                    tpkt_resp_packet = TPKT(3, cotp_resp_base_packet).pack()
                    sock.send(tpkt_resp_packet)

                    session.log_event(
                        request=codecs.encode(data, "hex"),
                        response=codecs.encode(tpkt_resp_packet, "hex"),
                    )

                    data = sock.recv(1024)

                    # another round of parsing payloads
                    tpkt_packet = TPKT().parse(data)
                    cotp_base_packet = COTP_BASE_packet().parse(tpkt_packet.payload)

                    if cotp_base_packet.tpdu_type == 0xF0:
                        logger.info(
                            "Received known COTP TPDU: {0}. ({1})".format(
                                cotp_base_packet.tpdu_type, session.id
                            )
                        )

                        # will throw exception if the packet does not contain the S7 magic number (0x32)
                        S7_packet = S7().parse(cotp_base_packet.trailer)
                        logger.info(
                            "Received S7 packet: magic:%s pdu_type:%s reserved:%s req_id:%s param_len:%s "
                            "data_len:%s result_inf:%s session_id:%s",
                            S7_packet.magic,
                            S7_packet.pdu_type,
                            S7_packet.reserved,
                            S7_packet.request_id,
                            S7_packet.param_length,
                            S7_packet.data_length,
                            S7_packet.result_info,
                            session.id,
                        )

                        # request pdu
                        if S7_packet.pdu_type == 1:
                            # 0xf0 == Request for connect / pdu negotiate
                            if S7_packet.param == 0xF0:
                                # create S7 response packet
                                s7_resp_negotiate_packet = S7(
                                    3, 0, S7_packet.request_id, 0, S7_packet.parameters
                                ).pack()
                                # wrap s7 the packet in cotp
                                cotp_resp_negotiate_packet = COTP_BASE_packet(
                                    0xF0, 0x80, s7_resp_negotiate_packet
                                ).pack()
                                # wrap the cotp packet
                                tpkt_resp_packet = TPKT(
                                    3, cotp_resp_negotiate_packet
                                ).pack()
                                sock.send(tpkt_resp_packet)

                                session.log_event(
                                    request=codecs.encode(data, "hex"),
                                    response=codecs.encode(tpkt_resp_packet, "hex"),
                                )

                                # handshake done, give some more data.
                                data = sock.recv(1024)

                                while data:
                                    tpkt_packet = TPKT().parse(data)
                                    cotp_base_packet = COTP_BASE_packet().parse(
                                        tpkt_packet.payload
                                    )

                                    if cotp_base_packet.tpdu_type == 0xF0:
                                        S7_packet = S7().parse(cotp_base_packet.trailer)
                                        logger.info(
                                            "Received S7 packet: magic:%s pdu_type:%s reserved:%s "
                                            "req_id:%s param_len:%s data_len:%s result_inf:%s session_id:%s",
                                            S7_packet.magic,
                                            S7_packet.pdu_type,
                                            S7_packet.reserved,
                                            S7_packet.request_id,
                                            S7_packet.param_length,
                                            S7_packet.data_length,
                                            S7_packet.result_info,
                                            session.id,
                                        )

                                        (
                                            response_param,
                                            response_data,
                                        ) = S7_packet.handle(
                                            address[0], session=session
                                        )
                                        # Job read/write and CPU stop/start → Ack-Data (0x03);
                                        # SZL/userdata → 0x07
                                        if S7_packet.param in (0x04, 0x05, 0x28, 0x29):
                                            resp_pdu_type = 3
                                        else:
                                            resp_pdu_type = 7
                                        s7_resp_packet = S7(
                                            resp_pdu_type,
                                            0,
                                            S7_packet.request_id,
                                            0,
                                            response_param,
                                            response_data,
                                        ).pack()
                                        cotp_resp_packet = COTP_BASE_packet(
                                            0xF0, 0x80, s7_resp_packet
                                        ).pack()
                                        tpkt_resp_packet = TPKT(
                                            3, cotp_resp_packet
                                        ).pack()
                                        sock.send(tpkt_resp_packet)

                                        session.log_event(
                                            request=codecs.encode(data, "hex"),
                                            response=codecs.encode(
                                                tpkt_resp_packet, "hex"
                                            ),
                                        )

                                    data = sock.recv(1024)
                    else:
                        logger.info(
                            "Received unknown COTP TPDU after handshake: {0}".format(
                                cotp_base_packet.tpdu_type
                            )
                        )
                        session.log_event(
                            error="Received unknown COTP TPDU after handshake: {0}".format(
                                cotp_base_packet.tpdu_type
                            )
                        )
                else:
                    logger.info(
                        "Received unknown COTP TPDU before handshake: {0}".format(
                            cotp_base_packet.tpdu_type
                        )
                    )
                    session.log_event(
                        error="Received unknown COTP TPDU before handshake: {0}".format(
                            cotp_base_packet.tpdu_type
                        )
                    )

        except socket.timeout:
            session.log_event(event_type="CONNECTION_LOST")
            logger.debug(
                "Socket timeout, remote: {0}. ({1})".format(address[0], session.id)
            )
        except socket.error:
            session.log_event(event_type="CONNECTION_LOST")
            logger.debug(
                "Connection reset by peer, remote: {0}. ({1})".format(
                    address[0], session.id
                )
            )
        except Exception as e:
            logger.exception(
                "Exception caught {0}, remote: {1}. ({2})".format(
                    e, address[0], session.id
                )
            )

    async def start(self, host, port):
        self.host = host
        self.port = port
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        logger.info("S7Comm server started on: {0}".format((host, port)))
        await serve_tcp_sync_handler(
            host,
            port,
            self,
            stop_event=self._stop,
            ready_event=self._ready,
            name="S7Server",
        )

    def stop(self):
        if hasattr(self, "_stop"):
            self._stop.set()
