# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

from datetime import datetime, timezone
from uuid import UUID

from conpot.core.loggers.event import SCHEMA_VERSION, normalize_event


def _session_fields(**overrides):
    base = {
        "session_id": UUID("12345678-1234-5678-1234-567812345678"),
        "protocol": "modbus",
        "session_time": datetime(2000, 1, 1, tzinfo=timezone.utc),
        "event_time": datetime(2000, 1, 2, tzinfo=timezone.utc),
        "src_ip": "1.2.3.4",
        "src_port": 1111,
        "dst_ip": "5.6.7.8",
        "dst_port": 502,
        "public_ip": None,
        "sensorid": None,
    }
    base.update(overrides)
    return base


def test_normalize_connection_only_event():
    event = normalize_event(_session_fields(), {"type": "NEW_CONNECTION"})

    assert event["schema_version"] == SCHEMA_VERSION
    assert event["session_id"] == "12345678-1234-5678-1234-567812345678"
    assert event["protocol"] == "modbus"
    assert event["event_type"] == "NEW_CONNECTION"
    assert event["request"] is None
    assert event["response"] is None
    assert event["error"] is None
    assert event["data"] == {}
    assert "remote" not in event
    assert "local" not in event
    assert "id" not in event
    assert "data_type" not in event
    assert "timestamp" not in event


def test_normalize_request_response():
    event = normalize_event(
        _session_fields(),
        {"request": "ping", "response": "pong"},
    )

    assert event["event_type"] is None
    assert event["request"] == "ping"
    assert event["response"] == "pong"
    assert event["data"] == {}


def test_normalize_preserves_extra_keys_in_data():
    event = normalize_event(
        _session_fields(),
        {
            "type": "PROXY",
            "raw_request": "aabb",
            "raw_response": "ccdd",
            "slave_id": 1,
        },
    )

    assert event["event_type"] == "PROXY"
    assert event["request"] is None
    assert event["response"] is None
    assert event["data"] == {
        "raw_request": "aabb",
        "raw_response": "ccdd",
        "slave_id": 1,
    }


def test_normalize_error_event():
    event = normalize_event(
        _session_fields(),
        {"error": "S7 error: Invalid length"},
    )

    assert event["error"] == "S7 error: Invalid length"
    assert event["event_type"] is None
    assert event["data"] == {}


def test_normalize_event_time_differs_from_session_time():
    event = normalize_event(_session_fields(), {"type": "NEW_CONNECTION"})

    assert event["session_time"] == "2000-01-01T00:00:00+00:00"
    assert event["event_time"] == "2000-01-02T00:00:00+00:00"
    assert event["session_time"] != event["event_time"]


def test_normalize_typed_request_response():
    event = normalize_event(
        _session_fields(),
        {
            "type": "GET",
            "request": {"oid": "1.2"},
            "response": {"oid": "1.2", "val": 1},
        },
    )

    assert event["event_type"] == "GET"
    assert event["request"] == {"oid": "1.2"}
    assert event["response"] == {"oid": "1.2", "val": 1}
    assert event["data"] == {}
