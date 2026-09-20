"""Blocking Modbus/TCP client for tests.

pymodbus' sync ``ModbusTcpClient`` sets the socket non-blocking and drives it
with ``select``. Tests build PDUs with pymodbus and send them on a stdlib socket.
"""

import socket
import struct

from pymodbus.pdu.bit_message import (
    ReadCoilsRequest,
    ReadCoilsResponse,
    ReadDiscreteInputsRequest,
    ReadDiscreteInputsResponse,
    WriteMultipleCoilsRequest,
)
from pymodbus.pdu.register_message import (
    ReadHoldingRegistersRequest,
    ReadHoldingRegistersResponse,
    ReadInputRegistersRequest,
    ReadInputRegistersResponse,
    WriteMultipleRegistersRequest,
)

READ_COILS = 1
READ_DISCRETE_INPUTS = 2
READ_HOLDING_REGISTERS = 3
READ_INPUT_REGISTERS = 4
WRITE_MULTIPLE_COILS = 15
WRITE_MULTIPLE_REGISTERS = 16
SLAVE_DEVICE_FAILURE = 4


class ModbusError(Exception):
    def __init__(self, exception_code):
        super().__init__("Modbus exception %s" % exception_code)
        self._exception_code = exception_code

    def get_exception_code(self):
        return self._exception_code


class TcpMaster(object):
    def __init__(self, host="127.0.0.1", port=502, timeout=1.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._transaction_id = 0

    def set_timeout(self, timeout):
        self.timeout = timeout

    def close(self):
        return None

    def execute(
        self,
        slave,
        function_code,
        starting_address,
        quantity_of_x=None,
        output_value=None,
    ):
        pdu = _request_pdu(function_code, starting_address, quantity_of_x, output_value)
        self._transaction_id = (self._transaction_id + 1) & 0xFFFF
        frame = struct.pack(">HHHB", self._transaction_id, 0, len(pdu) + 1, slave) + pdu
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.host, self.port))
            sock.sendall(frame)
            header = _recv_exact(sock, 7)
            _tid, _pid, length, _unit = struct.unpack(">HHHB", header)
            body = _recv_exact(sock, length - 1)
        finally:
            sock.close()

        if body and body[0] & 0x80:
            code = body[1] if len(body) > 1 else 0
            raise ModbusError(code)
        return _decode_response(function_code, body, quantity_of_x)


def _request_pdu(function_code, address, count, output_value):
    if function_code == READ_COILS:
        request = ReadCoilsRequest(address=address, count=count)
    elif function_code == READ_DISCRETE_INPUTS:
        request = ReadDiscreteInputsRequest(address=address, count=count)
    elif function_code == READ_HOLDING_REGISTERS:
        request = ReadHoldingRegistersRequest(address=address, count=count)
    elif function_code == READ_INPUT_REGISTERS:
        request = ReadInputRegistersRequest(address=address, count=count)
    elif function_code == WRITE_MULTIPLE_COILS:
        request = WriteMultipleCoilsRequest(
            address=address, bits=[bool(value) for value in output_value]
        )
    elif function_code == WRITE_MULTIPLE_REGISTERS:
        values = [int(value) for value in output_value]
        request = WriteMultipleRegistersRequest(
            address=address, count=len(values), registers=values
        )
    else:
        raise ValueError("Unsupported function code %s" % function_code)
    return struct.pack(">B", request.function_code) + request.encode()


def _decode_response(function_code, body, count):
    if function_code in (WRITE_MULTIPLE_COILS, WRITE_MULTIPLE_REGISTERS):
        return body
    if function_code == READ_COILS:
        response = ReadCoilsResponse()
    elif function_code == READ_DISCRETE_INPUTS:
        response = ReadDiscreteInputsResponse()
    elif function_code == READ_HOLDING_REGISTERS:
        response = ReadHoldingRegistersResponse()
    elif function_code == READ_INPUT_REGISTERS:
        response = ReadInputRegistersResponse()
    else:
        return body
    response.decode(body[1:])
    if function_code in (READ_COILS, READ_DISCRETE_INPUTS):
        bits = response.bits
        if count is not None:
            bits = bits[:count]
        return tuple(1 if bit else 0 for bit in bits)
    return tuple(response.registers)


def _recv_exact(sock, count):
    data = b""
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise OSError("short Modbus response")
        data += chunk
    return data
