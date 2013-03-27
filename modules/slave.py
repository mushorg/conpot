import struct

from modbus_tk.modbus import Slave, ModbusError, ModbusInvalidRequestError
from modbus_tk import defines, utils


class MBSlave(Slave):

    def __init__(self, slave_id):
        Slave.__init__(self, slave_id)

    def handle_request(self, request_pdu, broadcast=False):
        """
        parse the request pdu, makes the corresponding action
        and returns the response pdu
        """
        with self._data_lock:  # thread-safe
            try:
                # get the function code
                (self.function_code, ) = struct.unpack(">B", request_pdu[0])

                # check if the function code is valid. If not returns error response
                if not self.function_code in self._fn_code_map:
                    raise ModbusError(defines.ILLEGAL_FUNCTION)

                # if read query is broadcasted raises an error
                cant_be_broadcasted = (defines.READ_COILS, defines.READ_DISCRETE_INPUTS,
                                       defines.READ_INPUT_REGISTERS, defines.READ_HOLDING_REGISTERS)
                if broadcast and (self.function_code in cant_be_broadcasted):
                    raise ModbusInvalidRequestError("Function %d can not be broadcasted" % self.function_code)

                # execute the corresponding function
                response_pdu = self._fn_code_map[self.function_code](request_pdu)
                if response_pdu:
                    if broadcast:
                        print("broadcast: %s" % (utils.get_log_buffer("!!", response_pdu)))
                        return ""
                    else:
                        return struct.pack(">B", self.function_code) + response_pdu
                raise Exception("No response for function %d" % self.function_code)

            except ModbusError as e:
                print(str(e))
                return struct.pack(">BB", self.function_code + 128, e.get_exception_code())