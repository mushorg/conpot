import struct
import random

import gevent
from gevent import socket

from session import Session, call_with_optional_args, initialtimeout

from conpot.utils.udp_server import DatagramServer


class FakeSession(Session):

    def fake_cb(self, response):
        print repr(response)

    def __init__(self, bmc, userid, password, port=623):
        self.sockaddr = (bmc, port)
        self._initsession()
        self.expectednetfn = 6
        self.expectedcmd = 56
        self.ipmicallback = self.fake_cb


class IPMIServer(DatagramServer):

    def handle(self, msg, address):
        print repr(msg), address
        #session.sockaddr = None
        if not address[0] in self.sessions.keys():
            self.session = FakeSession(address[0], "Administrator", "Password", port=address[1])
            self.sessions[address[0]] = self.session
        else:
            print 'known source'
        self.sessions[address[0]].waiting_sessions[self.session] = None
        try:
            ret = self.sessions[address[0]]._handle_ipmi_packet(msg)
            print repr(ret)
            if ret:
                resp = self.sessions[address[0]]._send_ipmi_net_payload(ret["netfqn"], ret["command"], ret["data"][0])
                self.send_message(resp, address)
        except KeyError:
            print "Session del error"
            del self.sessions[address[0]]
            return
        except struct.error:
            print "Data unpack error"
            del self.sessions[address[0]]
            return
        else:
            self.expectednetfn = 511
            self.expectedcmd = 511

    def send_message(self, message, remote_address):
        self.socket.sendto(message, remote_address)

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sessions = dict()
        udp_sock = gevent.socket.socket(gevent.socket.AF_INET, gevent.socket.SOCK_DGRAM)
        udp_sock.setsockopt(gevent.socket.SOL_SOCKET, gevent.socket.SO_BROADCAST, 1)
        udp_sock.bind((self.host, self.port))
        DatagramServer.__init__(self, udp_sock, handle=self.handle)


if __name__ == "__main__":
    simpi_server = IPMIServer("localhost", 6230)
    try:
        simpi_server.serve_forever()
    except KeyboardInterrupt:
        print "bye"