# Copyright (C) 2013  Daniel creo Haslinger <creo-conpot@blackmesa.at>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

# conpot_dynrsp.py
#     keeps track of values loaded into active MIBs and updates
#     them for a more dynamic look and feel of conpots SNMP interface
  

from pysnmp.smi import builder 
from datetime import datetime
import random

def init():
    global response_table
    response_table = {}

    global start_time
    start_time = datetime.now()

def updateDynamicValues(reference_class, OID, reset_value):
    """ updates dynamic values in global table """

    global response_table
    global start_time

    if OID in response_table:

        dynamic_type = response_table[OID][0]		# what should be done?
        dynamic_aux = response_table[OID][1]		# axiliary data needed for manipulation
        dynamic_value = response_table[OID][2]		# current value to be manipulated

        # determine the correct response class. response classes not
        # handled here do not support dynamic responses (yet)

        if reference_class == 'DisplayString':

            (response_class,) = builder.MibBuilder().importSymbols("SNMPv2-TC", "DisplayString")


        elif reference_class == 'OctetString':

            (response_class,) = builder.MibBuilder().importSymbols("ASN1", "OctetString")


        elif reference_class == 'Integer32':

            (response_class,) = builder.MibBuilder().importSymbols("SNMPv2-SMI", "Integer32")


        elif reference_class == 'Counter32':

            (response_class,) = builder.MibBuilder().importSymbols("SNMPv2-SMI", "Counter32")


        elif reference_class == 'Gauge32':

            (response_class,) = builder.MibBuilder().importSymbols("SNMPv2-SMI", "Gauge32")


        elif reference_class == 'TimeTicks':

            (response_class,) = builder.MibBuilder().importSymbols("SNMPv2-SMI", "TimeTicks")

        else:

            # this reference class is not supported (yet)

            return False



        # determine the type of modification to be applied.

        if dynamic_type == 'static':

            # nothing should be done

            return False


        elif dynamic_type == 'increment':

            # increment current value by AUX and resets when it reaches the cap ( default = 1:2147483647 )

            if not dynamic_aux:     dynamic_aux = '1:2147483647'
            dynamic_aux = dynamic_aux.split(':')
            response_table[OID][2] = int(dynamic_value) + int(dynamic_aux[0])
            if(int(response_table[OID][2]) > int(dynamic_aux[1])):	response_table[OID][2] = reset_value
            return response_class


        elif dynamic_type == 'randominc':

            # increment current value by random integer between AUX(min:max) and reset
            # when it reaches the cap ( default 1:65535:2147418112)

            if not dynamic_aux:     dynamic_aux = '1:65535:2147418112'
            dynamic_aux = dynamic_aux.split(':')
            response_table[OID][2] = int(dynamic_value) + random.randrange(int(dynamic_aux[0]),int(dynamic_aux[1]))
            if(int(response_table[OID][2]) > int(dynamic_aux[2])):	response_table[OID][2] = reset_value
            return response_class


        elif dynamic_type == 'decrement':

            # decrement current value by AUX and reset when it reaches the cap ( default = 1:-2147483648 )

            if not dynamic_aux:     dynamic_aux = '1:-2147483648'
            dynamic_aux = dynamic_aux.split(':')
            response_table[OID][2] = int(dynamic_value) - int(dynamic_aux[0])
            if(int(response_table[OID][2] < int(dynamic_aux[1]))):	response_table[OID][2] = reset_value
            return response_class


        elif dynamic_type == 'randomdec':

            # decrement current value by random integer between AUX(min:max) and reset when
            # it reaches the cap ( default = 1:65535:-2147418113 )

            if not dynamic_aux:     dynamic_aux = '1:65535:-2147418113'
            dynamic_aux = dynamic_aux.split(':')
            response_table[OID][2] = int(dynamic_value) - random.randrange(int(dynamic_aux[0]),int(dynamic_aux[1]))
            if(int(response_table[OID][2]) < int(dynamic_aux[2])):	response_table[OID][2] = reset_value
            return response_class


        elif dynamic_type == 'randomint':

            # set value to random integer between AUX(min:max) ( default = 1:65535 )

            if not dynamic_aux:     dynamic_aux = "1:65535"
            dynamic_aux = dynamic_aux.split(':')
            response_table[OID][2] = random.randrange(int(dynamic_aux[0]),int(dynamic_aux[1]))
            return response_class


        elif dynamic_type == 'sysuptime':

            # set value to the current uptime of the conpot snmp process in milliseconds

            uptime_delta = datetime.now() - start_time
            response_table[OID][2] = round((uptime_delta.days * 24 * 60 * 60 + uptime_delta.seconds) * 100 + uptime_delta.microseconds / 10000)
            return response_class


        elif dynamic_type == 'evaluate':

            # set value to result of evaluated AUX ( default = do not modify value )

            if not dynamic_aux:     return False
            response_table[OID][2] = eval(dynamic_aux)
            return response_class


        else:

            # not sure how we got here, but consider the
            # type to be static.

            return False


    else:

        # this OID is not registered.

        return False

