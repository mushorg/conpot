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


logger = logging.getLogger(__name__)


# Simulates power usage for a Kamstrup 382 meter
class UsageSimulator(object):
    def __init__(self, *args):
        # TODO:
        #   1. Get initial measure values from databus static values
        #   2. Overwrite databus key and reference this class
        #   3. Somehow simulate different environment, time of day, size of facility/house, number of teenagers..
        pass