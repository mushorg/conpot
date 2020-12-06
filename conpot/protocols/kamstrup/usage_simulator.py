# Copyright (C) 2014  Johnny Vestergaard <jkv@unixcluster.dk>
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

import logging

import gevent
import conpot.core as conpot_core


logger = logging.getLogger(__name__)


# Simulates power usage for a Kamstrup 382 meter
class UsageSimulator(object):
    def __init__(self, *args):
        self._enabled = True
        self.stopped = gevent.event.Event()
        # both highres, lowres will be calculated on the fly
        self.energy_in = 0
        self.energy_out = 0
        # p1, p2, p3
        self.voltage = [0, 0, 0]
        self.current = [0, 0, 0]
        self.power = [0, 0, 0]
        gevent.spawn(self.initialize)

    def usage_counter(self):
        while self._enabled:
            # since this is gevent, this actually sleep for _at least_ 1 second
            # TODO: measure last entry and figure it out < jkv: Figure what out?!?
            gevent.sleep(1)
            for x in [0, 1, 2]:
                self.energy_in += int(self.power[x] * 0.0036)
        # ready for shutdown!
        self.stopped.set()

    def stop(self):
        self._enabled = False
        self.stopped.wait()

    def initialize(self):
        # we need the databus initialized before we can probe values
        databus = conpot_core.get_databus()
        databus.initialized.wait()

        # accumulated counter
        energy_in_register = "register_13"
        self.energy_in = databus.get_value(energy_in_register)
        databus.set_value(energy_in_register, self._get_energy_in)
        databus.set_value("register_1", self._get_energy_in_lowres)

        energy_out_register = "register_14"
        self.energy_out = databus.get_value(energy_out_register)
        databus.set_value(energy_out_register, self._get_energy_out)
        databus.set_value("register_2", self._get_energy_out_lowres)

        volt_1_register = "register_1054"
        self.voltage[0] = databus.get_value(volt_1_register)
        databus.set_value(volt_1_register, self._get_voltage_1)

        volt_2_register = "register_1055"
        self.voltage[1] = databus.get_value(volt_2_register)
        databus.set_value(volt_2_register, self._get_voltage_2)

        volt_3_register = "register_1056"
        self.voltage[2] = databus.get_value(volt_3_register)
        databus.set_value(volt_3_register, self._get_voltage_3)

        current_1_register = "register_1076"
        self.current[0] = databus.get_value(current_1_register)
        databus.set_value(current_1_register, self._get_current_1)

        current_2_register = "register_1077"
        self.current[1] = databus.get_value(current_2_register)
        databus.set_value(current_2_register, self._get_current_2)

        current_3_register = "register_1078"
        self.current[2] = databus.get_value(current_3_register)
        databus.set_value(current_3_register, self._get_current_3)

        power_1_register = "register_1080"
        self.power[0] = databus.get_value(power_1_register)
        databus.set_value(power_1_register, self._get_power_1)

        power_2_register = "register_1081"
        self.power[1] = databus.get_value(power_2_register)
        databus.set_value(power_2_register, self._get_power_2)

        power_3_register = "register_1082"
        self.power[2] = databus.get_value(power_3_register)
        databus.set_value(power_3_register, self._get_power_3)

        gevent.spawn(self.usage_counter)

    def _get_energy_in(self):
        return self.energy_in

    def _get_energy_out(self):
        return self.energy_out

    def _get_energy_in_lowres(self):
        return self.energy_in / 1000

    def _get_energy_out_lowres(self):
        return self.energy_out / 1000

    def _get_voltage_1(self):
        return self.voltage[0]

    def _get_voltage_2(self):
        return self.voltage[1]

    def _get_voltage_3(self):
        return self.voltage[2]

    def _get_current_1(self):
        return self.current[0]

    def _get_current_2(self):
        return self.current[1]

    def _get_current_3(self):
        return self.current[2]

    def _get_power_1(self):
        return self.power[0]

    def _get_power_2(self):
        return self.power[1]

    def _get_power_3(self):
        return self.power[2]
