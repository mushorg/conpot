import gevent
from gevent import socket

from session import Session

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
        session = FakeSession(address[0], "Administrator", "Password", port=address[1])
        #session.sockaddr = None
        session.waiting_sessions[self] = "foo"
        try:
            session._handle_ipmi_packet(msg)
        except:
            raise

    def __init__(self, host, port):
        self.host = host
        self.port = port
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