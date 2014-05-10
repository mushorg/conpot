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


class Proxy(object):
    def __init__(self, host, port, proxy_host, proxy_port, decoder=None):
        self.host = host
        self.port = port
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.decoder = None
        self.own_socket = None
        self.proxy_socket = None

    def start(self):
        # 1. Open and listen on IN/OUT socket
        # 2. On data from host add to decoder and relay
        # 3. On data from proxy_host add to decoder and relay

    def data_from_own(self, data):
        self.decoder.add_adversary_data(data)
        self.proxy_socket.send(data)

    def data_from_proxy(self, data):
        self.decoder.add_proxy_data(data)
        self.own_socket.send(data)
