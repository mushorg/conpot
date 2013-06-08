from gevent import socket
from gevent.server import StreamServer
from ConfigParser import ConfigParser

from bacpypes.comm import PDU
from bacpypes.debugging import Logging
from bacpypes.app import LocalDeviceObject, Application


class BACnetApp(Application, Logging):

    def __init__(self, device, address):
        Application.__init__(self, device, address)

    def request(self, apdu):
        Application.request(self, apdu)

    def indication(self, apdu):
        Application.indication(self, apdu)

    def response(self, apdu):
        Application.response(self, apdu)

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
            msg = fp.readline()
            print msg
            if msg:
                apdu = PDU(msg)
                bacnet_app.indication(apdu)
                print apdu
                fp.write(apdu)
                fp.flush()
            else:
                break
        sock.shutdown(socket.SHUT_WR)
        sock.close()


if __name__ == "__main__":
    server_handler = BACnetServer()
    server = StreamServer(('', 9000), server_handler.handle_echo)
    server.serve_forever()