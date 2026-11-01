# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from conpot import cli


@pytest.mark.parametrize("uids", [(1000, 0, 0), (1000, 1000, 0)])
def test_root_force_drops_privileges_before_file_logging(monkeypatch, tmp_path, uids):
    events = []
    logfile = tmp_path / "already-open.log"
    old_handler = logging.FileHandler(logfile)
    logging.getLogger().addHandler(old_handler)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "testing.cfg").write_text(
        "[daemon]\nuser = conpot\ngroup = conpot-group\n"
    )

    monkeypatch.setattr(cli.sys, "argv", ["conpot", "--force"])
    monkeypatch.setattr(cli, "package_directory", str(config_dir))
    monkeypatch.setattr(cli, "core_interface", SimpleNamespace(config=None))
    # A nonroot real UID must not bypass the root-only startup path when the
    # effective or saved UID is 0.
    monkeypatch.setattr(cli.os, "getuid", lambda: uids[0])
    monkeypatch.setattr(cli.os, "geteuid", lambda: uids[1])
    monkeypatch.setattr(cli.os, "getresuid", lambda: uids, raising=False)
    setup_console_logging = cli.setup_console_logging

    def configure_console(verbose, reset=False):
        assert reset
        events.append("console")
        setup_console_logging(verbose, reset=reset)

    monkeypatch.setattr(cli, "setup_console_logging", configure_console)

    def drop_privileges(uid_name, gid_name):
        assert (uid_name, gid_name) == ("conpot", "conpot-group")
        events.append("drop")

    def setup_file_logging(log_file, verbose):
        assert "drop" in events
        events.append("file")

    monkeypatch.setattr(cli, "drop_privileges", drop_privileges)
    monkeypatch.setattr(cli, "setup_file_logging", setup_file_logging)
    monkeypatch.setattr(cli, "list_available_templates", lambda package_dir: [])

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 0
    assert events == ["console", "drop", "file"]
    assert old_handler.stream is None
    assert "Running conpot with root" not in logfile.read_text()


def test_non_root_force_keeps_file_logging_without_privilege_drop(monkeypatch):
    events = []
    monkeypatch.setattr(cli.sys, "argv", ["conpot", "--force"])
    monkeypatch.setattr(cli, "core_interface", SimpleNamespace(config=None))
    monkeypatch.setattr(cli.os, "getuid", lambda: 1000)
    monkeypatch.setattr(cli.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(cli.os, "getresuid", lambda: (1000, 1000, 1000), raising=False)
    monkeypatch.setattr(
        cli,
        "setup_console_logging",
        lambda verbose, reset=False: events.append("console"),
    )
    monkeypatch.setattr(
        cli,
        "drop_privileges",
        lambda *args: pytest.fail("non-root startup must not drop privileges"),
    )
    monkeypatch.setattr(
        cli, "setup_file_logging", lambda log_file, verbose: events.append("file")
    )
    monkeypatch.setattr(cli, "list_available_templates", lambda package_dir: [])

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 0
    assert events == ["console", "file"]


def test_root_without_force_exits_before_file_logging(monkeypatch):
    events = []
    monkeypatch.setattr(cli.sys, "argv", ["conpot"])
    monkeypatch.setattr(cli, "core_interface", SimpleNamespace(config=None))
    monkeypatch.setattr(cli.os, "getuid", lambda: 0)
    monkeypatch.setattr(cli.os, "geteuid", lambda: 0)
    monkeypatch.setattr(cli.os, "getresuid", lambda: (0, 0, 0), raising=False)
    monkeypatch.setattr(
        cli,
        "setup_console_logging",
        lambda verbose, reset=False: events.append("console"),
    )
    monkeypatch.setattr(
        cli,
        "setup_file_logging",
        lambda *args: pytest.fail("root refusal must not open a logfile"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 3
    assert events == ["console"]


def test_drop_privileges_clears_supplementary_groups_first(monkeypatch):
    events = []
    user = SimpleNamespace(pw_name="conpot", pw_uid=1000, pw_gid=1000)
    group = SimpleNamespace(gr_name="conpot", gr_gid=1000)
    monkeypatch.setattr(cli.pwd, "getpwnam", lambda name: user)
    monkeypatch.setattr(cli.pwd, "getpwuid", lambda uid: user)
    monkeypatch.setattr(cli.grp, "getgrnam", lambda name: group)
    monkeypatch.setattr(cli.grp, "getgrgid", lambda gid: group)
    monkeypatch.setattr(
        cli.os, "setgroups", lambda groups: events.append(("groups", groups))
    )
    monkeypatch.setattr(cli.os, "setgid", lambda gid: events.append(("gid", gid)))
    monkeypatch.setattr(cli.os, "setuid", lambda uid: events.append(("uid", uid)))
    monkeypatch.setattr(cli.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(cli.os, "seteuid", lambda uid: events.append(("euid", uid)))
    monkeypatch.setattr(cli.os, "getuid", lambda: 1000)
    monkeypatch.setattr(cli.os, "getgid", lambda: 1000)
    monkeypatch.setattr(cli, "logger", Mock())

    cli.drop_privileges("conpot", "conpot")

    assert events == [
        ("euid", 0),
        ("groups", []),
        ("gid", 1000),
        ("uid", 1000),
    ]
