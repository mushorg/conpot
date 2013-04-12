# Modbus TestKit: Implementation of Modbus protocol in python
# (C)2009 - Luc Jean - luc.jean@gmail.com
# (C)2009 - Apidev - http://www.apidev.fr
# This is distributed under GNU LGPL license, see license.txt

import socket

import modbus_tk
import modbus_tk.defines as cst
import modbus_tk.modbus_tcp as modbus_tcp

import config as conpot_config

if __name__ == "__main__":
    try:
        master = modbus_tcp.TcpMaster(host="localhost", port=conpot_config.port)
        master.set_timeout(1.0)

        #read 8 first bits from discrete output on slave 1
        print master.execute(slave=1, function_code=cst.READ_COILS, starting_address=1, quantity_of_x=8)
        #try to set first 8 bits to 11111111
        master.execute(1, cst.WRITE_MULTIPLE_COILS, 1, output_value=[1, 1, 1, 1, 1, 1, 1, 1])
        #read first 8 bit (check if they have changes...)
        print master.execute(slave=1, function_code=cst.READ_COILS, starting_address=1, quantity_of_x=8)

        #print master.execute(slave=1, function_code=cst.READ_HOLDING_REGISTERS, starting_address=0, quantity_of_x=2)
        #print master.execute(slave=5, function_code=cst.READ_COILS, starting_address=0, quantity_of_x=2)
        #logger.info(master.execute(1, cst.READ_DISCRETE_INPUTS, 0, 8))
        #logger.info(master.execute(1, cst.READ_INPUT_REGISTERS, 100, 3))
        #logger.info(master.execute(1, cst.READ_HOLDING_REGISTERS, 100, 12))
        #logger.info(master.execute(1, cst.WRITE_SINGLE_COIL, 7, output_value=1))
        #logger.info(master.execute(1, cst.WRITE_SINGLE_REGISTER, 100, output_value=54))
        #logger.info(master.execute(1, cst.WRITE_MULTIPLE_COILS, 0, output_value=[1, 1, 0, 1, 1, 0, 1, 1]))
        #logger.info(master.execute(1, cst.WRITE_MULTIPLE_REGISTERS, 100, output_value=xrange(12)))

    except modbus_tk.modbus.ModbusError, e:
        print 'Caught exception code: {0}'.format(e.get_exception_code())
    except socket.timeout:
        print "Timeout"
