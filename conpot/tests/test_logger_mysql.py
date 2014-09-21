# Copyright (C) 2014  Daniel creo Haslinger <creo-conpot@blackmesa.at>
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

from conpot.core.loggers.mysql_log import MySQLlogger


class Test_MySQLlogger(unittest.TestCase):
    def test_mysqllogger(self):
        """
        Objective: Test if events can be stored to and retrieved from mysql properly.
        """

        host = '127.0.0.1'
        port = 3306
        username = 'travis'
        passphrase = ''
        db = 'conpot'
        logdevice = ''
        logsocket = 'tcp'
        sensorid = 'default'

        mysqllogger = MySQLlogger(host, port, db, username, passphrase, logdevice, logsocket, sensorid)

        test_event = {}
        test_event['id'] = 1337
        test_event['remote'] = "127.0.0.2"
        test_event['data_type'] = "unittest"
        test_event['request'] = "foo"
        test_event['response'] = "bar"

        mysqllogger.log(test_event)


        gevent.sleep(2)
        self.assertIsNone(error_message, 'Unexpected error message: {0}'.format(error_message))
