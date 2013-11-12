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

from datetime import datetime
import time

from gevent.server import StreamServer
import gevent.monkey

gevent.monkey.patch_all()
import uuid
import socket
from tpkt import TPKT
from cotp import COTP as COTP_BASE_packet
from cotp import COTP_ConnectionRequest
from cotp import COTP_ConnectionConfirm
from s7 import S7

import logging
from lxml import etree

logger = logging.getLogger(__name__)


class S7Server(object):
    def __init__(self, template, log_queue):

        self.log_queue = log_queue
        self.timeout = 5
        self.ssl_lists = {}
        S7.ssl_lists = self.ssl_lists

        dom = etree.parse(template)
        template_name = dom.xpath('//conpot_template/@name')[0]

        system_status_lists = dom.xpath('//conpot_template/s7comm/system_status_lists/*')
        for ssl in system_status_lists:
            ssl_id = ssl.attrib['id']
            ssl_dict = {}
            self.ssl_lists[ssl_id] = ssl_dict
            items = ssl.xpath('./*')
            for item in items:
                item_id = item.attrib['id']
                value = item.xpath('./text()')[0] if len(item.xpath('./text()')) else ''
                ssl_dict[item_id] = value

        logger.debug('Conpot debug info: S7 SSL/SZL: {0}'.format(self.ssl_lists))
        logger.info('Conpot S7Comm initialized using the {0} template.'.format(template_name))

    def _add_log_data(self, req, resp):
        elapse_ms = int((time.time() - self.start_time) * 1000)
        while elapse_ms in self.session_data["data"]:
            elapse_ms += 1
        self.session_data['data'][elapse_ms] = {'request': req.encode('hex'), 'response': resp.encode('hex')}

    def handle(self, sock, address):
        sock.settimeout(self.timeout)
        session_id = str(uuid.uuid4())
        self.session_data = {'session_id': session_id, 'remote': address, 'timestamp': datetime.utcnow(),
                             'data_type': 's7comm', 'data': {}}
        self.start_time = time.time()
        logger.info('New connection from {0}:{1}. ({2})'.format(address[0], address[1], session_id))
        fileobj = sock.makefile()

        try:
            while True:

                data = fileobj.readline()
                if not data:
                    break

                tpkt_packet = TPKT().parse(data)
                cotp_base_packet = COTP_BASE_packet().parse(tpkt_packet.payload)
                if cotp_base_packet.tpdu_type == 0xe0:

                    # connection request
                    cotp_cr_request = COTP_ConnectionRequest().dissect(cotp_base_packet.payload)
                    logger.debug('Received COTP Connection Request: dst-ref:{0} src-ref:{1} dst-tsap:{2} src-tsap:{3} '
                                 'tpdu-size:{4}. ({5})'.format(cotp_cr_request.dst_ref, cotp_cr_request.src_ref,
                                                               cotp_cr_request.dst_tsap, cotp_cr_request.src_tsap,
                                                               cotp_cr_request.tpdu_size, session_id))

                    # confirm connection response
                    cotp_cc_response = COTP_ConnectionConfirm(cotp_cr_request.src_ref, cotp_cr_request.dst_ref, 0,
                                                              cotp_cr_request.src_tsap, cotp_cr_request.dst_tsap,
                                                              0x0a).assemble()

                    # encapsulate and transmit
                    cotp_resp_base_packet = COTP_BASE_packet(0xd0, 0, cotp_cc_response).pack()
                    tpkt_resp_packet = TPKT(3, cotp_resp_base_packet).pack()
                    sock.send(tpkt_resp_packet)

                    self._add_log_data(data, tpkt_resp_packet)

                    data = sock.recv(1024)

                    # another round of parsing payloads
                    tpkt_packet = TPKT().parse(data)
                    cotp_base_packet = COTP_BASE_packet().parse(tpkt_packet.payload)

                    if cotp_base_packet.tpdu_type == 0xf0:
                        logger.debug('Received known COTP TPDU: {0}. ({1})'.format(cotp_base_packet.tpdu_type,
                                                                                   session_id))

                        # will throw exception if the packet does not contain the S7 magic number (0x32)
                        S7_packet = S7().parse(cotp_base_packet.trailer)
                        logger.debug('Received S7 packet: magic:{0} pdu_type:{1} reserved:{2} req_id:{3} param_len:{4} '
                                     'data_len:{5} result_inf:{6}'.format(
                            S7_packet.magic, S7_packet.pdu_type,
                            S7_packet.reserved, S7_packet.request_id,
                            S7_packet.param_length, S7_packet.data_length,
                            S7_packet.result_info, session_id))

                        # request pdu
                        if S7_packet.pdu_type == 1:

                            # 0xf0 == Request for connect / pdu negotiate
                            if S7_packet.param == 0xf0:

                                # create S7 response packet
                                s7_resp_negotiate_packet = S7(3, 0, S7_packet.request_id, 0,
                                                              S7_packet.parameters).pack()
                                # wrap s7 the packet in cotp
                                cotp_resp_negotiate_packet = COTP_BASE_packet(0xf0, 0x80,
                                                                              s7_resp_negotiate_packet).pack()
                                # wrap the cotp packet
                                tpkt_resp_packet = TPKT(3, cotp_resp_negotiate_packet).pack()
                                sock.send(tpkt_resp_packet)

                                self._add_log_data(data, tpkt_resp_packet)

                                #handshake done, give some more data.
                                data = sock.recv(1024)

                                while data:
                                    tpkt_packet = TPKT().parse(data)
                                    cotp_base_packet = COTP_BASE_packet().parse(tpkt_packet.payload)

                                    if cotp_base_packet.tpdu_type == 0xf0:
                                        S7_packet = S7().parse(cotp_base_packet.trailer)
                                        logger.debug('Received S7 packet: magic:{0} pdu_type:{1} reserved:{2} '
                                                     'req_id:{3} param_len:{4} data_len:{5} result_inf:{6}'.format(
                                            S7_packet.magic, S7_packet.pdu_type,
                                            S7_packet.reserved, S7_packet.request_id,
                                            S7_packet.param_length, S7_packet.data_length,
                                            S7_packet.result_info, session_id))

                                        response_param, response_data = S7_packet.handle()
                                        s7_resp_ssl_packet = S7(7, 0, S7_packet.request_id, 0, response_param,
                                                                response_data).pack()
                                        cotp_resp_ssl_packet = COTP_BASE_packet(0xf0, 0x80, s7_resp_ssl_packet).pack()
                                        tpkt_resp_packet = TPKT(3, cotp_resp_ssl_packet).pack()
                                        sock.send(tpkt_resp_packet)

                                        self._add_log_data(data, tpkt_resp_packet)

                                    data = sock.recv(1024)
                    else:
                        logger.debug(
                            'Received unknown COTP TPDU after handshake: {0}'.format(cotp_base_packet.tpdu_type))
                else:
                    logger.debug('Received unknown COTP TPDU before handshake: {0}'.format(cotp_base_packet.tpdu_type))

        except socket.timeout:
            logger.debug('Socket timeout, remote: {0}. ({1})'.format(address[0], session_id))

        self.log_queue.put(self.session_data)

    def get_server(self, host, port):
        connection = (host, port)
        server = StreamServer(connection, self.handle)
        logger.info('S7Comm server started on: {0}'.format(connection))
        return server
