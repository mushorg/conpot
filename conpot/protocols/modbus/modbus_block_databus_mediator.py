import conpot.core as conpot_core


class DatabusBlock(object):
    """A Modbus address range whose values live in the Conpot databus.

    Addresses are wire addresses. Unlike pymodbus ``ModbusDeviceContext``,
    nothing here adds one before the lookup.
    """

    def __init__(self, databus_key, starting_address, size):
        self.starting_address = starting_address
        self.databus_key = databus_key
        # The template's size is authoritative: it is what the block claims to
        # serve. A databus list of a different length would silently widen or
        # shrink the address range (and crash on reads past its end).
        length = len(conpot_core.get_databus().get_value(self.databus_key))
        if length != size:
            raise ValueError(
                "Modbus block %s has size %d but its databus value holds %d "
                "entries" % (databus_key, size, length)
            )
        self.size = size

    def is_in(self, starting_address, size):
        """Return True if a block at this address and size would overlap."""
        if starting_address > self.starting_address:
            return (self.starting_address + self.size) > starting_address
        elif starting_address < self.starting_address:
            return (starting_address + size) > self.starting_address
        return True

    def get_values(self, offset, count):
        values = conpot_core.get_databus().get_value(self.databus_key)
        return list(values[offset : offset + count])

    def set_values(self, offset, values):
        # Mutate the databus list in place. The PLC scan cycle reads the same
        # object; replacing it would detach that reader. Coils stay ints.
        stored = conpot_core.get_databus().get_value(self.databus_key)
        for index, value in enumerate(values):
            if isinstance(value, bool):
                stored[offset + index] = 1 if value else 0
            else:
                stored[offset + index] = value
