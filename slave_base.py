import struct

from modbus_tk.modbus import Slave, DuplicatedKeyError, MissingKeyError
from modbus_tk import defines


class SlaveBase:
    """
    Database keeping track of the slaves.
    """
    def __init__(self):
        self._slaves = {}

    def add_slave(self, slave_id):
        """
        Add a new slave with the given id
        """
        if (slave_id <= 0) or (slave_id > 255):
            raise Exception("Invalid slave id %d" % slave_id)
        if not slave_id in self._slaves:
            self._slaves[slave_id] = Slave(slave_id)
            return self._slaves[slave_id]
        else:
            raise DuplicatedKeyError("Slave %d already exists" % slave_id)

    def get_slave(self, slave_id):
        """
        Get the slave with the given id
        """
        if self._slaves.has_key(slave_id):
            return self._slaves[slave_id]
        else:
            raise MissingKeyError("Slave %d doesn't exist" % slave_id)

    def remove_slave(self, slave_id):
        """
        Remove the slave with the given id
        """
        if self._slaves.has_key(slave_id):
            self._slaves.pop(slave_id)
        else:
            raise MissingKeyError("Slave %d already exists" % slave_id)

    def remove_all_slaves(self):
        """
        Clean the list of slaves
        """
        self._slaves.clear()

    def handle_request(self, query, request):
        """
        When a request is received, handle it and returns the response pdu
        """
        request_pdu = ""
        try:
            #extract the pdu and the slave id
            (slave_id, request_pdu) = query.parse_request(request)

            #get the slave and let him executes the action
            if slave_id == 0:
                #broadcast
                for key in self._slaves:
                    self._slaves[key].handle_request(request_pdu, broadcast=True)
                return
            else:
                slave = self.get_slave(slave_id)
                response_pdu = slave.handle_request(request_pdu)
                #make the full response
                response = query.build_response(response_pdu)
                return response
        except Exception as excpt:
            print("handle request failed: " + str(excpt))
        except:
            print("handle request failed: unknown error")

        #If the request was not handled correctly, return a server error response
        func_code = 1
        if len(request_pdu) > 0:
            (func_code, ) = struct.unpack(">B", request_pdu[0])
        return struct.pack(">BB", func_code+0x80, defines.SLAVE_DEVICE_FAILURE)
