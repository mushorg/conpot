import struct

from modbus_tk.modbus import Databank
from modbus_tk import defines


class SlaveBase(Databank):
    """
    Database keeping track of the slaves.
    """
    def __init__(self):
        Databank.__init__(self)

    def handle_request(self, query, request):
        """
        When a request is received, handle it and returns the response pdu
        """
        self.request_pdu = None
        self.slave_id = None
        self.slave = None
        try:
            #extract the pdu and the slave id
            self.slave_id, self.request_pdu = query.parse_request(request)

            #get the slave and let him executes the action
            if self.slave_id == 0:
                #broadcast
                for key in self._slaves:
                    self._slaves[key].handle_request(self.request_pdu, broadcast=True)
                return
            else:
                self.slave = self.get_slave(self.slave_id)
                response_pdu = self.slave.handle_request(self.request_pdu)
                #make the full response
                response = query.build_response(response_pdu)
                return response
        except Exception as excpt:
            print("handle request failed: " + str(excpt))
        except:
            print("handle request failed: unknown error")

        #If the request was not handled correctly, return a server error response
        func_code = 1
        if len(self.request_pdu) > 0:
            (func_code, ) = struct.unpack(">B", self.request_pdu[0])
        return struct.pack(">BB", func_code+0x80, defines.SLAVE_DEVICE_FAILURE)
