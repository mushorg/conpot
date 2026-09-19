import logging
import struct

from pymodbus.constants import ExcCodes
from pymodbus.pdu import DecodePDU, ExceptionResponse
from pymodbus.pdu.bit_message import (
    ReadCoilsRequest,
    ReadCoilsResponse,
    ReadDiscreteInputsRequest,
    ReadDiscreteInputsResponse,
    WriteMultipleCoilsRequest,
    WriteMultipleCoilsResponse,
    WriteSingleCoilRequest,
    WriteSingleCoilResponse,
)
from pymodbus.pdu.register_message import (
    ReadHoldingRegistersRequest,
    ReadHoldingRegistersResponse,
    ReadInputRegistersRequest,
    ReadInputRegistersResponse,
    WriteMultipleRegistersRequest,
    WriteMultipleRegistersResponse,
    WriteSingleRegisterRequest,
    WriteSingleRegisterResponse,
)

from conpot.utils.networking import str_to_bytes

from .modbus_block_databus_mediator import DatabusBlock

logger = logging.getLogger(__name__)

# Template <type> names. Values are the Modbus function codes modbus_tk used
# as block-type keys, which is also how requests address these tables.
BLOCK_TYPES = {
    "COILS": ReadCoilsRequest.function_code,
    "DISCRETE_INPUTS": ReadDiscreteInputsRequest.function_code,
    "HOLDING_REGISTERS": ReadHoldingRegistersRequest.function_code,
    "ANALOG_INPUTS": ReadInputRegistersRequest.function_code,
}

_READ_BIT_LIMIT = 2000
_READ_REGISTER_LIMIT = 125
_WRITE_COIL_LIMIT = 1968
_WRITE_REGISTER_LIMIT = 123

_BROADCAST_FUNCTIONS = (
    WriteSingleCoilRequest.function_code,
    WriteSingleRegisterRequest.function_code,
    WriteMultipleCoilsRequest.function_code,
    WriteMultipleRegistersRequest.function_code,
)

# Importing the message modules registers their PDUs on DecodePDU.
_DECODER = DecodePDU(True)


class ModbusInvalidRequestError(Exception):
    """A PDU that cannot be turned into an exception response."""


