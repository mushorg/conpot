from modbus_tk.hooks import call_hooks
import conpot.core as conpot_core


class ModbusBlockDatabusMediator(object):
    """This class represents the values for a range of addresses"""

    def __init__(self, databus_key, starting_address):
        """
        Constructor: defines the address range and creates the array of values
        """
        self.starting_address = starting_address
        # self._data = [0]*size
        self.databus_key = databus_key
        self.size = len(conpot_core.get_databus().get_value(self.databus_key))

    def is_in(self, starting_address, size):
        """
        Returns true if a block with the given address and size
        would overlap this block
        """
        if starting_address > self.starting_address:
            return (self.starting_address + self.size) > starting_address
        elif starting_address < self.starting_address:
            return (starting_address + size) > self.starting_address
        return True

    def __getitem__(self, r):
        """"""
        return conpot_core.get_databus().get_value(self.databus_key).__getitem__(r)

    def __setitem__(self, r, v):
        """"""
        call_hooks("modbus.ModbusBlock.setitem", (self, r, v))
        obj = conpot_core.get_databus().get_value(self.databus_key)
        return obj.__setitem__(r, v)
