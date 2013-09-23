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

# dynrsp.py
#     keeps track of values loaded into active MIBs and updates
#     them for a more dynamic look and feel of conpots SNMP interface
  
import random

from pysnmp.smi import builder 
from datetime import datetime


class DynamicResponder(object):
    def __init__(self):
        """ initiate variables """

        self.response_table = {}            # stores dynamic values for OIDs
        self.evasion_table = {}             # stores the number of requests
        self.start_time = datetime.now()

    def update_dynamic_values(self, reference_class, OID, reset_value):
        """ updates dynamic values in table """

        if OID in self.response_table:
    
            dynamic_type = self.response_table[OID][0]		# what should be done?
            dynamic_aux = self.response_table[OID][1]		# axiliary data needed for manipulation
            dynamic_value = self.response_table[OID][2]		# current value to be manipulated
    
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
                # dynamic responses are not supported for this class (yet)
                return False

            # determine the type of modification to be applied.
    
            if dynamic_type == 'static':
                # we're static, no modifications should be done.
                return False
    
            elif dynamic_type == 'increment':
                # increment current value by AUX and resets when it reaches the cap.
                # DEFAULTS: increment by 1, cap at 2147483647.
    
                if not dynamic_aux:
                    dynamic_aux = '1:2147483647'
    
                dynamic_aux = dynamic_aux.split(':')
                self.response_table[OID][2] = int(dynamic_value) + int(dynamic_aux[0])
    
                if int(self.response_table[OID][2]) > int(dynamic_aux[1]):
                    self.response_table[OID][2] = reset_value
    
                return response_class
    
            elif dynamic_type == 'randominc':
    
                # increment current value by random integer between AUX(min:max) and reset
                # when it reaches the cap.
                # DEFAULT: increment by rnd(1,65535), cap at 2147418112.
    
                if not dynamic_aux:
                    dynamic_aux = '1:65535:2147418112'
    
                dynamic_aux = dynamic_aux.split(':')
                self.response_table[OID][2] = int(dynamic_value) + random.randrange(int(dynamic_aux[0]),
                                                                                    int(dynamic_aux[1]))
    
                if int(self.response_table[OID][2]) > int(dynamic_aux[2]):
                    self.response_table[OID][2] = reset_value
    
                return response_class
    
            elif dynamic_type == 'decrement':
    
                # decrement current value by AUX and reset when it reaches the cap.
                # DEFAULT: decrement by 1, cap at -2147483648.
    
                if not dynamic_aux:
                    dynamic_aux = '1:-2147483648'
    
                dynamic_aux = dynamic_aux.split(':')
                self.response_table[OID][2] = int(dynamic_value) - int(dynamic_aux[0])
    
                if int(self.response_table[OID][2] < int(dynamic_aux[1])):
                    self.response_table[OID][2] = reset_value
    
                return response_class
    
            elif dynamic_type == 'randomdec':
    
                # decrement current value by random integer between AUX(min:max) and reset when
                # it reaches the cap.
                # DEFAULT: decrement by rnd(1,65535), cap at -2147418113.
    
                if not dynamic_aux:
                    dynamic_aux = '1:65535:-2147418113'
    
                dynamic_aux = dynamic_aux.split(':')
                self.response_table[OID][2] = int(dynamic_value) - random.randrange(int(dynamic_aux[0]),
                                                                                    int(dynamic_aux[1]))
    
                if int(self.response_table[OID][2]) < int(dynamic_aux[2]):
                    self.response_table[OID][2] = reset_value
    
                return response_class
    
            elif dynamic_type == 'randomint':
    
                # set value to random integer between AUX(min:max).
                # DEFAULT: rnd(1,65535)
    
                if not dynamic_aux:
                    dynamic_aux = "1:65535"
    
                dynamic_aux = dynamic_aux.split(':')
                self.response_table[OID][2] = random.randrange(int(dynamic_aux[0]), int(dynamic_aux[1]))

                return response_class

            elif dynamic_type == 'sysuptime':
    
                # set value to the current uptime of the conpot snmp process in milliseconds.
                # the auxiliary value - if provided - is used as a kickstarter (in milliseconds).
                # DEFAULT: start at 0ms
    
                if not dynamic_aux:
                    dynamic_aux = 0
    
                uptime_delta = datetime.now() - self.start_time
                self.response_table[OID][2] = round((uptime_delta.days * 24 * 60 * 60 + uptime_delta.seconds)
                                                    * 100 + uptime_delta.microseconds / 10000) + int(dynamic_aux)
    
                return response_class
    
            elif dynamic_type == 'evaluate':
    
                # set value to result of evaluated AUX.
                # DEFAULT: do not evaluate, act like you would for "static" types.
    
                if not dynamic_aux:
                    return False
    
                self.response_table[OID][2] = eval(dynamic_aux)
    
                return response_class
    
            else:
                # not sure how we got here, but consider the
                # type to be static.
                return False

        else:
            # this OID is not registered.
            return False

    def update_evasion_table(self, client_ip):
        """ updates dynamic evasion table """

        # get current minute as epoch..
        now = datetime.now()
        epoch_minute = int((datetime(now.year, now.month, now.day, now.hour, now.minute) -
                          datetime(1970, 1, 1)).total_seconds())

        # if this is a new minute, re-initialize the evasion table
        if epoch_minute not in self.evasion_table:
            self.evasion_table.clear()                              # purge previous entries
            self.evasion_table[epoch_minute] = {}                   # create current minute
            self.evasion_table[epoch_minute]['overall'] = 0         # prepare overall request count

        # if this is a new client, add him to the evasion table
        if client_ip[0] not in self.evasion_table[epoch_minute]:
            self.evasion_table[epoch_minute][client_ip[0]] = 0

        # increment number of requests..
        self.evasion_table[epoch_minute][client_ip[0]] += 1
        self.evasion_table[epoch_minute]['overall'] += 1

        current_numreq = self.evasion_table[epoch_minute][client_ip[0]]
        overall_numreq = self.evasion_table[epoch_minute]['overall']

        # return numreq(per_ip) and numreq(overall)
        return current_numreq, overall_numreq
