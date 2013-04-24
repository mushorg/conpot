# Copyright (C) 2013  Lukas Rist <glaslos@gmail.com>
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


import hpfeeds
import config


class HPFriendsLogger(object):

    def __init__(self):
        try:
            self.hpc = hpfeeds.new(config.hpfriends_host, config.hpfriends_port,
                                   config.hpfriends_ident, config.hpfriends_secret)
            self.hpc.connect()
        except Exception as e:
            raise

    def log(self, data):
        for chan in config.hpfriends_channels:
            self.hpc.publish(chan, data)