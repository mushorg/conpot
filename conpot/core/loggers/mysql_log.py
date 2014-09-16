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

    def __init__(self):

        self.conn = sqlite3.connect(db_path)
        self._create_db()

    def _create_db(self):
        cursor = self.conn.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS events
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                remote TEXT,
                protocol TEXT,
                request TEXT,
                response TEXT
            )""")

    def log(self, event):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO events(session, remote, protocol, request, response) VALUES (?, ?, ?, ?, ?)",
                       (str(event["id"]), str(event["remote"]), event['data_type'],
                        event["data"].get('request'), event["data"].get('response'))
        )
        self.conn.commit()
        return cursor.lastrowid

    def log_session(self, session):
        pass

    def select_data(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM events")
        print cursor.fetchall()
