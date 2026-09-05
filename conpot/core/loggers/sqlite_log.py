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


import sqlite3
import pwd
import os
import platform
import grp


class SQLiteLogger(object):
    def _chown_db(self, path, uid_name="nobody", gid_name="nogroup"):
        path = path.rpartition("/")[0]
        if not os.path.isdir(path):
            os.mkdir(path)
        # TODO: Have this in a central place
        wanted_uid = pwd.getpwnam(uid_name)[2]
        # special handling for os x. (getgrname has trouble with gid below 0)
        if platform.mac_ver()[0]:
            wanted_gid = -2
        else:
            wanted_gid = grp.getgrnam(gid_name)[2]
        os.chown(path, wanted_uid, wanted_gid)

    def __init__(self, db_path="logs/conpot.db"):
        self._chown_db(db_path)
        self.conn = sqlite3.connect(db_path)
        self._create_db()

    def _create_db(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS events
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                remote TEXT,
                protocol TEXT,
                request TEXT,
                response TEXT
            )"""
        )

    def log(self, event):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO events(session, remote, protocol, request, response) VALUES (?, ?, ?, ?, ?)",
            (
                str(event["id"]),
                str(event["remote"]),
                event["data_type"],
                str(event["data"].get("request")),
                str(event["data"].get("response")),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid
