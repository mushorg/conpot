# Copyright (C) 2014 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

import asyncio
import json
import logging
import time

from datetime import datetime

import configparser

from conpot.core.loggers.sqlite_log import SQLiteLogger
from conpot.core.loggers.hpfriends import HPFriendsLogger
from conpot.core.loggers.syslog import SysLogger
from conpot.core.loggers.taxii_log import TaxiiLogger
from conpot.core.loggers.json_log import JsonLogger
from .loggers.helpers import json_default

logger = logging.getLogger(__name__)


class LogWorker(object):
    def __init__(
        self, config, template, session_manager, public_ip, template_directory=None
    ):
        self.config = config
        self.log_queue = session_manager.log_queue
        self.session_manager = session_manager
        self.sqlite_logger = None
        self.json_logger = None
        self.friends_feeder = None
        self.syslog_client = None
        self.public_ip = public_ip
        self.taxii_logger = None

        if config.getboolean("sqlite", "enabled"):
            self.sqlite_logger = SQLiteLogger()

        if config.getboolean("json", "enabled"):
            filename = config.get("json", "filename")
            sensorid = config.get("common", "sensorid")
            self.json_logger = JsonLogger(filename, sensorid, public_ip)

        if config.getboolean("hpfriends", "enabled"):
            host = config.get("hpfriends", "host")
            port = config.getint("hpfriends", "port")
            ident = config.get("hpfriends", "ident")
            secret = config.get("hpfriends", "secret")
            channels = eval(config.get("hpfriends", "channels"))
            try:
                self.friends_feeder = HPFriendsLogger(
                    host, port, ident, secret, channels
                )
            except Exception as e:
                logger.exception(e)
                self.friends_feeder = None

        if config.getboolean("syslog", "enabled"):
            host = config.get("syslog", "host")
            port = config.getint("syslog", "port")
            facility = config.get("syslog", "facility")
            logdevice = config.get("syslog", "device")
            logsocket = config.get("syslog", "socket")
            self.syslog_client = SysLogger(host, port, facility, logdevice, logsocket)

        if config.getboolean("taxii", "enabled"):
            self.taxii_logger = TaxiiLogger(
                config, template, template_directory=template_directory
            )

        self.enabled = True
        self._stop = asyncio.Event()

    def _process_sessions(self):
        sessions = self.session_manager._sessions
        try:
            session_timeout = self.config.get("session", "timeout")
        except configparser.NoSectionError, configparser.NoOptionError:
            session_timeout = 5
        for session in list(sessions):
            if len(session.data) > 0:
                sec_last_event = max(session.data) / 1000
            else:
                sec_last_event = 0
            sec_session_start = time.mktime(session.timestamp.timetuple())
            sec_now = time.mktime(datetime.utcnow().timetuple())
            if (sec_now - (sec_session_start + sec_last_event)) >= float(
                session_timeout
            ):
                logger.info("Session timed out: %s", session.id)
                session.set_ended()
                sessions.remove(session)

    def _dispatch(self, event):
        if self.public_ip:
            event["public_ip"] = self.public_ip

        if self.friends_feeder:
            self.friends_feeder.log(json.dumps(event, default=json_default))

        if self.sqlite_logger:
            self.sqlite_logger.log(event)

        if self.syslog_client:
            self.syslog_client.log(event)

        if self.taxii_logger:
            self.taxii_logger.log(event)

        if self.json_logger:
            self.json_logger.log(event)

    async def start(self):
        """Async consumer loop (supervisor TaskGroup entrypoint)."""
        self.enabled = True
        self._stop.clear()
        while self.enabled and not self._stop.is_set():
            try:
                event = await asyncio.wait_for(self.log_queue.get(), timeout=2.0)
            except asyncio.TimeoutError:
                self._process_sessions()
            else:
                await asyncio.get_running_loop().run_in_executor(
                    None, self._dispatch, event
                )

    def stop(self):
        self.enabled = False
        self._stop.set()