class MBSlave(object):
    """One Modbus unit id: template blocks plus pymodbus encode/decode."""

    def __init__(self, slave_id, dom):
        self._id = slave_id
        self.dom = dom
        self.function_code = None
        self._blocks = {}
        self._memory = {block_type: [] for block_type in BLOCK_TYPES.values()}
        logger.debug("Modbus slave (ID: %d) created", self._id)

    def add_block(self, block_name, block_type, starting_address, size):
        if size <= 0:
            raise ValueError("size must be a positive number")
        if starting_address < 0:
            raise ValueError("starting address must be zero or positive number")
        if block_name in self._blocks:
            raise ValueError("Block %s already exists." % block_name)
        if block_type not in self._memory:
            raise ValueError("Invalid block type %s" % block_type)

        index = len(self._memory[block_type])
        for i, block in enumerate(self._memory[block_type]):
            if block.is_in(starting_address, size):
                raise ValueError(
                    "Overlap block at %d size %d" % (block.starting_address, block.size)
                )
            if block.starting_address > starting_address:
                index = i
                break

        self._blocks[block_name] = (block_type, starting_address)
        self._memory[block_type].insert(
            index, DatabusBlock(block_name, starting_address)
        )

    def handle_request(self, request_pdu, broadcast=False):
        """Return a response PDU, or None when a broadcast must stay silent."""
        logger.debug("Slave (ID: %d) is handling request", self._id)
        if not request_pdu:
            raise ModbusInvalidRequestError("Request PDU is empty")

        self.function_code = request_pdu[0]
        if broadcast and self.function_code not in _BROADCAST_FUNCTIONS:
            raise ModbusInvalidRequestError(
                "Function %d can not be broadcasted" % self.function_code
            )

        if self.function_code == 0x11:
            response = self._report_slave_id()
        elif self.function_code == 0x2B:
            response = self._device_info(request_pdu)
        else:
            response = self._handle_standard(request_pdu)

        if broadcast:
            logger.info("Modbus broadcast on slave %s", self._id)
            return None
        return response

    def _handle_standard(self, request_pdu):
        try:
            pdu = _DECODER.decode(request_pdu)
        except struct.error:
            return _exception_pdu(self.function_code, ExcCodes.ILLEGAL_VALUE)
        if pdu is None:
            return _exception_pdu(self.function_code, ExcCodes.ILLEGAL_FUNCTION)

        if isinstance(pdu, (ReadCoilsRequest, ReadDiscreteInputsRequest)):
            return self._read_bits(pdu)
        if isinstance(pdu, (ReadHoldingRegistersRequest, ReadInputRegistersRequest)):
            return self._read_registers(pdu)
        if isinstance(pdu, WriteSingleCoilRequest):
            return self._write_single_coil(pdu, request_pdu)
        if isinstance(pdu, WriteSingleRegisterRequest):
            return self._write_single_register(pdu)
        if isinstance(pdu, WriteMultipleCoilsRequest):
            return self._write_multiple_coils(pdu, request_pdu)
        if isinstance(pdu, WriteMultipleRegistersRequest):
            return self._write_multiple_registers(pdu)
        return _exception_pdu(self.function_code, ExcCodes.ILLEGAL_FUNCTION)

    def _read_bits(self, pdu):
        if pdu.count <= 0 or pdu.count > _READ_BIT_LIMIT:
            return _exception_pdu(pdu.function_code, ExcCodes.ILLEGAL_VALUE)
        found = self._block_and_offset(pdu.function_code, pdu.address, pdu.count)
        if found is None:
            return _exception_pdu(pdu.function_code, ExcCodes.ILLEGAL_ADDRESS)
        block, offset = found
        values = block.get_values(offset, pdu.count)
        if pdu.function_code == ReadCoilsRequest.function_code:
            response = ReadCoilsResponse(bits=values)
        else:
            response = ReadDiscreteInputsResponse(bits=values)
        return _success_pdu(response)

    def _read_registers(self, pdu):
        if pdu.count <= 0 or pdu.count > _READ_REGISTER_LIMIT:
            return _exception_pdu(pdu.function_code, ExcCodes.ILLEGAL_VALUE)
        found = self._block_and_offset(pdu.function_code, pdu.address, pdu.count)
        if found is None:
            return _exception_pdu(pdu.function_code, ExcCodes.ILLEGAL_ADDRESS)
        block, offset = found
        values = [int(value) for value in block.get_values(offset, pdu.count)]
        if pdu.function_code == ReadHoldingRegistersRequest.function_code:
            response = ReadHoldingRegistersResponse(registers=values)
        else:
            response = ReadInputRegistersResponse(registers=values)
        return _success_pdu(response)

    def _write_single_coil(self, pdu, request_pdu):
        try:
            _address, raw_value = struct.unpack(">HH", request_pdu[1:5])
        except struct.error:
            return _exception_pdu(pdu.function_code, ExcCodes.ILLEGAL_VALUE)
        if raw_value == 0:
            stored = 0
        elif raw_value == 0xFF00:
            stored = 1
        else:
            return _exception_pdu(pdu.function_code, ExcCodes.ILLEGAL_VALUE)
        found = self._block_and_offset(BLOCK_TYPES["COILS"], pdu.address, 1)
        if found is None:
            return _exception_pdu(pdu.function_code, ExcCodes.ILLEGAL_ADDRESS)
        block, offset = found
        block.set_values(offset, [stored])
        response = WriteSingleCoilResponse(address=pdu.address, bits=[bool(stored)])
        return _success_pdu(response)

    def _write_single_register(self, pdu):
        if not pdu.registers:
            return _exception_pdu(pdu.function_code, ExcCodes.ILLEGAL_VALUE)
        found = self._block_and_offset(BLOCK_TYPES["HOLDING_REGISTERS"], pdu.address, 1)
        if found is None:
            return _exception_pdu(pdu.function_code, ExcCodes.ILLEGAL_ADDRESS)
        block, offset = found
        block.set_values(offset, [int(pdu.registers[0])])
        response = WriteSingleRegisterResponse(
            address=pdu.address, registers=[int(pdu.registers[0])]
        )
        return _success_pdu(response)

    def _write_multiple_coils(self, pdu, request_pdu):
        try:
            _address, count, byte_count = struct.unpack(">HHB", request_pdu[1:6])
        except struct.error:
            return _exception_pdu(pdu.function_code, ExcCodes.ILLEGAL_VALUE)
        expected = count // 8
        if count % 8:
            expected += 1
        if count <= 0 or count > _WRITE_COIL_LIMIT or byte_count != expected:
            return _exception_pdu(pdu.function_code, ExcCodes.ILLEGAL_VALUE)
        found = self._block_and_offset(BLOCK_TYPES["COILS"], pdu.address, count)
        if found is None:
            return _exception_pdu(pdu.function_code, ExcCodes.ILLEGAL_ADDRESS)
        block, offset = found
        block.set_values(offset, list(pdu.bits))
        response = WriteMultipleCoilsResponse(address=pdu.address, count=count)
        return _success_pdu(response)

    def _write_multiple_registers(self, pdu):
        if (
            pdu.count <= 0
            or pdu.count > _WRITE_REGISTER_LIMIT
            or len(pdu.registers) != pdu.count
        ):
            return _exception_pdu(pdu.function_code, ExcCodes.ILLEGAL_VALUE)
        found = self._block_and_offset(
            BLOCK_TYPES["HOLDING_REGISTERS"], pdu.address, pdu.count
        )
        if found is None:
            return _exception_pdu(pdu.function_code, ExcCodes.ILLEGAL_ADDRESS)
        block, offset = found
        block.set_values(offset, [int(value) for value in pdu.registers])
        response = WriteMultipleRegistersResponse(address=pdu.address, count=pdu.count)
        return _success_pdu(response)

    def _block_and_offset(self, block_type, address, length):
        for block in self._memory[block_type]:
            if address >= block.starting_address:
                offset = address - block.starting_address
                if block.size >= offset + length:
                    return block, offset
        return None

    def _report_slave_id(self):
        # Historical Conpot PDU: function code is present twice. Scanners and
        # test_report_slave_id lock this layout; pymodbus ReportDeviceIdResponse
        # encodes a different one.
        logger.debug("Requested to report slave ID (0x11)")
        return bytes((0x11, 0x11, 0x01, 0x01, 0xFF))

    def _device_info(self, request_pdu):
        # Always return all three objects. The stock MEI handler would return
        # only the requested object id; the default template test asks for
        # object 2 and still expects VendorName and ProductCode in the body.
        try:
            info_root = self.dom.xpath("//modbus/device_info")[0]
            vendor_name = info_root.xpath("./VendorName/text()")[0]
            product_code = info_root.xpath("./ProductCode/text()")[0]
            major_minor_revision = info_root.xpath("./MajorMinorRevision/text()")[0]
            _req_device_id, _object_id = struct.unpack(">BB", request_pdu[2:4])
        except struct.error, IndexError:
            return _exception_pdu(0x2B, ExcCodes.ILLEGAL_VALUE)

        device_info = {0: vendor_name, 1: product_code, 2: major_minor_revision}
        response = struct.pack(">B", 0x2B)
        response += struct.pack(">B", 0x0E)
        response += struct.pack(">B", _req_device_id)
        response += struct.pack(">B", 0x01)
        response += struct.pack(">B", 0x00)
        response += struct.pack(">B", 0x00)
        response += struct.pack(">B", len(device_info))
        for object_id in range(len(device_info)):
            response += struct.pack(">B", object_id)
            response += struct.pack(">B", len(device_info[object_id]))
            response += str_to_bytes(device_info[object_id])
        return response


def _exception_pdu(function_code, code):
    pdu = ExceptionResponse(function_code, int(code))
    return struct.pack(">B", pdu.function_code) + pdu.encode()


def _success_pdu(pdu):
    return struct.pack(">B", pdu.function_code) + pdu.encode()
