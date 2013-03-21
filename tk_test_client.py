# Modbus TestKit: Implementation of Modbus protocol in python
# (C)2009 - Luc Jean - luc.jean@gmail.com
# (C)2009 - Apidev - http://www.apidev.fr
# This is distributed under GNU LGPL license, see license.txt

import modbus_tk
import modbus_tk.defines as cst
import modbus_tk.modbus_tcp as modbus_tcp

logger = modbus_tk.utils.create_logger("console")

if __name__ == "__main__":
    try:
        #Connect to the slave
        master = modbus_tcp.TcpMaster()
        master.set_timeout(5.0)
        logger.info("connected")

        logger.info(master.execute(5, cst.READ_HOLDING_REGISTERS, 0, 3))

        #send some queries
        logger.info(master.execute(5, cst.READ_COILS, 0, 10))
        #logger.info(master.execute(1, cst.READ_DISCRETE_INPUTS, 0, 8))
        #logger.info(master.execute(1, cst.READ_INPUT_REGISTERS, 100, 3))
        #logger.info(master.execute(1, cst.READ_HOLDING_REGISTERS, 100, 12))
        #logger.info(master.execute(1, cst.WRITE_SINGLE_COIL, 7, output_value=1))
        #logger.info(master.execute(1, cst.WRITE_SINGLE_REGISTER, 100, output_value=54))
        #logger.info(master.execute(1, cst.WRITE_MULTIPLE_COILS, 0, output_value=[1, 1, 0, 1, 1, 0, 1, 1]))
        #logger.info(master.execute(1, cst.WRITE_MULTIPLE_REGISTERS, 100, output_value=xrange(12)))

    except modbus_tk.modbus.ModbusError, e:
        logger.error("%s- Code=%d" % (e, e.get_exception_code()))