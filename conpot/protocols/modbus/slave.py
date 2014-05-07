import struct
import logging

from modbus_tk.modbus import Slave, ModbusError, ModbusInvalidRequestError, InvalidArgumentError, DuplicatedKeyError,\
                             InvalidModbusBlockError, OverlapModbusBlockError
from modbus_tk import defines, utils

from modbus_block_databus_mediator import ModbusBlockDatabusMediator

logger = logging.getLogger(__name__)


class MBSlave(Slave):

    def __init__(self, slave_id, dom):
        Slave.__init__(self, slave_id)
        self._fn_code_map = {defines.READ_COILS: self._read_coils,
                             defines.READ_DISCRETE_INPUTS: self._read_discrete_inputs,
                             defines.READ_INPUT_REGISTERS: self._read_input_registers,
                             defines.READ_HOLDING_REGISTERS: self._read_holding_registers,
                             defines.WRITE_SINGLE_COIL: self._write_single_coil,
                             defines.WRITE_SINGLE_REGISTER: self._write_single_register,
                             defines.WRITE_MULTIPLE_COILS: self._write_multiple_coils,
                             defines.WRITE_MULTIPLE_REGISTERS: self._write_multiple_registers,
                             defines.DEVICE_INFO: self._device_info,
                             }
        self.dom = dom

    def _device_info(self, request_pdu):
        info_root = self.dom.xpath('//conpot_template/protocols/modbus/device_info')[0]
        vendor_name = info_root.xpath('./VendorName/text()')[0]
        product_code = info_root.xpath('./ProductCode/text()')[0]
        major_minor_revision = info_root.xpath('./MajorMinorRevision/text()')[0]

        (req_device_id, req_object_id) = struct.unpack(">BB", request_pdu[2:4])
        device_info = {
            0: vendor_name,
            1: product_code,
            2: major_minor_revision
        }

        # MEI type
        response = struct.pack(">B", 0x0E)
        # requested device id
        response += struct.pack(">B", req_device_id)
        # conformity level
        response += struct.pack(">B", 0x01)
        # followup data 0x00 is False
        response += struct.pack(">B", 0x00)
        # No next object id
        response += struct.pack(">B", 0x00)
        # Number of objects
        response += struct.pack(">B", len(device_info))
        for i in range(len(device_info)):
            # Object id
            response += struct.pack(">B", i)
            # Object length
            response += struct.pack(">B", len(device_info[i]))
            response += device_info[i]
        return response

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

                can_broadcast = [defines.WRITE_MULTIPLE_COILS, defines.WRITE_MULTIPLE_REGISTERS,
                                 defines.WRITE_SINGLE_COIL, defines.WRITE_SINGLE_REGISTER]
                if broadcast and (self.function_code not in can_broadcast):
                    raise ModbusInvalidRequestError("Function %d can not be broadcasted" % self.function_code)

                # execute the corresponding function
                response_pdu = self._fn_code_map[self.function_code](request_pdu)
                if response_pdu:
                    if broadcast:
                        # not really sure whats going on here - better log it!
                        logger.info("broadcast: %s" % (utils.get_log_buffer("!!", response_pdu)))
                        return ""
                    else:
                        return struct.pack(">B", self.function_code) + response_pdu
                raise Exception("No response for function %d" % self.function_code)

            except ModbusError as e:
                logger.error('Exception caught: {0}. (A proper response will be sent to the peer)'.format(e))
                return struct.pack(">BB", self.function_code + 128, e.get_exception_code())

    def add_block(self, block_name, block_type, starting_address, size):
        """Add a new block identified by its name"""
        with self._data_lock: # thread-safe
            if size <= 0:
                raise InvalidArgumentError, "size must be a positive number"
            if starting_address < 0:
                raise InvalidArgumentError, "starting address must be zero or positive number"
            if self._blocks.has_key(block_name):
                raise DuplicatedKeyError, "Block %s already exists. " % (block_name)

            if not self._memory.has_key(block_type):
                raise InvalidModbusBlockError, "Invalid block type %d" % (block_type)

            # check that the new block doesn't overlap an existing block
            # it means that only 1 block per type must correspond to a given address
            # for example: it must not have 2 holding registers at address 100
            index = 0
            for i in xrange(len(self._memory[block_type])):
                block = self._memory[block_type][i]
                if block.is_in(starting_address, size):
                    raise OverlapModbusBlockError, "Overlap block at %d size %d" % (block.starting_address, block.size)
                if block.starting_address > starting_address:
                    index = i
                    break

            # if the block is ok: register it
            self._blocks[block_name] = (block_type, starting_address)
            # add it in the 'per type' shortcut
            self._memory[block_type].insert(index, ModbusBlockDatabusMediator(block_name, starting_address, size))
