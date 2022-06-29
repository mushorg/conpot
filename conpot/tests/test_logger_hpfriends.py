# Copyright (C) 2013  Johnny Vestergaard <jkv@unixcluster.dk>
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

import unittest
import gevent

from conpot.core.loggers.hpfriends import HPFriendsLogger


class Test_HPFriends(unittest.TestCase):
    @unittest.skip("disabled until honeycloud up and running again")
    def test_hpfriends(self):
        """
        Objective: Test if data can be published to hpfriends without errors.
        """

        host = "hpfriends.honeycloud.net"
        port = 20000
        ident = "HBmU08rR"
        secret = "XDNNuMGYUuWFaWyi"
        channels = [
            "test.test",
        ]
        hpf = HPFriendsLogger(host, port, ident, secret, channels)
        gevent.sleep(0.5)
        error_message = hpf.log("some some test data")
        gevent.sleep(0.5)
        self.assertIsNone(
            error_message, "Unexpected error message: {0}".format(error_message)
        )
