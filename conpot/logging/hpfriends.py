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
import gevent


class HPFriendsLogger(object):

    def __init__(self, host, port, ident, secret, channels):
        self.channels = channels
        try:
            with gevent.Timeout(2):
                self.hpc = hpfeeds.new(host, port, ident, secret)
        except:
            raise Exception("Connection to HPFriends timed out")

    def log(self, data):
        #hpfeed lib supports passing list of channels
        self.hpc.publish(self.channels, data)
        error_msg = self.hpc.wait()
        return error_msg

