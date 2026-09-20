# Copyright (C) 2026 MushMush Foundation
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
import os
import tempfile
from argparse import Namespace
from unittest.mock import MagicMock, patch

from conpot.core import protocol_startup


class FakeServer:
    def __init__(self, template, template_directory, args):
        self.template = template
        self.template_directory = template_directory
        self.args = args
        self.stopped = False
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()

    async def start(self, host, port):
        self.host = host
        self.port = port
        self._ready.set()
        await self._stop.wait()

    def stop(self):
        self.stopped = True
        if hasattr(self, "_stop"):
            self._stop.set()


def _write_protocol_toml(root, name, enabled, host="127.0.0.1", port=15020):
    path = os.path.join(root, "{}.toml".format(name))
    with open(path, "w") as fh:
        fh.write(
            '[{name}]\nenabled = {enabled}\nhost = "{host}"\nport = {port}\n'.format(
                name=name,
                enabled="true" if enabled in (True, "True", "true") else "false",
                host=host,
                port=port,
            )
        )
    return path


def test_start_protocols_enabled_collects_server():
    with tempfile.TemporaryDirectory() as tmp:
        _write_protocol_toml(tmp, "fakeproto", True, host="127.0.0.1", port=15020)
        args = Namespace(config="/tmp/testing.cfg")
        fake_schema = MagicMock()

        with (
            patch.dict(
                protocol_startup.protocols.name_mapping,
                {"fakeproto": FakeServer},
                clear=True,
            ),
            patch.object(
                protocol_startup.protocol_schemas, "fakeproto", fake_schema, create=True
            ),
        ):
            servers = protocol_startup.collect_protocols(tmp, "/unused", args)

        assert len(servers) == 1
        server, host, port = servers[0]
        assert isinstance(server, FakeServer)
        assert isinstance(server.template, dict)
        assert host == "127.0.0.1"
        assert port == 15020


def test_start_protocols_disabled_skips_spawn():
    with tempfile.TemporaryDirectory() as tmp:
        _write_protocol_toml(tmp, "fakeproto", False)
        args = Namespace(config="/tmp/testing.cfg")
        fake_schema = MagicMock()

        with (
            patch.dict(
                protocol_startup.protocols.name_mapping,
                {"fakeproto": FakeServer},
                clear=True,
            ),
            patch.object(
                protocol_startup.protocol_schemas, "fakeproto", fake_schema, create=True
            ),
        ):
            servers = protocol_startup.collect_protocols(tmp, "/unused", args)

        assert servers == []


def test_start_protocols_missing_template_skips():
    with tempfile.TemporaryDirectory() as tmp:
        args = Namespace(config="/tmp/testing.cfg")

        with patch.dict(
            protocol_startup.protocols.name_mapping,
            {"fakeproto": FakeServer},
            clear=True,
        ):
            servers = protocol_startup.collect_protocols(tmp, "/unused", args)

        assert servers == []


def test_start_proxy_disabled():
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "proxy.toml"), "w") as fh:
            fh.write("[proxies]\nenabled = false\nproxy = []\n")

        servers = protocol_startup.collect_proxies(tmp)
        assert servers == []


def test_start_proxy_enabled():
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "proxy.toml"), "w") as fh:
            fh.write("""
[proxies]
enabled = true

[[proxies.proxy]]
name = "test"
host = "127.0.0.1"
port = 9999
proxy_host = "10.0.0.1"
proxy_port = 80
""")

        fake_proxy = MagicMock()

        with patch.object(
            protocol_startup, "Proxy", return_value=fake_proxy
        ) as proxy_cls:
            servers = protocol_startup.collect_proxies(tmp)

        assert len(servers) == 1
        assert servers[0] == (fake_proxy, "127.0.0.1", 9999)
        proxy_cls.assert_called_once_with("test", "10.0.0.1", 80, None, None, None)


def test_start_proxy_missing_template():
    with tempfile.TemporaryDirectory() as tmp:
        servers = protocol_startup.collect_proxies(tmp)
        assert servers == []


def test_create_log_worker():
    fake_worker = MagicMock()

    with patch.object(
        protocol_startup, "LogWorker", return_value=fake_worker
    ) as lw_cls:
        worker = protocol_startup.create_log_worker(
            "config", "dom", "session", "1.2.3.4", template_directory="/tmpl"
        )

    assert worker is fake_worker
    lw_cls.assert_called_once_with(
        "config", "dom", "session", "1.2.3.4", template_directory="/tmpl"
    )


def test_start_services_combines_all():
    args = Namespace(config="/tmp/testing.cfg")
    fake_handle = MagicMock()
    ready = asyncio.Event()
    ready.set()
    fake_server = MagicMock()
    fake_server._ready = ready
    fake_proxy = MagicMock()
    fake_proxy._ready = ready
    fake_log = MagicMock()
    fake_log._ready = ready

    async def _run():
        with (
            patch.object(
                protocol_startup,
                "collect_protocols",
                return_value=[(fake_server, "127.0.0.1", 1)],
            ),
            patch.object(protocol_startup, "create_log_worker", return_value=fake_log),
            patch.object(
                protocol_startup,
                "collect_proxies",
                return_value=[(fake_proxy, "127.0.0.1", 2)],
            ),
            patch.object(
                protocol_startup, "spawn_startable_task", return_value=fake_handle
            ) as spawn_mock,
        ):
            return (
                await protocol_startup.start_services(
                    "/tmpl", "/pkg", "cfg", args, "dom", "sess", None
                ),
                spawn_mock,
            )

    handles, spawn_mock = asyncio.run(_run())
    assert handles == [
        (fake_server, fake_handle),
        (fake_log, fake_handle),
        (fake_proxy, fake_handle),
    ]
    assert spawn_mock.call_count == 3
