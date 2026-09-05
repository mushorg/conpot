# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""Canonical attack-event schema (v1) for the LogWorker sink pipeline."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

SCHEMA_VERSION = 1


def _to_iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _session_id_str(session_id: Any) -> str:
    if isinstance(session_id, UUID):
        return str(session_id)
    return str(session_id)


def normalize_event(session_fields: dict, event_data: dict | None) -> dict:
    """Build a v1 attack event from session metadata and a protocol payload.

    Known payload keys are lifted to the top level:
    ``type`` -> ``event_type``, plus ``request``, ``response``, ``error``.
    Remaining keys are kept under ``data``.
    """
    payload = dict(event_data or {})

    event_type = payload.pop("type", None)
    request = payload.pop("request", None)
    response = payload.pop("response", None)
    error = payload.pop("error", None)

    event_time = session_fields.get("event_time")
    if event_time is None:
        event_time = datetime.now(timezone.utc)

    session_time = session_fields.get("session_time")
    if session_time is None:
        session_time = session_fields.get("timestamp")

    return {
        "schema_version": SCHEMA_VERSION,
        "sensorid": session_fields.get("sensorid"),
        "session_id": _session_id_str(session_fields["session_id"]),
        "protocol": session_fields.get("protocol"),
        "session_time": _to_iso(session_time),
        "event_time": _to_iso(event_time),
        "src_ip": session_fields.get("src_ip"),
        "src_port": session_fields.get("src_port"),
        "dst_ip": session_fields.get("dst_ip"),
        "dst_port": session_fields.get("dst_port"),
        "public_ip": session_fields.get("public_ip"),
        "event_type": event_type,
        "request": request,
        "response": response,
        "error": error,
        "data": payload,
    }
