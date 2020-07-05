# modified by Sooky Peter <xsooky00@stud.fit.vutbr.cz>
# Brno University of Technology, Faculty of Information Technology
import struct
from lxml import etree
import codecs
from modbus_tk.modbus import (
    Databank,
    DuplicatedKeyError,
    MissingKeyError,
    ModbusInvalidRequestError,
)
from modbus_tk import defines

from conpot.protocols.modbus.slave import MBSlave
import logging

logger = logging.getLogger(__name__)


class SlaveBase(Databank):

    """
    Database keeping track of the slaves.
    """

    def __init__(self, template):
        Databank.__init__(self)
        self.dom = etree.parse(template)

    def add_slave(self, slave_id, unsigned=True, memory=None):
        """
        Add a new slave with the given id
        """
        if (slave_id < 0) or (slave_id > 255):
            raise Exception("Invalid slave id %d" % slave_id)
        if slave_id not in self._slaves:
            self._slaves[slave_id] = MBSlave(slave_id, self.dom)
            return self._slaves[slave_id]
        else:
            raise DuplicatedKeyError("Slave %d already exists" % slave_id)

    def handle_request(self, query, request, mode):
        """
        Handles a request. Return value is a tuple where element 0
        is the response object and element 1 is a dictionary
        of items to log.
        """
        request_pdu = None
        response_pdu = b""
        slave_id = None
        function_code = None
        func_code = None
        slave = None
        response = None

        try:
            # extract the pdu and the slave id
            slave_id, request_pdu = query.parse_request(request)
            if len(request_pdu) > 0:
                (func_code,) = struct.unpack(">B", request_pdu[:1])

            logger.debug("Working mode: %s" % mode)

            if mode == "tcp":
                if slave_id == 0 or slave_id == 255:
                    slave = self.get_slave(slave_id)
                    response_pdu = slave.handle_request(request_pdu)
                    response = query.build_response(response_pdu)
                else:
                    # TODO:
                    # Shall we return SLAVE DEVICE FAILURE, or ILLEGAL ACCESS?
                    # Would it be better to make this configurable?
                    r = struct.pack(
                        ">BB", func_code + 0x80, defines.SLAVE_DEVICE_FAILURE
                    )
                    response = query.build_response(r)

            elif mode == "serial":
                if slave_id == 0:  # broadcasting
                    for key in self._slaves:
                        response_pdu = self._slaves[key].handle_request(
                            request_pdu, broadcast=True
                        )

                    # no response is sent back
                    return (
                        None,
                        {
                            "request": request_pdu.encode("hex"),
                            "slave_id": slave_id,
                            "function_code": func_code,
                            "response": "",
                        },
                    )
                elif 0 < slave_id <= 247:  # normal request handling
                    slave = self.get_slave(slave_id)
                    response_pdu = slave.handle_request(request_pdu)
                    # make the full response
                    response = query.build_response(response_pdu)
                else:
                    # TODO:
                    # Same here. Return SLAVE DEVICE FAILURE or ILLEGAL ACCESS?
                    r = struct.pack(
                        ">BB", func_code + 0x80, defines.SLAVE_DEVICE_FAILURE
                    )
                    response = query.build_response(r)

        except (MissingKeyError, IOError) as e:
            logger.error(e)
            # If slave was not found or the request was not handled correctly,
            # return a server error response
            r = struct.pack(">BB", func_code + 0x80, defines.SLAVE_DEVICE_FAILURE)
            response = query.build_response(r)
        except ModbusInvalidRequestError as e:
            logger.error(e)
            # TODO: return something here?

        if slave:
            function_code = slave.function_code

        return (
            response,
            {
                "request": codecs.encode(request_pdu, "hex"),
                "slave_id": slave_id,
                "function_code": function_code,
                "response": codecs.encode(response_pdu, "hex"),
            },
        )
