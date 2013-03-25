import struct
import logging

import modbus_tk.modbus_tcp as modbus_tcp
import modbus_tk.defines as mdef
from modbus_tk import modbus

import slave_base

from gevent.server import StreamServer

FORMAT = '%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger('modbus_tk')


class ModbusServer(modbus.Server):

    def __init__(self, port=502, address='127.0.0.1', timeout_in_sec=1, databank=None):
        """Constructor: initializes the server settings"""
        modbus.Server.__init__(self, databank if databank else modbus.Databank())
        #creates a slave with id 0
        slave1 = self.add_slave(1)
        #add 2 blocks of holding registers
        slave1.add_block("a", mdef.HOLDING_REGISTERS, 1, 100)  # address 0, length 100
        slave1.add_block("b", mdef.HOLDING_REGISTERS, 200, 20)  # address 200, length 20

        #creates another slave with id 5
        slave5 = self.add_slave(5)
        slave5.add_block("c", mdef.COILS, 0, 100)
        slave5.add_block("d", mdef.HOLDING_REGISTERS, 0, 100)

        #set the values of registers at address 0
        slave1.set_values("a", 1, range(100))

    def handle(self, socket, address):
        print 'New connection from %s:%s' % address
        self.fileobj = socket.makefile()
        while True:
            request = self.fileobj.read(7)
            if not request:
                print "client disconnected"
                break
            if request.strip().lower() == 'quit':
                print "client quit"
                break
            tr_id, pr_id, length = struct.unpack(">HHH", request[:6])
            while len(request) < (length + 6):
                new_byte = self.fileobj.read(1)
                request += new_byte
            query = modbus_tcp.TcpQuery()
            response = self._databank.handle_request(query, request)
            if response:
                self.fileobj.write(response)
                self.fileobj.flush()


if __name__ == "__main__":
    modbus_server = ModbusServer(databank=slave_base.SlaveBase())
    server = StreamServer(('localhost', 502), modbus_server.handle)
    server.serve_forever()
