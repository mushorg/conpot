# Copyright (C) 2015  Danilo Massa
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
from .helpers import json_default


class JsonLogger(object):
    def __init__(self, filename, sensorid, public_ip):
        self.fileHandle = open(filename, "a")
        self.sensorid = sensorid
        self.public_ip = public_ip

    def log(self, event):

        if self.public_ip is not None:
            dst_ip = self.public_ip
        else:
            dst_ip = None
        data = {
            "timestamp": event["timestamp"].isoformat(),
            "sensorid": self.sensorid,
            "id": event["id"],
            "src_ip": event["remote"][0],
            "src_port": event["remote"][1],
            "dst_ip": event["local"][0],
            "dst_port": event["local"][1],
            "public_ip": dst_ip,
            "data_type": event["data_type"],
            "request": event["data"].get("request"),
            "response": event["data"].get("response"),
            "event_type": event["data"].get("type"),
        }

        json.dump(data, self.fileHandle, default=json_default)
        self.fileHandle.write("\n")
        self.fileHandle.flush()
