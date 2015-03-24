# Copyright (C) 2014 Johnny Vestergaard <jkv@unixcluster.dk>
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

import logging
import uuid

from datetime import datetime

logger = logging.getLogger(__name__)


# one instance per connection
class AttackSession(object):
    def __init__(self, protocol, source_ip, source_port, databus, log_queue):
        self.log_queue = log_queue
        self.id = uuid.uuid4()
        logger.info('New {0} session from {1} ({2})'.format(protocol, source_ip, self.id))
        self.protocol = protocol
        self.source_ip = source_ip
        self.source_port = source_port
        self.timestamp = datetime.utcnow()
        self.databus = databus
        self.public_ip = None
        self.data = dict()
        self._ended = False

    def _dump_event(self, event_data):
        data = {
            "id": self.id,
            "remote": (self.source_ip, self.source_port),
            "data_type": self.protocol,
            "timestamp": self.timestamp,
            "public_ip": self.public_ip,
            "data": event_data
        }
        return data

    def add_event(self, event_data):
        sec_elapsed = (datetime.utcnow() - self.timestamp).total_seconds()
        elapse_ms = int(sec_elapsed * 1000)
        while elapse_ms in self.data:
            elapse_ms += 1
        self.data[elapse_ms] = event_data
        # TODO: We should only log the session when it is finished
        self.log_queue.put(self._dump_event(event_data))

    def dump(self):
        data = {
            "id": self.id,
            "remote": (self.source_ip, self.source_port),
            "data_type": self.protocol,
            "timestamp": self.timestamp,
            "public_ip": self.public_ip,
            "data": self.data
        }
        return data

    def set_ended(self):
        self._ended = True
