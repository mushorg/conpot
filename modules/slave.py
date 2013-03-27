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
        with self._data_lock: #thread-safe
            try:
                # get the function code
                (function_code, ) = struct.unpack(">B", request_pdu[0])

                # check if the function code is valid. If not returns error response
                if not self._fn_code_map.has_key(function_code):
                    raise ModbusError(defines.ILLEGAL_FUNCTION)

                # if read query is broadcasted raises an error
                cant_be_broadcasted = (defines.READ_COILS, defines.READ_DISCRETE_INPUTS,
                                      defines.READ_INPUT_REGISTERS, defines.READ_HOLDING_REGISTERS)
                if broadcast and (function_code in cant_be_broadcasted):
                    raise ModbusInvalidRequestError("Function %d can not be broadcasted" % function_code)

                #execute the corresponding function
                response_pdu = self._fn_code_map[function_code](request_pdu)
                if response_pdu:
                    if broadcast:
                        print("broadcast: %s" % (utils.get_log_buffer("!!", response_pdu)))
                        return ""
                    else:
                        return struct.pack(">B", function_code) + response_pdu
                raise Exception("No response for function %d" % function_code)

            except ModbusError, excpt:
                print(str(excpt))
                return struct.pack(">BB", function_code+128, excpt.get_exception_code())