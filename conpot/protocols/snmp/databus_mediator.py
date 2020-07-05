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

# this class mediates between the SNMP attack surface and conpots databus
# furthermore it keeps request statistics iot evade being used as a DOS
# reflection tool

from pysnmp.smi import builder
from datetime import datetime
import conpot.core as conpot_core


class DatabusMediator(object):
    def __init__(self, oid_mappings):
        """ initiate variables """

        self.evasion_table = {}  # stores the number of requests
        self.start_time = datetime.now()
        self.oid_map = oid_mappings  # mapping between OIDs and databus keys
        self.databus = conpot_core.get_databus()

    def get_response(self, reference_class, OID):
        if OID in self.oid_map:
            if reference_class == "DisplayString":
                (response_class,) = builder.MibBuilder().importSymbols(
                    "SNMPv2-TC", "DisplayString"
                )

            elif reference_class == "OctetString":
                (response_class,) = builder.MibBuilder().importSymbols(
                    "ASN1", "OctetString"
                )

            elif reference_class == "Integer32":
                (response_class,) = builder.MibBuilder().importSymbols(
                    "SNMPv2-SMI", "Integer32"
                )

            elif reference_class == "Counter32":
                (response_class,) = builder.MibBuilder().importSymbols(
                    "SNMPv2-SMI", "Counter32"
                )

            elif reference_class == "Gauge32":
                (response_class,) = builder.MibBuilder().importSymbols(
                    "SNMPv2-SMI", "Gauge32"
                )

            elif reference_class == "TimeTicks":
                (response_class,) = builder.MibBuilder().importSymbols(
                    "SNMPv2-SMI", "TimeTicks"
                )
            # TODO: All mode classes - or autodetect'ish?
            else:
                # dynamic responses are not supported for this class (yet)
                return False
            response_value = self.databus.get_value(self.oid_map[OID])
            return response_class(response_value)
        else:
            return None

    def set_value(self, OID, value):
        # TODO: Access control. The profile shold indicate which OIDs are writable
        self.databus.set_value(self.oid_map[OID], value)

    def update_evasion_table(self, client_ip):
        """ updates dynamic evasion table """

        # get current minute as epoch..
        now = datetime.now()
        epoch_minute = int(
            (
                datetime(now.year, now.month, now.day, now.hour, now.minute)
                - datetime(1970, 1, 1)
            ).total_seconds()
        )

        # if this is a new minute, re-initialize the evasion table
        if epoch_minute not in self.evasion_table:
            self.evasion_table.clear()  # purge previous entries
            self.evasion_table[epoch_minute] = {}  # create current minute
            self.evasion_table[epoch_minute][
                "overall"
            ] = 0  # prepare overall request count

        # if this is a new client, add him to the evasion table
        if client_ip[0] not in self.evasion_table[epoch_minute]:
            self.evasion_table[epoch_minute][client_ip[0]] = 0

        # increment number of requests..
        self.evasion_table[epoch_minute][client_ip[0]] += 1
        self.evasion_table[epoch_minute]["overall"] += 1

        current_numreq = self.evasion_table[epoch_minute][client_ip[0]]
        overall_numreq = self.evasion_table[epoch_minute]["overall"]

        # return numreq(per_ip) and numreq(overall)
        return current_numreq, overall_numreq
