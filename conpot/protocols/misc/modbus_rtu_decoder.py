# Decoder for Modbus RTU

import logging
from struct import unpack
from modbus_tk import utils


class ModbusRtuDecoder:
    def __init__(self):
        pass

    @staticmethod
    def validate_crc(message):
        """Check whether the packet received is valid"""
        if len(message) < 3:
            return False
        else:
            (crc,) = unpack('>H', message[-2:])
            return crc == utils.calculate_crc(message[:-2])

    @classmethod
    def decode(cls, data):
        """Decode the contents of the packet"""
        assert cls.validate_crc(data), 'Not a valid Modbus RTU packet'
        logging.debug('Decoding message: {0}'.format(data))
        message = {}
        (message['Slave ID'], ) = unpack('>B', data[0])
        pdu = data[1:-2]
        if len(pdu) > 1:
            (message['Function Code'], ) = unpack('>B', data[1])
            message['Data'] = unpack('>' + ('B' * len(data[2:-2])), data[2:-2])
        (message['CRC'], ) = unpack('>H', data[-2:])
        return message


# for debugging:
if __name__ == '__main__':
    test_data = b'\x01\x02\x00\x00\x00\x01\xb9\xca'
    assert ModbusRtuDecoder.validate_crc(test_data)
    print(ModbusRtuDecoder.decode(test_data))