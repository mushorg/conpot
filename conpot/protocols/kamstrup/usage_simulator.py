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
import conpot.core as conpot_core
import gevent


logger = logging.getLogger(__name__)


# Simulates power usage for a Kamstrup 382 meter
class UsageSimulator(object):
    def __init__(self, *args):
        # both highres, lowres will be calculated on the fly
        self.energy_in = 0
        self.energy_out = 0
        # p1, p2, p3
        self.voltage = [0, 0, 0]
        self.current = [0, 0, 0]
        self.power = [0, 0, 0]
        gevent.spawn(self.initialize)

    def initialize(self):
        # we need the databus initialized before we can probe values
        databus = conpot_core.get_databus()
        databus.initialized.wait()

        # accumulated counter
        self.energy_in = databus.get_value("register_13")
        self.energy_out = databus.get_value("register_13")
        # TODO: Overwrite databus values with function in this class

        # the following will serve be the values we diviate around
        self.voltage[0] = databus.get_value("register_1054")
        self.voltage[1] = databus.get_value("register_1055")
        self.voltage[2] = databus.get_value("register_1056")
        self.current[0] = databus.get_value("register_1076")
        self.current[1] = databus.get_value("register_1077")
        self.current[2] = databus.get_value("register_1078")
        self.power[0] = databus.get_value("register_1080")
        self.power[1] = databus.get_value("register_1081")
        self.power[2] = databus.get_value("register_1082")
        # TODO: Overwrite databus values with function in this class
