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

from datetime import datetime, timezone

from conpot.core.loggers.event import SCHEMA_VERSION, normalize_event

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
        self.timestamp = datetime.now(timezone.utc)
        self.public_ip = None
        self.data = dict()
        self._ended = False

    def _session_fields(self, event_time=None):
        return {
            "session_id": self.id,
            "protocol": self.protocol,
            "session_time": self.timestamp,
            "event_time": event_time or datetime.now(timezone.utc),
            "src_ip": self.source_ip,
            "src_port": self.source_port,
            "dst_ip": self.destination_ip,
            "dst_port": self.destination_port,
            "public_ip": self.public_ip,
            "sensorid": None,
        }

    def _dump_data(self, data, event_time=None):
        return normalize_event(self._session_fields(event_time=event_time), data)

    def add_event(self, event_data):
        event_time = datetime.now(timezone.utc)
        sec_elapsed = (event_time - self.timestamp).total_seconds()
        elapse_ms = int(sec_elapsed * 1000)
        while elapse_ms in self.data:
            elapse_ms += 1
        event = self._dump_data(event_data, event_time=event_time)
        self.data[elapse_ms] = event
        self._enqueue(event)

    def log_event(
        self, event_type=None, request=None, response=None, error=None, **extra
    ):
        event_data = dict(extra)
        if event_type is not None:
            event_data["type"] = event_type
        if request is not None:
            event_data["request"] = request
        if response is not None:
            event_data["response"] = response
        if error is not None:
            event_data["error"] = error
        self.add_event(event_data)

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
        return {
            "schema_version": SCHEMA_VERSION,
            "session_id": str(self.id),
            "protocol": self.protocol,
            "session_time": (
                self.timestamp.isoformat()
                if isinstance(self.timestamp, datetime)
                else self.timestamp
            ),
            "src_ip": self.source_ip,
            "src_port": self.source_port,
            "dst_ip": self.destination_ip,
            "dst_port": self.destination_port,
            "public_ip": self.public_ip,
            "data": self.data,
        }

    def set_ended(self):
        self._ended = True
