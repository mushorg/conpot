# Copyright (C) 2014 Johnny Vestergaard <jkv@unixcluster.dk>
# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

import asyncio

from conpot.core.attack_session import AttackSession


# one instance only
class SessionManager:
    def __init__(self):
        self._sessions = []
        self.log_queue = asyncio.Queue()
        self._loop = None

    def attach_event_loop(self, loop):
        """Bind the supervisor / test event loop used for thread-safe puts."""
        self._loop = loop

    def _find_sessions(self, protocol, source_ip):
        for session in self._sessions:
            if session.protocol == protocol:
                if session.source_ip == source_ip:
                    return session
        return None

    def get_session(
        self,
        protocol,
        source_ip,
        source_port,
        destination_ip=None,
        destination_port=None,
    ):
        attack_session = self._find_sessions(protocol, source_ip)
        if not attack_session:
            attack_session = AttackSession(
                protocol,
                source_ip,
                source_port,
                destination_ip,
                destination_port,
                self.log_queue,
                self._loop,
            )
            self._sessions.append(attack_session)
        return attack_session

    def delete_session(self, id):
        for i, session in enumerate(self._sessions):
            if session.id == id:
                del self._sessions[i]
                break

    def purge_sessions(self):
        self._sessions = []
        self.log_queue = asyncio.Queue()
