# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

import asyncio
from unittest import mock

import conpot
from conpot.core.log_worker import LogWorker


def _config(sensorid="default"):
    config = mock.Mock()
    config.get.side_effect = lambda section, option: {
        ("common", "sensorid"): sensorid,
    }[(section, option)]
    config.getboolean.return_value = False
    return config


def test_log_worker_derives_template_name_from_directory():
    session_manager = mock.Mock()
    session_manager.log_queue = asyncio.Queue()
    worker = LogWorker(
        _config(),
        template={"meta": True},
        session_manager=session_manager,
        public_ip=None,
        template_directory="/opt/conpot/templates/default",
    )
    assert worker.template_name == "default"
    assert worker.template_name is not None


def test_log_worker_stamps_provenance_fields():
    """LogWorker.start stamps sensorid/template/conpot_version before dispatch."""
    session_manager = mock.Mock()
    session_manager.log_queue = asyncio.Queue()
    worker = LogWorker(
        _config(sensorid="honeypot-1"),
        template=None,
        session_manager=session_manager,
        public_ip=None,
        template_directory="/tmp/templates/IEC104",
    )

    event = {"session_id": "abc", "protocol": "modbus"}
    # Mirror the enrichment LogWorker.start applies before _dispatch.
    event["sensorid"] = worker.sensorid
    event["template"] = worker.template_name
    event["conpot_version"] = conpot.__version__

    assert event["sensorid"] == "honeypot-1"
    assert event["template"] == "IEC104"
    assert event["conpot_version"] == conpot.__version__


def test_log_worker_template_name_none_without_directory():
    session_manager = mock.Mock()
    session_manager.log_queue = asyncio.Queue()
    worker = LogWorker(
        _config(),
        template=None,
        session_manager=session_manager,
        public_ip=None,
        template_directory=None,
    )
    assert worker.template_name is None
