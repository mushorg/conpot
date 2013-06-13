from gevent import socket
from gevent.server import StreamServer
from ConfigParser import ConfigParser

from bacpypes.debugging import Logging
from bacpypes.app import LocalDeviceObject, Application
from bacpypes.apdu import APDU, apdu_types, unconfirmed_request_types, PDU


class BACnetApp(Application, Logging):

    def __init__(self, device, address):
        Application.__init__(self, device, address)

    def request(self, apdu):
        print "ret", apdu
        self.ret_val = apdu

    def indication(self, apdu):
        Application.indication(self, apdu)

    def response(self, apdu):
        print "response"

    def confirmation(self, apdu):
        Application.confirmation(self, apdu)


class BACnetServer():
    def __init__(self):
        self.config = ConfigParser()
        self.config.read('bacnet.ini')
        self.thisDevice = LocalDeviceObject(
            objectName=self.config.get('BACpypes', 'objectName'),
            objectIdentifier=self.config.getint('BACpypes', 'objectIdentifier'),
            maxApduLengthAccepted=self.config.getint('BACpypes', 'maxApduLengthAccepted'),
            segmentationSupported=self.config.get('BACpypes', 'segmentationSupported'),
            vendorIdentifier=self.config.getint('BACpypes', 'vendorIdentifier')
        )

    def handle_echo(self, sock, address):
        bacnet_app = BACnetApp(self.thisDevice, self.config.get('BACpypes', 'address'))
        fp = sock.makefile()
        while True:
            msg = fp.read(6)
            if msg:
                f = PDU()
                f.pduData = msg
                # TODO: Handle other types of PDU besides APDU
                b = APDU()
                b.decode(f)
                b.debug_contents()
                atype = apdu_types.get(b.apduType)
                # This is easy to handle as long as atype is UnconfirmedRequestPDU
                atype = unconfirmed_request_types.get(b.apduService)
                c = atype()
                c.decode(b)
                bacnet_app.indication(c)
                fp.write("bar")
                fp.flush()
            else:
                break
        sock.shutdown(socket.SHUT_WR)
        sock.close()


if __name__ == "__main__":
    server_handler = BACnetServer()
    server = StreamServer(('', 9000), server_handler.handle_echo)
    server.serve_forever()