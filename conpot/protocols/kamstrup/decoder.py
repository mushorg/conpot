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


class Decoder(object):
    def __init__(self):
        self.data_from_adversary = []
        # data from the server that we are relaying for
        self.data_from_server = []

    def add_adversary_data(self, data):
        self.data_from_adversary.extend(data)
        self.trydecode(data, 'from_adv')

    def add_proxy_data(self, data):
        self.data_from_adversary.extend(data)
        self.trydecode(data, 'from_server')

    def trydecode(data):
        pass
        # 1. Tried to decode the data
        # 2. If successfull pop the data and log.
        # 3. If not successfull just return