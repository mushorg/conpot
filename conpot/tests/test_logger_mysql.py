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
    @unittest.skip
    def test_mysqllogger(self):
        """
        Objective: Test if events can be stored to and retrieved from mysql properly.
        """

        # instanciate our mysql logging infrastructure
        host = '127.0.0.1'
        port = 3306
        username = 'travis'
        passphrase = ''
        db = 'conpot_unittest'
        logdevice = ''
        logsocket = 'tcp'
        sensorid = 'default'

        mysqllogger = MySQLlogger(host, port, db, username, passphrase, logdevice, logsocket, sensorid)

        # create a test event
        test_event = {}
        test_event['id'] = 1337
        test_event['remote'] = "127.0.0.2"
        test_event['data_type'] = "unittest"
        test_event['data'] = {'request': 'foo', 'response': 'bar'}

        # lets do it, but do not retry in case of failure
        success = mysqllogger.log(test_event, 0)
        self.assertTrue(success, 'Could not log to mysql database')

        # now that we logged something, lets try to retrieve the event again..
        retrieved_event = mysqllogger.select_session_data(test_event['id'])
        self.assertEqual(len(retrieved_event), 1, 'Retrieved wrong number of events (or no event at all)')
