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

from gevent.queue import Queue

from conpot.core.attack_session import AttackSession
from conpot.core.databus import Databus


# one instance only
class SessionManager(object):
    def __init__(self):
        self._sessions = []
        self._databus = Databus()
        self.log_queue = Queue()

    def _find_sessions(self, protocol, source_ip):
        for session in self._sessions:
            if session.protocol == protocol:
                if session.source_ip == source_ip:
                    return session
        return None

    def get_session(self, protocol, source_ip, source_port):
        # around here we would inject dependencies into the attack session
        attack_session = self._find_sessions(protocol, source_ip)
        if not attack_session:
            attack_session = AttackSession(protocol, source_ip, source_port, self._databus, self.log_queue)
            self._sessions.append(attack_session)
        return attack_session

    def get_session_count(self, protocol):
        count = 0
        for session in self._sessions:
            if session.protocol == protocol:
                count += 1
        return count

    def get_session_count(self):
        return len(self._sessions)

    def purge_sessions(self):
        # there is no native purge/clear mechanism for gevent queues, so...
        self.log_queue = Queue()

    def initialize_databus(self, config_file):
        self._databus.initialize(config_file)
