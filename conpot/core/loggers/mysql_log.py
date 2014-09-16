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


import MySQLdb


class MySQLlogger(object):

    def __init__(self, host, port, db, username, passphrase, logdevice, logsocket, sensorid):

        self.sensorid = sensorid
        if str(logsocket).lower() == 'tcp':
            self.conn = MySQLdb.connect(host=host, port=port, user=username, passwd=passphrase, db=db)
        elif str(logsocket).lower() == 'dev':
            self.conn = MySQLdb.connect(unix_socket=logdevice, user=username, passwd=passphrase, db=db)

        self._create_db()

    def _create_db(self):
        cursor = self.conn.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS `events` (
                        `id` bigint(20) NOT NULL AUTO_INCREMENT,
                        `sensorid` text NOT NULL,
                        `session` text NOT NULL,
                        `timestamp` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        `remote` text NOT NULL,
                        `protocol` text NOT NULL,
                        `request` text NOT NULL,
                        `response` text NOT NULL,
                        PRIMARY KEY (`id`)
                        ) ENGINE=InnoDB DEFAULT CHARSET=latin1;
                       """)

    def log(self, event):
        cursor = self.conn.cursor()
        cursor.execute("""INSERT INTO
                            events (sensorid, session, remote, protocol, request, response)
                          VALUES
                            (%s, %s, %s, %s, %s, %s)""",
                       (str(self.sensorid),
                        str(event["id"]),
                        str(event["remote"]),
                        event["data_type"],
                        event["data"].get('request'),
                        event["data"].get('response')))

        self.conn.commit()

        return cursor.lastrowid

    def log_session(self, session):
        pass

    def select_data(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM events")
        print cursor.fetchall()
