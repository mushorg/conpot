# Copyright (C) 2020  srenfo
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

import asyncio

import pytest

from conpot import core
from conpot.utils.server_tasks import (
    AsyncioTaskHandle,
    spawn_startable_task,
    spawn_test_server,
    teardown_test_server,
)


class StartableStub:
    def __init__(self):
        self.args = None
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()

    async def start(self, *args):
        self.args = args
        self._ready.set()
        await self._stop.wait()


@pytest.mark.parametrize("args", ((), ("127.0.0.1", 8080), (1, 2, 3, 4)))
def test_spawn_startable_task_passes_args(args):
    async def _run():
        instance = StartableStub()
        handle = spawn_startable_task(instance, *args)
        instance._stop.set()
        await handle._task
        return instance

    instance = asyncio.run(_run())
    assert instance.args == args


def test_spawn_startable_task_sets_name():
    async def _run():
        instance = StartableStub()
        handle = spawn_startable_task(instance)
        instance._stop.set()
        await handle._task
        return handle

    handle = asyncio.run(_run())
    assert handle.name == "StartableStub"


def test_spawn_startable_task_not_scheduled():
    async def _run():
        instance = StartableStub()
        # create_task without yielding so start() has not set _ready yet
        handle = spawn_startable_task(instance)
        scheduled = handle.scheduled_once
        instance._stop.set()
        await handle._task
        return scheduled

    assert asyncio.run(_run()) is False


def test_spawn_startable_task_can_observe_scheduling():
    async def _run():
        instance = StartableStub()
        handle = spawn_startable_task(instance)
        await instance._ready.wait()
        scheduled = handle.scheduled_once
        instance._stop.set()
        await handle._task
        return scheduled

    assert asyncio.run(_run()) is True


class ServerStub:
    def __init__(self, template, template_directory, args):
        self.template = template
        self.template_directory = template_directory
        self.args = args
        self.host = None
        self.port = None
        self._ready = None
        self._stop = None

    async def start(self, host, port):
        self.host = host
        self.port = port
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        self._ready.set()
        await self._stop.wait()

    def stop(self):
        if self._stop is not None:
            self._stop.set()


def test_spawn_test_server_returns_server_and_handle():
    server, handle = spawn_test_server(ServerStub, "default", "Fake", args="arbitrary")
    try:
        assert isinstance(server, ServerStub)
        assert isinstance(handle, AsyncioTaskHandle)

        assert server.template == {}
        assert server.template_directory.endswith("/conpot/templates/default")
        assert server.args == "arbitrary"
    finally:
        teardown_test_server(server, handle)


def test_spawn_test_server_initializes_databus():
    server, handle = spawn_test_server(ServerStub, "default", "Fake")
    try:
        assert core.get_databus().initialized.is_set()
    finally:
        teardown_test_server(server, handle)


def test_spawn_test_server_runs_at_least_once():
    server, handle = spawn_test_server(ServerStub, "default", "Fake")
    try:
        assert handle.scheduled_once is True
    finally:
        teardown_test_server(server, handle)


def test_spawn_test_server_starts_on_localhost_any_port():
    server, handle = spawn_test_server(ServerStub, "default", "Fake")
    try:
        assert server.host == "127.0.0.1"
        assert server.port == 0
    finally:
        teardown_test_server(server, handle)


def test_spawn_test_server_can_set_port():
    server, handle = spawn_test_server(ServerStub, "default", "Fake", port=42)
    try:
        assert server.port == 42
    finally:
        teardown_test_server(server, handle)


class LoopingServer:
    def __init__(self, *_, **__):
        self.stopped = False
        self._stop = None
        self._ready = None

    async def start(self, _, __):
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        self._ready.set()
        await self._stop.wait()

    def stop(self):
        self.stopped = True
        if self._stop is not None:
            self._stop.set()


def test_teardown_test_server_stops_instance():
    server, handle = spawn_test_server(LoopingServer, "default", "Fake")

    teardown_test_server(server, handle)

    assert server.stopped
    assert handle.dead


class RaisingServer:
    def __init__(self, *_, **__):
        self._ready = None
        self._stop = None

    async def start(self, host, port):
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        self._ready.set()
        raise RuntimeError("Test Error")

    def stop(self):
        if self._stop is not None:
            self._stop.set()


def test_teardown_test_server_does_not_raise_from_serve_task():
    # Shutdown cancels / awaits the serve task and swallows its exception.
    server, handle = spawn_test_server(RaisingServer, "default", "Fake")
    teardown_test_server(server, handle)
    assert handle.dead
