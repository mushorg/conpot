import struct

from modbus_tk.modbus import Databank, DuplicatedKeyError, MissingKeyError

from modbus_tk import defines

from conpot.modbus.slave import MBSlave


class SlaveBase(Databank):
    """
    Database keeping track of the slaves.
    """

    def __init__(self):
        Databank.__init__(self)

    def add_slave(self, slave_id):
        """
        Add a new slave with the given id
        """
        if (slave_id <= 0) or (slave_id > 255):
            raise Exception("Invalid slave id %d" % slave_id)
        if not slave_id in self._slaves:
            self._slaves[slave_id] = MBSlave(slave_id)
            return self._slaves[slave_id]
        else:
            raise DuplicatedKeyError("Slave %d already exists" % slave_id)

    def handle_request(self, query, request):
        """
        Handles a request. Return value is a tuple where element 0 is the response object and element 1 is a dictionary
        of items to log.
        """
        request_pdu = None
        response_pdu = ""
        slave_id = None
        function_code = None
        slave = None

        try:
            #extract the pdu and the slave id
            slave_id, request_pdu = query.parse_request(request)
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
        except (IOError, MissingKeyError) as excpt:
            func_code = 1
            if len(request_pdu) > 0:
                (func_code, ) = struct.unpack(">B", request_pdu[0])
                #If the request was not handled correctly, return a server error response
            r = struct.pack(">BB", func_code + 0x80, defines.SLAVE_DEVICE_FAILURE)
            response = query.build_response(r)

        if slave:
            function_code = slave.function_code

        return (response, {'request': request_pdu.encode('hex'),
                           'slave_id': slave_id,
                           'function_code': function_code,
                           'response': response_pdu.encode('hex')})




