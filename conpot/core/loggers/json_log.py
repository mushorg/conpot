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
    def __init__(self, filename, sensorid=None, public_ip=None):
        self.fileHandle = open(filename, "a")
        # sensorid/public_ip kept for backward-compatible constructor callers;
        # v1 events carry these fields from LogWorker.
        self.sensorid = sensorid
        self.public_ip = public_ip

    def log(self, event):
        # Prefer fields already on the event; fall back to constructor values.
        if event.get("sensorid") is None and self.sensorid is not None:
            event = dict(event)
            event["sensorid"] = self.sensorid
        if event.get("public_ip") is None and self.public_ip is not None:
            event = dict(event)
            event["public_ip"] = self.public_ip

        json.dump(event, self.fileHandle, default=json_default)
        self.fileHandle.write("\n")
        self.fileHandle.flush()
