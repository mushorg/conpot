import struct
from lxml import etree

from modbus_tk.modbus import Databank, DuplicatedKeyError, MissingKeyError
from modbus_tk import defines

from conpot.protocols.modbus.slave import MBSlave


class SlaveBase(Databank):
    """
    Database keeping track of the slaves.
    """

    def __init__(self, template):
        Databank.__init__(self)
        self.dom = etree.parse(template)

    def add_slave(self, slave_id):
        """
        Add a new slave with the given id
        """
        if (slave_id <= 0) or (slave_id > 255):
            raise Exception("Invalid slave id %d" % slave_id)
        if not slave_id in self._slaves:
            self._slaves[slave_id] = MBSlave(slave_id, self.dom)
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
        func_code = None
        slave = None
        response = None

        try:
            # extract the pdu and the slave id
            slave_id, request_pdu = query.parse_request(request)
            if len(request_pdu) > 0:
                (func_code, ) = struct.unpack(">B", request_pdu[0])
            # 43 is Device Information
            if func_code == 43:
                # except will throw MissingKeyError
                slave = self.get_slave(slave_id)
                response_pdu = slave.handle_request(request_pdu)
                # make the full response
                response = query.build_response(response_pdu)
            # get the slave and let him execute the action
            elif slave_id == 0:
                # broadcast
                for key in self._slaves:
                    response_pdu = self._slaves[key].handle_request(request_pdu, broadcast=True)
                    response = query.build_response(response_pdu)
            elif slave_id == 255:
                r = struct.pack(">BB", func_code + 0x80, 0x0B)
                response = query.build_response(r)
            else:
                slave = self.get_slave(slave_id)
                response_pdu = slave.handle_request(request_pdu)
                # make the full response
                response = query.build_response(response_pdu)
        except (IOError, MissingKeyError) as e:
            # If the request was not handled correctly, return a server error response
            r = struct.pack(">BB", func_code + 0x80, defines.SLAVE_DEVICE_FAILURE)
            response = query.build_response(r)

        if slave:
            function_code = slave.function_code

        return (response, {'request': request_pdu.encode('hex'),
                           'slave_id': slave_id,
                           'function_code': function_code,
                           'response': response_pdu.encode('hex')})
