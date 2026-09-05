# Copyright (C) 2026  Lukas Rist <glaslos@gmail.com>
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

from gevent import monkey

monkey.patch_all()

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

    def start(self, host, port):
        self.host = host
        self.port = port

    def stop(self):
        self.stopped = True


def _write_protocol_xml(root, name, enabled, host="127.0.0.1", port=15020):
    proto_dir = os.path.join(root, name)
    os.makedirs(proto_dir)
    path = os.path.join(proto_dir, "{}.xml".format(name))
    with open(path, "w") as fh:
        fh.write(
            '<{name} enabled="{enabled}" host="{host}" port="{port}"/>\n'.format(
                name=name, enabled=enabled, host=host, port=port
            )
        )
    return path


def test_start_protocols_enabled_spawns_server():
    with tempfile.TemporaryDirectory() as tmp:
        _write_protocol_xml(tmp, "fakeproto", "True", host="127.0.0.1", port=15020)
        args = Namespace(config="/tmp/testing.cfg")
        fake_greenlet = MagicMock()

        with (
            patch.dict(
                protocol_startup.protocols.name_mapping,
                {"fakeproto": FakeServer},
                clear=True,
            ),
            patch.object(protocol_startup, "validate_template"),
            patch.object(
                protocol_startup,
                "spawn_startable_greenlet",
                return_value=fake_greenlet,
            ) as spawn_mock,
        ):
            servers = protocol_startup.start_protocols(tmp, "/unused", args)

        assert len(servers) == 1
        server, greenlet = servers[0]
        assert isinstance(server, FakeServer)
        assert greenlet is fake_greenlet
        spawn_mock.assert_called_once_with(server, "127.0.0.1", 15020)
        fake_greenlet.link_exception.assert_called_once()


def test_start_protocols_disabled_skips_spawn():
    with tempfile.TemporaryDirectory() as tmp:
        _write_protocol_xml(tmp, "fakeproto", "False")
        args = Namespace(config="/tmp/testing.cfg")

        with (
            patch.dict(
                protocol_startup.protocols.name_mapping,
                {"fakeproto": FakeServer},
                clear=True,
            ),
            patch.object(protocol_startup, "validate_template"),
            patch.object(protocol_startup, "spawn_startable_greenlet") as spawn_mock,
        ):
            servers = protocol_startup.start_protocols(tmp, "/unused", args)

        assert servers == []
        spawn_mock.assert_not_called()


def test_start_protocols_missing_template_skips():
    with tempfile.TemporaryDirectory() as tmp:
        args = Namespace(config="/tmp/testing.cfg")

        with (
            patch.dict(
                protocol_startup.protocols.name_mapping,
                {"fakeproto": FakeServer},
                clear=True,
            ),
            patch.object(protocol_startup, "spawn_startable_greenlet") as spawn_mock,
        ):
            servers = protocol_startup.start_protocols(tmp, "/unused", args)

        assert servers == []
        spawn_mock.assert_not_called()


def test_start_proxy_disabled():
    with tempfile.TemporaryDirectory() as tmp:
        proxy_dir = os.path.join(tmp, "proxy")
        os.makedirs(proxy_dir)
        with open(os.path.join(proxy_dir, "proxy.xml"), "w") as fh:
            fh.write('<proxies enabled="False"/>\n')

        with (
            patch.object(protocol_startup, "validate_template"),
            patch.object(protocol_startup, "spawn_startable_greenlet") as spawn_mock,
        ):
            servers = protocol_startup.start_proxy(tmp)

        assert servers == []
        spawn_mock.assert_not_called()


def test_start_proxy_enabled():
    with tempfile.TemporaryDirectory() as tmp:
        proxy_dir = os.path.join(tmp, "proxy")
        os.makedirs(proxy_dir)
        with open(os.path.join(proxy_dir, "proxy.xml"), "w") as fh:
            fh.write("""
                <proxies enabled="True">
                    <proxy name="test" host="127.0.0.1" port="9999">
                        <proxy_host>10.0.0.1</proxy_host>
                        <proxy_port>80</proxy_port>
                    </proxy>
                </proxies>
                """)

        fake_proxy = MagicMock()
        fake_server = MagicMock()
        fake_proxy.get_server.return_value = fake_server
        fake_greenlet = MagicMock()
        # Preserve real Proxy path for inspect.getfile(Proxy) before mocking
        real_proxy_path = protocol_startup.inspect.getfile(protocol_startup.Proxy)

        with (
            patch.object(protocol_startup, "validate_template"),
            patch.object(
                protocol_startup.inspect, "getfile", return_value=real_proxy_path
            ),
            patch.object(
                protocol_startup, "Proxy", return_value=fake_proxy
            ) as proxy_cls,
            patch.object(
                protocol_startup,
                "spawn_startable_greenlet",
                return_value=fake_greenlet,
            ) as spawn_mock,
        ):
            servers = protocol_startup.start_proxy(tmp)

        assert len(servers) == 1
        assert servers[0] == (fake_proxy, fake_greenlet)
        proxy_cls.assert_called_once_with("test", "10.0.0.1", 80, None, None, None)
        fake_proxy.get_server.assert_called_once_with("127.0.0.1", 9999)
        spawn_mock.assert_called_once_with(fake_server)


def test_start_proxy_missing_template():
    with tempfile.TemporaryDirectory() as tmp:
        servers = protocol_startup.start_proxy(tmp)
        assert servers == []


def test_start_log_worker():
    fake_greenlet = MagicMock()
    fake_worker = MagicMock()

    with (
        patch.object(protocol_startup, "LogWorker", return_value=fake_worker) as lw_cls,
        patch.object(
            protocol_startup, "spawn_startable_greenlet", return_value=fake_greenlet
        ),
    ):
        worker, greenlet = protocol_startup.start_log_worker(
            "config", "dom", "session", "1.2.3.4"
        )

    assert worker is fake_worker
    assert greenlet is fake_greenlet
    lw_cls.assert_called_once_with("config", "dom", "session", "1.2.3.4")


def test_start_services_combines_all():
    args = Namespace(config="/tmp/testing.cfg")
    fake_greenlet = MagicMock()

    with (
        patch.object(
            protocol_startup, "start_protocols", return_value=[("proto", fake_greenlet)]
        ),
        patch.object(
            protocol_startup,
            "start_log_worker",
            return_value=("log", fake_greenlet),
        ),
        patch.object(
            protocol_startup, "start_proxy", return_value=[("proxy", fake_greenlet)]
        ),
    ):
        servers = protocol_startup.start_services(
            "/tmpl", "/pkg", "cfg", args, "dom", "sess", None
        )

    assert servers == [
        ("proto", fake_greenlet),
        ("log", fake_greenlet),
        ("proxy", fake_greenlet),
    ]
