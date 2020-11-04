# Copyright 2015 Lenovo
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Author: Peter Sooky <xsooky00@stud.fit.vubtr.cz>
# Brno University of Technology, Faculty of Information Technology


import struct
import os
import socket
import logging

import pyghmi.exceptions as exc
import pyghmi.ipmi.private.constants as constants
from pyghmi.ipmi.private.session import Session

import random
import hmac
import hashlib
from Crypto.Cipher import AES

logger = logging.getLogger(__name__)


def _monotonic_time():
    return os.times()[4]


class FakeSession(Session):
    def __init__(self, bmc, userid, password, port):
        self.lastpayload = None
        self.servermode = True
        self.privlevel = 4
        self.request_entry = []
        self.socket = None
        self.response = None
        self.stage = 0
        self.bmc = bmc
        self.port = port
        self.bmc_handlers = {}
        self.userid = userid
        self.password = password
        self._initsession()
        self.sockaddr = (bmc, port)
        self.server = None
        self.sol_handler = None
        self.ipmicallback = self._generic_callback
        logger.info("New IPMI session initialized for client (%s)", self.sockaddr)

    def _generic_callback(self, response):
        self.lastresponse = response

    def _ipmi20(self, rawdata):
        data = list(struct.unpack("%dB" % len(rawdata), rawdata))
        # payload type numbers in IPMI specification Table 13-16; 6 bits
        payload_type = data[5] & 0b00111111
        # header = data[:15]; message = data[16:]
        if payload_type == 0x10:
            # rmcp+ open session request
            return self.server._got_rmcp_openrequest(data[16:])
        elif payload_type == 0x11:
            # ignore: rmcp+ open session response
            return
        elif payload_type == 0x12:
            # rakp message 1
            return self.server._got_rakp1(data[16:])
        elif payload_type == 0x13:
            # ignore: rakp message 2
            return
        elif payload_type == 0x14:
            # rakp message 3
            return self.server._got_rakp3(data[16:])
        elif payload_type == 0x15:
            # ignore: rakp message 4
            return
        elif payload_type == 0 or payload_type == 1:
            # payload_type == 0; IPMI message
            # payload_type == 1; SOL(Serial Over Lan)
            if not (data[5] & 0b01000000):
                # non-authenticated payload
                self.server.close_server_session()
                return
            encryption_bit = 0
            if data[5] & 0b10000000:
                # using AES-CBC-128
                encryption_bit = 1
            authcode = rawdata[-12:]
            if self.k1 is None:
                # we are in no shape to process a packet now
                self.server.close_server_session()
                return
            expectedauthcode = hmac.new(self.k1, rawdata[4:-12], hashlib.sha1).digest()[
                :12
            ]
            if authcode != expectedauthcode:
                # BMC failed to assure integrity to us, drop it
                self.server.close_server_session()
                return
            sid = struct.unpack("<I", rawdata[6:10])[0]
            if sid != self.localsid:
                # session id mismatch, drop it
                self.server.close_server_session()
                return
            remseqnumber = struct.unpack("<I", rawdata[10:14])[0]
            if hasattr(self, "remseqnumber"):
                if remseqnumber < self.remseqnumber and self.remseqnumber != 0xFFFFFFFF:
                    self.server.close_server_session()
                    return
            self.remseqnumber = remseqnumber
            psize = data[14] + (data[15] << 8)
            payload = data[16 : 16 + psize]
            if encryption_bit:
                iv = rawdata[16:32]
                decrypter = AES.new(self.aeskey, AES.MODE_CBC, iv)
                decrypted = decrypter.decrypt(
                    struct.pack("%dB" % len(payload[16:]), *payload[16:])
                )
                payload = struct.unpack("%dB" % len(decrypted), decrypted)
                padsize = payload[-1] + 1
                payload = list(payload[:-padsize])
            if payload_type == 0:
                self._ipmi15(payload)
            elif payload_type == 1:
                if self.last_payload_type == 1:
                    self.lastpayload = None
                    self.last_payload_type = None
                    self.waiting_sessions.pop(self, None)
                    if len(self.pendingpayloads) > 0:
                        (
                            nextpayload,
                            nextpayloadtype,
                            retry,
                        ) = self.pendingpayloads.popleft()
                        self.send_payload(
                            payload=nextpayload,
                            payload_type=nextpayloadtype,
                            retry=retry,
                        )
                if self.sol_handler:
                    # FIXME: self.sol_handler(payload)
                    pass
        else:
            logger.error("IPMI Unrecognized payload type.")
            self.server.close_server_session()
            return

    def _ipmi15(self, payload):
        self.seqlun = payload[4]
        self.clientaddr = payload[3]
        self.clientnetfn = (payload[1] >> 2) + 1
        self.clientcommand = payload[5]
        self._parse_payload(payload)
        return

    def _parse_payload(self, payload):
        if hasattr(self, "hasretried"):
            if self.hasretried:
                self.hasretried = 0
                self.tabooseq[(self.expectednetfn, self.expectedcmd, self.seqlun)] = 16
        self.expectednetfn = 0x1FF
        self.expectedcmd = 0x1FF
        self.waiting_sessions.pop(self, None)
        self.lastpayload = None
        self.last_payload_type = None
        response = {}
        response["netfn"] = payload[1] >> 2
        del payload[0:5]
        # remove the trailing checksum
        del payload[-1]
        response["command"] = payload[0]
        del payload[0:1]
        response["data"] = payload
        self.timeout = 0.5 + (0.5 * random.random())
        self.ipmicallback(response)

    def _send_ipmi_net_payload(
        self,
        netfn=None,
        command=None,
        data=None,
        code=0,
        bridge_request=None,
        retry=None,
        delay_xmit=None,
    ):
        if data is None:
            data = []
        if retry is None:
            retry = not self.servermode
        data = [code] + data
        if netfn is None:
            netfn = self.clientnetfn
        if command is None:
            command = self.clientcommand
        if data[0] is None and len(data) == 1:
            self.server.close_server_session()
            return
        ipmipayload = self._make_ipmi_payload(netfn, command, bridge_request, data)
        payload_type = constants.payload_types["ipmi"]
        self.send_payload(
            payload=ipmipayload,
            payload_type=payload_type,
            retry=retry,
            delay_xmit=delay_xmit,
        )

    def _make_ipmi_payload(self, netfn, command, bridge_request=None, data=()):
        bridge_msg = []
        self.expectedcmd = command
        self.expectednetfn = netfn + 1
        # IPMI spec forbids gaps bigger then 7 in seq number.
        # seqincrement = 7

        if bridge_request:
            addr = bridge_request.get("addr", 0x0)
            channel = bridge_request.get("channel", 0x0)
            bridge_msg = self._make_bridge_request_msg(channel, netfn, command)
            rqaddr = constants.IPMI_BMC_ADDRESS
            rsaddr = addr
        else:
            rqaddr = self.rqaddr
            rsaddr = constants.IPMI_BMC_ADDRESS
        rsaddr = self.clientaddr
        header = [rsaddr, netfn << 2]

        reqbody = [rqaddr, self.seqlun, command] + list(data)
        headsum = self.server._checksum(*header)
        bodysum = self.server._checksum(*reqbody)
        payload = header + [headsum] + reqbody + [bodysum]
        if bridge_request:
            payload = bridge_msg + payload
            tail_csum = self.server._checksum(*payload[3:])
            payload.append(tail_csum)
        return payload

    def _aespad(self, data):
        newdata = list(data)
        currlen = len(data) + 1
        neededpad = currlen % 16
        if neededpad:
            neededpad = 16 - neededpad
        padval = 1
        while padval <= neededpad:
            newdata.append(padval)
            padval += 1
        newdata.append(neededpad)
        return newdata

    def send_payload(
        self,
        payload=(),
        payload_type=None,
        retry=True,
        delay_xmit=None,
        needskeepalive=False,
    ):
        if payload and self.lastpayload:
            self.pendingpayloads.append((payload, payload_type, retry))
            return
        if payload_type is None:
            payload_type = self.last_payload_type
        if not payload:
            payload = self.lastpayload
        # constant RMCP header for IPMI
        message = [0x6, 0x00, 0xFF, 0x07]
        if retry:
            self.lastpayload = payload
            self.last_payload_type = payload_type
        message.append(self.authtype)
        baretype = payload_type
        if self.integrityalgo:
            payload_type |= 0b01000000
        if self.confalgo:
            payload_type |= 0b10000000

        if self.ipmiversion == 2.0:
            message.append(payload_type)
            if baretype == 2:
                raise NotImplementedError("OEM Payloads")
            elif baretype not in constants.payload_types.values():
                raise NotImplementedError("Unrecognized payload type %d" % baretype)
            message += struct.unpack("!4B", struct.pack("<I", self.sessionid))
        message += struct.unpack("!4B", struct.pack("<I", self.sequencenumber))
        if self.ipmiversion == 1.5:
            message += struct.unpack("!4B", struct.pack("<I", self.sessionid))
            if not self.authtype == 0:
                message += self._ipmi15authcode(payload)
            message.append(len(payload))
            message += payload
            totlen = 34 + len(message)
            if totlen in (56, 84, 112, 128, 156):
                # Legacy pad as mandated by ipmi spec
                message.append(0)
        elif self.ipmiversion == 2.0:
            psize = len(payload)
            if self.confalgo:
                pad = (psize + 1) % 16
                if pad:
                    # if no pad needed, then we take no more action
                    pad = 16 - pad
                newpsize = psize + pad + 17
                message.append(newpsize & 0xFF)
                message.append(newpsize >> 8)
                iv = os.urandom(16)
                message += list(struct.unpack("16B", iv))
                payloadtocrypt = self._aespad(payload)
                crypter = AES.new(self.aeskey, AES.MODE_CBC, iv)
                crypted = crypter.encrypt(
                    struct.pack("%dB" % len(payloadtocrypt), *payloadtocrypt)
                )
                crypted = list(struct.unpack("%dB" % len(crypted), crypted))
                message += crypted
            else:
                # no confidetiality algorithm
                message.append(psize & 0xFF)
                message.append(psize >> 8)
                message += list(payload)
            if self.integrityalgo:
                neededpad = (len(message) - 2) % 4
                if neededpad:
                    neededpad = 4 - neededpad
                message += [0xFF] * neededpad
                message.append(neededpad)
                message.append(7)
                integdata = message[4:]
                authcode = hmac.new(
                    self.k1,
                    struct.pack("%dB" % len(integdata), *integdata),
                    hashlib.sha1,
                ).digest()[
                    :12
                ]  # SHA1-96 - per RFC2404 truncates to 96 bits
                message += struct.unpack("12B", authcode)
        self.netpacket = struct.pack("!%dB" % len(message), *message)
        self.stage += 1
        self._xmit_packet(retry, delay_xmit=delay_xmit)

    def send_ipmi_response(self, data=None, code=0):
        if data is None:
            data = []
        self._send_ipmi_net_payload(data=data, code=code)

    def _xmit_packet(self, retry=True, delay_xmit=None):
        if self.sequencenumber:
            self.sequencenumber += 1
        if delay_xmit is not None:
            # skip transmit, let retry timer do it's thing
            self.waiting_sessions[self] = {}
            self.waiting_sessions[self]["ipmisession"] = self
            self.waiting_sessions[self]["timeout"] = delay_xmit + _monotonic_time()
            return
        if self.sockaddr:
            self.send_data(self.netpacket, self.sockaddr)
        else:
            self.allsockaddrs = []
            try:
                for res in socket.getaddrinfo(
                    self.bmc, self.port, 0, socket.SOCK_DGRAM
                ):
                    sockaddr = res[4]
                    if res[0] == socket.AF_INET:
                        # convert the sockaddr to AF_INET6
                        newhost = "::ffff:" + sockaddr[0]
                        sockaddr = (newhost, sockaddr[1], 0, 0)
                    self.allsockaddrs.append(sockaddr)
                    self.bmc_handlers[sockaddr] = self
                    self.send_data(self.netpacket, sockaddr)
            except socket.gaierror:
                raise exc.IpmiException("Unable to transmit to specified address")
        if retry:
            self.waiting_sessions[self] = {}
            self.waiting_sessions[self]["ipmisession"] = self
            self.waiting_sessions[self]["timeout"] = self.timeout + _monotonic_time()

    def send_data(self, packet, address):
        logger.info("IPMI response sent to %s", address)
        logger.debug("IPMI: Sending response {} to client {}".format(packet, address))
        self.socket.sendto(packet, address)
