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


import json
import sqlite3
import pwd
import os
import platform
import grp

from .helpers import json_default


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
        self._migrate_db()

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
                response TEXT,
                event_type TEXT,
                event_json TEXT
            )"""
        )
        self.conn.commit()

    def _migrate_db(self):
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(events)")
        columns = {row[1] for row in cursor.fetchall()}
        if "event_type" not in columns:
            cursor.execute("ALTER TABLE events ADD COLUMN event_type TEXT")
        if "event_json" not in columns:
            cursor.execute("ALTER TABLE events ADD COLUMN event_json TEXT")
        self.conn.commit()

    def log(self, event):
        cursor = self.conn.cursor()
        session_id = event.get("session_id") or event.get("id")
        protocol = event.get("protocol") or event.get("data_type")
        src_ip = event.get("src_ip")
        src_port = event.get("src_port")
        if src_ip is None and "remote" in event:
            src_ip, src_port = event["remote"][0], event["remote"][1]
        remote = "('%s', %s)" % (src_ip, src_port)

        request = event.get("request")
        response = event.get("response")
        if request is None and isinstance(event.get("data"), dict):
            request = event["data"].get("request")
        if response is None and isinstance(event.get("data"), dict):
            response = event["data"].get("response")

        event_type = event.get("event_type")
        if event_type is None and isinstance(event.get("data"), dict):
            event_type = event["data"].get("type")

        cursor.execute(
            "INSERT INTO events(session, remote, protocol, request, response, event_type, event_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(session_id),
                remote,
                protocol,
                str(request) if request is not None else None,
                str(response) if response is not None else None,
                event_type,
                json.dumps(event, default=json_default),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid
