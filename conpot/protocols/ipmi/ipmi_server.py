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

from gevent import socket
from gevent.server import DatagramServer
import struct
import pyghmi.ipmi.private.constants as constants
import pyghmi.ipmi.private.serversession as serversession
import uuid
import hmac
import hashlib
import os
from conpot.helpers import chr_py3
import collections
from lxml import etree
from conpot.protocols.ipmi.fakebmc import FakeBmc
from conpot.protocols.ipmi.fakesession import FakeSession
import conpot.core as conpot_core
import logging as logger


class IpmiServer(object):
    def __init__(self, template, template_directory, args):
        dom = etree.parse(template)
        databus = conpot_core.get_databus()
        self.device_name = databus.get_value(
            dom.xpath("//ipmi/device_info/device_name/text()")[0]
        )
        self.port = None
        self.sessions = dict()

        self.uuid = uuid.uuid4()
        self.kg = None
        self.sock = None
        self.authdata = collections.OrderedDict()
        lanchannel = 1
        authtype = 0b10000000
        authstatus = 0b00000100
        chancap = 0b00000010
        oemdata = (0, 0, 0, 0)
        self.authcap = struct.pack(
            "BBBBBBBBB", 0, lanchannel, authtype, authstatus, chancap, *oemdata
        )
        self.server = None
        self.session = None
        self.bmc = self._configure_users(dom)
        logger.info("Conpot IPMI initialized using %s template", template)

    def _configure_users(self, dom):
        # XML parsing
        authdata_name = dom.xpath("//ipmi/user_list/user/user_name/text()")
        authdata_passwd = dom.xpath("//ipmi/user_list/user/password/text()")
        authdata_name = [i.encode("utf-8") for i in authdata_name]
        authdata_passwd = [i.encode("utf-8") for i in authdata_passwd]
        self.authdata = collections.OrderedDict(zip(authdata_name, authdata_passwd))

        authdata_priv = dom.xpath("//ipmi/user_list/user/privilege/text()")
        if False in map(lambda k: 0 < int(k) <= 4, authdata_priv):
            raise ValueError("Privilege level must be between 1 and 4")
        authdata_priv = [int(k) for k in authdata_priv]
        self.privdata = collections.OrderedDict(zip(authdata_name, authdata_priv))

        activeusers = dom.xpath("//ipmi/user_list/user/active/text()")
        self.activeusers = [1 if x == "true" else 0 for x in activeusers]

        fixedusers = dom.xpath("//ipmi/user_list/user/fixed/text()")
        self.fixedusers = [1 if x == "true" else 0 for x in fixedusers]
        self.channelaccessdata = collections.OrderedDict(
            zip(authdata_name, activeusers)
        )

        return FakeBmc(self.authdata, self.port)

    def _checksum(self, *data):
        csum = sum(data)
        csum ^= 0xFF
        csum += 1
        csum &= 0xFF
        return csum

    def handle(self, data, address):
        # make sure self.session exists
        if not address[0] in self.sessions.keys() or not hasattr(self, "session"):
            # new session for new source
            logger.info("New IPMI traffic from %s", address)
            self.session = FakeSession(address[0], "", "", address[1])
            self.session.server = self
            self.uuid = uuid.uuid4()
            self.kg = None

            self.session.socket = self.sock
            self.sessions[address[0]] = self.session
            self.initiate_session(data, address, self.session)
        else:
            # session already exists
            logger.info("Incoming IPMI traffic from %s", address)
            if self.session.stage == 0:
                self.close_server_session()
            else:
                self._got_request(data, address, self.session)

    def initiate_session(self, data, address, session):
        if len(data) < 22:
            self.close_server_session()
            return
        if not (chr_py3(data[0]) == b"\x06" and data[2:4] == b"\xff\x07"):
            # check rmcp version, sequencenumber and class;
            self.close_server_session()
            return
        if chr_py3(data[4]) == b"\x06":
            # ipmi v2
            session.ipmiversion = 2.0
            session.authtype = 6
            payload_type = chr_py3(data[5])
            if payload_type not in (b"\x00", b"\x10"):
                self.close_server_session()
                return
            if payload_type == b"\x10":
                # new session to handle conversation
                serversession.ServerSession(
                    self.authdata,
                    self.kg,
                    session.sockaddr,
                    self.sock,
                    data[16:],
                    self.uuid,
                    bmc=self,
                )
                serversession.ServerSession.logged = logger
                return
            # data = data[13:]
        if len(data[14:16]) < 2:
            self.close_server_session()
        else:
            myaddr, netfnlun = struct.unpack("2B", data[14:16])
            netfn = (netfnlun & 0b11111100) >> 2
            mylun = netfnlun & 0b11
            if netfn == 6:
                # application request
                if chr_py3(data[19]) == b"\x38":
                    # cmd = get channel auth capabilities
                    verchannel, level = struct.unpack("2B", data[20:22])
                    version = verchannel & 0b10000000
                    if version != 0b10000000:
                        self.close_server_session()
                        return
                    channel = verchannel & 0b1111
                    if channel != 0xE:
                        self.close_server_session()
                        return
                    (clientaddr, clientlun) = struct.unpack("BB", data[17:19])
                    level &= 0b1111
                    self.send_auth_cap(
                        myaddr, mylun, clientaddr, clientlun, session.sockaddr
                    )

    def send_auth_cap(self, myaddr, mylun, clientaddr, clientlun, sockaddr):
        header = b"\x06\x00\xff\x07\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10"

        headerdata = (clientaddr, clientlun | (7 << 2))
        headersum = self._checksum(*headerdata)
        header += struct.pack(
            "BBBBBB", *(headerdata + (headersum, myaddr, mylun, 0x38))
        )
        header += self.authcap
        bodydata = struct.unpack("B" * len(header[17:]), header[17:])
        header += chr_py3(self._checksum(*bodydata))
        self.session.stage += 1
        logger.info("Connection established with %s", sockaddr)
        self.session.send_data(header, sockaddr)

    def close_server_session(self):
        logger.info("IPMI Session closed %s", self.session.sockaddr[0])
        # cleanup session
        del self.sessions[self.session.sockaddr[0]]
        del self.session

    def _got_request(self, data, address, session):
        if chr_py3(data[4]) in (b"\x00", b"\x02"):
            # ipmi 1.5 payload
            session.ipmiversion = 1.5
            remsequencenumber = struct.unpack("<I", data[5:9])[0]
            if (
                hasattr(session, "remsequencenumber")
                and remsequencenumber < session.remsequencenumber
            ):
                self.close_server_session()
                return
            session.remsequencenumber = remsequencenumber
            if ord(chr_py3(data[4])) != session.authtype:
                self.close_server_session()
                return
            remsessid = struct.unpack("<I", data[9:13])[0]
            if remsessid != session.sessionid:
                self.close_server_session()
                return
            rsp = list(struct.unpack("!%dB" % len(data), data))
            authcode = False
            if chr_py3(data[4]) == b"\x02":
                # authcode in ipmi 1.5 packet
                authcode = data[13:29]
                del rsp[13:29]
            payload = list(rsp[14 : 14 + rsp[13]])
            if authcode:
                expectedauthcode = session._ipmi15authcode(
                    payload, checkremotecode=True
                )
                expectedauthcode = struct.pack(
                    "%dB" % len(expectedauthcode), *expectedauthcode
                )
                if expectedauthcode != authcode:
                    self.close_server_session()
                    return
            session._ipmi15(payload)
        elif chr_py3(data[4]) == b"\x06":
            # ipmi 2.0 payload
            session.ipmiversion = 2.0
            session.authtype = 6
            session._ipmi20(data)
        else:
            # unrecognized data
            self.close_server_session()
            return

    def _got_rmcp_openrequest(self, data):
        request = struct.pack("B" * len(data), *data)
        clienttag = ord(chr_py3(request[0]))
        self.clientsessionid = list(struct.unpack("4B", request[4:8]))
        self.managedsessionid = list(struct.unpack("4B", os.urandom(4)))
        self.session.privlevel = 4
        response = (
            [clienttag, 0, self.session.privlevel, 0]
            + self.clientsessionid
            + self.managedsessionid
            + [
                0,
                0,
                0,
                8,
                1,
                0,
                0,
                0,  # auth
                1,
                0,
                0,
                8,
                1,
                0,
                0,
                0,  # integrity
                2,
                0,
                0,
                8,
                1,
                0,
                0,
                0,  # privacy
            ]
        )
        logger.info("IPMI open session request")
        self.session.send_payload(
            response, constants.payload_types["rmcpplusopenresponse"], retry=False
        )

    def _got_rakp1(self, data):
        clienttag = data[0]
        self.Rm = data[8:24]
        self.rolem = data[24]
        self.maxpriv = self.rolem & 0b111
        namepresent = data[27]
        if namepresent == 0:
            self.close_server_session()
            return
        usernamebytes = data[28:]
        self.username = struct.pack("%dB" % len(usernamebytes), *usernamebytes)
        if self.username not in self.authdata:
            logger.info(
                "User {} supplied by client not in user_db.".format(
                    self.username,
                )
            )
            self.close_server_session()
            return
        uuidbytes = self.uuid.bytes
        uuidbytes = list(struct.unpack("%dB" % len(uuidbytes), uuidbytes))
        self.uuiddata = uuidbytes
        self.Rc = list(struct.unpack("16B", os.urandom(16)))
        hmacdata = (
            self.clientsessionid
            + self.managedsessionid
            + self.Rm
            + self.Rc
            + uuidbytes
            + [self.rolem, len(self.username)]
        )
        hmacdata = struct.pack("%dB" % len(hmacdata), *hmacdata)
        hmacdata += self.username
        self.kuid = self.authdata[self.username]
        if self.kg is None:
            self.kg = self.kuid
        authcode = hmac.new(self.kuid, hmacdata, hashlib.sha1).digest()
        authcode = list(struct.unpack("%dB" % len(authcode), authcode))
        newmessage = (
            [clienttag, 0, 0, 0] + self.clientsessionid + self.Rc + uuidbytes + authcode
        )
        logger.info("IPMI rakp1 request")
        self.session.send_payload(
            newmessage, constants.payload_types["rakp2"], retry=False
        )

    def _got_rakp3(self, data):
        RmRc = struct.pack("B" * len(self.Rm + self.Rc), *(self.Rm + self.Rc))
        self.sik = hmac.new(
            self.kg,
            RmRc + struct.pack("2B", self.rolem, len(self.username)) + self.username,
            hashlib.sha1,
        ).digest()
        self.session.k1 = hmac.new(self.sik, b"\x01" * 20, hashlib.sha1).digest()
        self.session.k2 = hmac.new(self.sik, b"\x02" * 20, hashlib.sha1).digest()
        self.session.aeskey = self.session.k2[0:16]

        hmacdata = (
            struct.pack("B" * len(self.Rc), *self.Rc)
            + struct.pack("4B", *self.clientsessionid)
            + struct.pack("2B", self.rolem, len(self.username))
            + self.username
        )
        expectedauthcode = hmac.new(self.kuid, hmacdata, hashlib.sha1).digest()
        authcode = struct.pack("%dB" % len(data[8:]), *data[8:])
        if expectedauthcode != authcode:
            self.close_server_session()
            return
        clienttag = data[0]
        if data[1] != 0:
            self.close_server_session()
            return
        self.session.localsid = struct.unpack(
            "<I", struct.pack("4B", *self.managedsessionid)
        )[0]

        logger.info("IPMI rakp3 request")
        self.session.ipmicallback = self.handle_client_request
        self._send_rakp4(clienttag, 0)

    def _send_rakp4(self, tagvalue, statuscode):
        payload = [tagvalue, statuscode, 0, 0] + self.clientsessionid
        hmacdata = self.Rm + self.managedsessionid + self.uuiddata
        hmacdata = struct.pack("%dB" % len(hmacdata), *hmacdata)
        authdata = hmac.new(self.sik, hmacdata, hashlib.sha1).digest()[:12]
        payload += struct.unpack("%dB" % len(authdata), authdata)
        logger.info("IPMI rakp4 sent")
        self.session.send_payload(
            payload, constants.payload_types["rakp4"], retry=False
        )
        self.session.confalgo = "aes"
        self.session.integrityalgo = "sha1"
        self.session.sessionid = struct.unpack(
            "<I", struct.pack("4B", *self.clientsessionid)
        )[0]

    def handle_client_request(self, request):
        if request["netfn"] == 6 and request["command"] == 0x3B:
            # set session privilage level
            pendingpriv = request["data"][0]
            returncode = 0
            if pendingpriv > 1:
                if pendingpriv > self.maxpriv:
                    returncode = 0x81
                else:
                    self.clientpriv = request["data"][0]
            self.session._send_ipmi_net_payload(code=returncode, data=[self.clientpriv])
            logger.info(
                "IPMI response sent (Set Session Privilege) to %s",
                self.session.sockaddr,
            )
        elif request["netfn"] == 6 and request["command"] == 0x3C:
            # close session
            self.session.send_ipmi_response()
            logger.info(
                "IPMI response sent (Close Session) to %s", self.session.sockaddr
            )
            self.close_server_session()
        elif request["netfn"] == 6 and request["command"] == 0x44:
            # get user access
            # reschan = request["data"][0]
            # channel = reschan & 0b00001111
            resuid = request["data"][1]
            usid = resuid & 0b00011111
            if self.clientpriv > self.maxpriv:
                returncode = 0xD4
            else:
                returncode = 0
            self.usercount = len(self.authdata.keys())
            self.channelaccess = (
                0b0000000 | self.privdata[list(self.authdata.keys())[usid - 1]]
            )
            if self.channelaccessdata[list(self.authdata.keys())[usid - 1]] == "true":
                # channelaccess: 7=res; 6=callin; 5=link; 4=messaging; 3-0=privilege
                self.channelaccess |= 0b00110000

            data = list()
            data.append(self.usercount)
            data.append(sum(self.activeusers))
            data.append(sum(self.fixedusers))
            data.append(self.channelaccess)
            self.session._send_ipmi_net_payload(code=returncode, data=data)
            logger.info(
                "IPMI response sent (Get User Access) to %s", self.session.sockaddr
            )
        elif request["netfn"] == 6 and request["command"] == 0x46:
            # get user name
            userid = request["data"][0]
            returncode = 0
            username = list(self.authdata.keys())[userid - 1]
            data = list(username)
            while len(data) < 16:
                # filler
                data.append(0)
            self.session._send_ipmi_net_payload(code=returncode, data=data)
            logger.info(
                "IPMI response sent (Get User Name) to %s", self.session.sockaddr
            )
        elif request["netfn"] == 6 and request["command"] == 0x45:
            # set user name
            # TODO: fix issue where users can be overwritten
            # python does not support dictionary with duplicate keys
            userid = request["data"][0]
            username = "".join(chr(x) for x in request["data"][1:]).strip(b"\x00")
            oldname = list(self.authdata.keys())[userid - 1]
            # need to recreate dictionary to preserve order
            self.copyauth = collections.OrderedDict()
            self.copypriv = collections.OrderedDict()
            self.copychannel = collections.OrderedDict()
            index = 0
            for k, v in self.authdata.iteritems():
                if index == userid - 1:
                    self.copyauth.update({username: self.authdata[oldname]})
                    self.copypriv.update({username: self.privdata[oldname]})
                    self.copychannel.update({username: self.channelaccessdata[oldname]})
                else:
                    self.copyauth.update({k: v})
                    self.copypriv.update({k: self.privdata[k]})
                    self.copychannel.update({k: self.channelaccessdata[k]})
                index += 1
            self.authdata = self.copyauth
            self.privdata = self.copypriv
            self.channelaccessdata = self.copychannel

            returncode = 0
            self.session._send_ipmi_net_payload(code=returncode)
            logger.info(
                "IPMI response sent (Set User Name) to %s", self.session.sockaddr
            )
        elif request["netfn"] == 6 and request["command"] == 0x47:
            # set user passwd
            passwd_length = request["data"][0] & 0b10000000
            userid = request["data"][0] & 0b00111111
            username = list(self.authdata.keys())[userid - 1]
            operation = request["data"][1] & 0b00000011
            returncode = 0

            if passwd_length:
                # 20 byte
                passwd = "".join(chr(x) for x in request["data"][2:22])
            else:
                # 16 byte
                passwd = "".join(chr(x) for x in request["data"][2:18])
            if operation == 0:
                # disable user
                if self.activeusers[list(self.authdata.keys()).index(username)]:
                    self.activeusers[list(self.authdata.keys()).index(username)] = 0
            elif operation == 1:
                # enable user
                if not self.activeusers[list(self.authdata.keys()).index(username)]:
                    self.activeusers[list(self.authdata.keys()).index(username)] = 1
            elif operation == 2:
                # set passwd
                if len(passwd) not in [16, 20]:
                    returncode = 0x81
                self.authdata[username] = passwd.strip(b"\x00")
            else:
                # test passwd
                if len(passwd) not in [16, 20]:
                    returncode = 0x81
                if self.authdata[username] != passwd.strip(b"\x00"):
                    returncode = 0x80

            self.session._send_ipmi_net_payload(code=returncode)
            logger.info(
                "IPMI response sent (Set User Password) to %s", self.session.sockaddr
            )
        elif request["netfn"] in [0, 6] and request["command"] in [1, 2, 8, 9]:
            self.bmc.handle_raw_request(request, self.session)
        else:
            returncode = 0xC1
            self.session._send_ipmi_net_payload(code=returncode)
            logger.info("IPMI unrecognized command from %s", self.session.sockaddr)
            logger.info(
                "IPMI response sent (Invalid Command) to %s", self.session.sockaddr
            )

    def start(self, host, port):
        connection = (host, port)
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setblocking(True)
        self.sock.bind(connection)
        self.server = DatagramServer(self.sock, self.handle)
        self.server.start()
        logger.info("IPMI server started on: %s", (host, self.server.server_port))
        self.server.serve_forever()

    def stop(self):
        self.server.stop()
