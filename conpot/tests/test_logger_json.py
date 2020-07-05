# Copyright (C) 2016 MushMush Foundation
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

from os import path
from datetime import datetime

import unittest
import tempfile
import shutil
import json

from conpot.core.loggers.json_log import JsonLogger


class TestJsonLogger(unittest.TestCase):
    def setUp(self):
        self.logging_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.logging_dir)

    def test_log_event(self):
        filename = path.join(self.logging_dir, "test.json")
        sensorid = "default"
        public_ip = "0.0.0.0"
        dst_port = 502
        timestamp = datetime.now()
        event_id = 1337
        src_ip = "127.0.0.1"
        src_port = "2048"
        data_type = "unittest"
        request = "ping"
        response = "pong"

        json_logger = JsonLogger(filename, sensorid, public_ip)
        json_logger.log(
            {
                "timestamp": timestamp,
                "id": event_id,
                "remote": (src_ip, src_port),
                "local": (public_ip, dst_port),
                "data_type": data_type,
                "data": {"request": request, "response": response},
            }
        )

        with open(filename, "r") as logfile:
            e = json.load(logfile)
            self.assertEqual(e["timestamp"], timestamp.isoformat())
            self.assertEqual(e["sensorid"], sensorid)
            self.assertEqual(e["id"], event_id)
            self.assertEqual(e["src_ip"], src_ip)
            self.assertEqual(e["src_port"], src_port)
            self.assertEqual(e["dst_ip"], public_ip)
            self.assertEqual(e["dst_port"], dst_port)
            self.assertEqual(e["data_type"], data_type)
            self.assertEqual(e["request"], request)
            self.assertEqual(e["response"], response)
            self.assertEqual(e["event_type"], None)
