# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

import json
import logging
from unittest import mock

from conpot.core.loggers.event import SCHEMA_VERSION
from conpot.core.loggers.sqlite_log import SQLiteLogger
from conpot.core.loggers.syslog import SysLogger


def _v1_event(**overrides):
    event = {
        "schema_version": SCHEMA_VERSION,
        "sensorid": "default",
        "session_id": "abc-123",
        "protocol": "modbus",
        "session_time": "2000-01-01T00:00:00+00:00",
        "event_time": "2000-01-01T00:00:01+00:00",
        "src_ip": "1.2.3.4",
        "src_port": 1111,
        "dst_ip": "5.6.7.8",
        "dst_port": 502,
        "public_ip": "9.9.9.9",
        "event_type": "NEW_CONNECTION",
        "request": "ping",
        "response": "pong",
        "error": None,
        "data": {"slave_id": 1},
    }
    event.update(overrides)
    return event


def test_sqlite_logger_stores_event_type_and_json(tmp_path, monkeypatch):
    db_dir = tmp_path / "logs"
    db_dir.mkdir()
    db_path = str(db_dir / "conpot.db")

    # Skip privilege chown in unit tests.
    monkeypatch.setattr(SQLiteLogger, "_chown_db", lambda self, path: None)

    logger = SQLiteLogger(db_path=db_path)
    row_id = logger.log(_v1_event())
    assert row_id == 1

    cursor = logger.conn.cursor()
    cursor.execute(
        "SELECT session, remote, protocol, request, response, event_type, event_json "
        "FROM events WHERE id = 1"
    )
    row = cursor.fetchone()
    assert row[0] == "abc-123"
    assert "1.2.3.4" in row[1]
    assert row[2] == "modbus"
    assert row[3] == "ping"
    assert row[4] == "pong"
    assert row[5] == "NEW_CONNECTION"
    stored = json.loads(row[6])
    assert stored["schema_version"] == SCHEMA_VERSION
    assert stored["data"] == {"slave_id": 1}


def test_syslog_logger_emits_json_line():
    handler = mock.Mock()
    handler.level = logging.INFO

    with mock.patch("conpot.core.loggers.syslog.SysLogHandler", return_value=handler):
        syslog = SysLogger(
            host="localhost",
            port=514,
            facility="local0",
            logdevice="/dev/log",
            logsocket="udp",
        )

    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    capture = Capture()
    capture.setLevel(logging.INFO)
    syslog.logger.handlers = [capture]
    syslog.log(_v1_event())

    assert len(records) == 1
    payload = json.loads(records[0].getMessage())
    assert payload["session_id"] == "abc-123"
    assert payload["protocol"] == "modbus"
    assert payload["schema_version"] == SCHEMA_VERSION
