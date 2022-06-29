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

from contextlib import redirect_stderr

import pytest
from gevent import Greenlet, sleep

from conpot import core
from conpot.utils.greenlet import (
    spawn_startable_greenlet,
    spawn_test_server,
    teardown_test_server,
)


class StartableStub:
    def __init__(self):
        self.args = None

    def start(self, *args):
        self.args = args


@pytest.mark.parametrize("args", ((), ("127.0.0.1", 8080), (1, 2, 3, 4)))
def test_spawn_startable_greenlet_passes_args(args):
    instance = StartableStub()

    greenlet = spawn_startable_greenlet(instance, *args)
    greenlet.get()

    assert instance.args == args


def test_spawn_startable_greenlet_sets_name():
    greenlet = spawn_startable_greenlet(StartableStub())

    assert str(greenlet).startswith('<ServiceGreenlet "StartableStub"')


def test_spawn_startable_greenlet_not_scheduled():
    greenlet = spawn_startable_greenlet(StartableStub())

    assert not greenlet.scheduled_once.is_set()


def test_spawn_startable_greenlet_can_observe_scheduling():
    greenlet = spawn_startable_greenlet(StartableStub())
    greenlet.scheduled_once.wait()

    assert greenlet.scheduled_once.is_set()


class ServerStub:
    def __init__(self, template, template_directory, args):
        self.template = template
        self.template_directory = template_directory
        self.args = args
        self.host = None
        self.port = None

    def start(self, host, port):
        self.host = host
        self.port = port


def test_spawn_test_server_returns_server_and_greenlet():
    server, greenlet = spawn_test_server(
        ServerStub, "default", "Fake", args="arbitrary"
    )

    assert isinstance(server, ServerStub)
    assert isinstance(greenlet, Greenlet)

    assert server.template.endswith("/conpot/templates/default/Fake/Fake.xml")
    assert server.template_directory.endswith("/conpot/templates/default")
    assert server.args == "arbitrary"


def test_spawn_test_server_initializes_databus():
    spawn_test_server(ServerStub, "default", "Fake")

    assert core.get_databus().initialized.is_set()


def test_spawn_test_server_runs_at_least_once():
    _, greenlet = spawn_test_server(ServerStub, "default", "Fake")

    assert greenlet.scheduled_once.is_set()


def test_spawn_test_server_starts_on_localhost_any_port():
    server, _ = spawn_test_server(ServerStub, "default", "Fake")

    assert server.host == "127.0.0.1"
    assert server.port == 0


def test_spawn_test_server_can_set_port():
    server, _ = spawn_test_server(ServerStub, "default", "Fake", port=42)

    assert server.port == 42


class LoopingServer:
    def __init__(self, *_, **__):
        self.stopped = False

    def start(self, _, __):
        while not self.stopped:
            sleep()

    def stop(self):
        self.stopped = True


def test_teardown_test_server_stops_instance():
    server, greenlet = spawn_test_server(LoopingServer, "default", "Fake")

    teardown_test_server(server, greenlet)

    assert server.stopped
    assert greenlet.dead


class RaisingServer(LoopingServer):
    def start(self, host, port):
        super().start(host, port)
        raise RuntimeError("Test Error")


def test_teardown_test_server_propagates_exception():
    server, greenlet = spawn_test_server(RaisingServer, "default", "Fake")

    with pytest.raises(RuntimeError) as exc_info:
        # Greenlets print exception tracebacks to stderr, suppress that in this test
        with redirect_stderr(None):
            teardown_test_server(server, greenlet)

    assert str(exc_info.value) == "Test Error"
