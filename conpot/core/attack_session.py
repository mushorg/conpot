# Copyright (C) 2014 Johnny Vestergaard <jkv@unixcluster.dk>
# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

import asyncio
import logging
import uuid

from datetime import datetime

logger = logging.getLogger(__name__)


class AttackSession(object):
    def __init__(
        self,
        protocol,
        source_ip,
        source_port,
        destination_ip,
        destination_port,
        log_queue,
        loop=None,
    ):
        self.log_queue = log_queue
        self._loop = loop
        self.id = uuid.uuid4()
        logger.info("New %s session from %s (%s)", protocol, source_ip, self.id)
        self.protocol = protocol
        self.source_ip = source_ip
        self.source_port = source_port
        self.destination_ip = destination_ip
        self.destination_port = destination_port
        self.timestamp = datetime.utcnow()
        self.public_ip = None
        self.data = dict()
        self._ended = False

    def _dump_data(self, data):
        return {
            "id": self.id,
            "remote": (self.source_ip, self.source_port),
            "src_ip": self.source_ip,
            "src_port": self.source_port,
            "local": (self.destination_ip, self.destination_port),
            "dst_ip": self.destination_ip,
            "dst_port": self.destination_port,
            "data_type": self.protocol,
            "timestamp": self.timestamp,
            "public_ip": self.public_ip,
            "data": data,
        }

    def add_event(self, event_data):
        now = datetime.utcnow()
        sec_elapsed = (now - self.timestamp).total_seconds()
        elapse_ms = int(sec_elapsed * 1000)
        while elapse_ms in self.data:
            elapse_ms += 1
        self.data[elapse_ms] = event_data
        payload = self._dump_data(event_data)
        self._enqueue(payload)

    def _enqueue(self, payload):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = self._loop
        if loop is not None and loop.is_running():
            try:
                if asyncio.get_running_loop() is loop:
                    self.log_queue.put_nowait(payload)
                    return
            except RuntimeError:
                pass
            asyncio.run_coroutine_threadsafe(self.log_queue.put(payload), loop)
            return
        # No running loop (unit tests with fakes / before supervisor start).
        if hasattr(self.log_queue, "put_nowait"):
            try:
                self.log_queue.put_nowait(payload)
                return
            except Exception:
                pass
        self.log_queue.put(payload)

    def dump(self):
        return self._dump_data(self.data)

    def set_ended(self):
        self._ended = True
