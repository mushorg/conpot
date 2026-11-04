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
    log = Mock()
    monkeypatch.setattr(cli, "logger", log)
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
        assert (uid_name, gid_name) == (None, None)
        events.append("drop")
        return "conpot", "conpot"

    def setup_file_logging(log_file, verbose):
        assert "drop" in events
        events.append("file")
        raise PermissionError("not writable by dropped user")

    monkeypatch.setattr(cli, "drop_privileges", drop_privileges)
    monkeypatch.setattr(cli, "setup_file_logging", setup_file_logging)
    monkeypatch.setattr(cli, "list_available_templates", lambda package_dir: [])

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 0
    assert events == ["console", "drop", "file"]
    log.error.assert_called_once()
    log.info.assert_called_once()
    assert log.warning.call_count == 2
    log.warning.assert_any_call(
        "Root --force startup was requested; privileges have now been dropped."
    )
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
    state = {"uid": (0, 0, 0), "gid": (0, 0, 0), "groups": [10, 20]}
    user = SimpleNamespace(pw_name="conpot", pw_uid=1000, pw_gid=1000)
    group = SimpleNamespace(gr_name="conpot", gr_gid=1000)
    monkeypatch.setattr(cli.pwd, "getpwnam", lambda name: user)
    monkeypatch.setattr(cli.pwd, "getpwuid", lambda uid: user)
    monkeypatch.setattr(cli.grp, "getgrnam", lambda name: group)
    monkeypatch.setattr(cli.grp, "getgrgid", lambda gid: group)

    def setgroups(groups):
        events.append("groups")
        state.update(groups=groups)

    def setgid(gid):
        events.append("gid")
        state.update(gid=(gid, gid, gid))

    def setuid(uid):
        events.append("uid")
        state.update(uid=(uid, uid, uid))

    monkeypatch.setattr(cli.os, "setgroups", setgroups)
    monkeypatch.setattr(cli.os, "setgid", setgid)
    monkeypatch.setattr(cli.os, "setuid", setuid)
    monkeypatch.setattr(cli.os, "geteuid", lambda: state["uid"][1])
    monkeypatch.setattr(
        cli.os, "setegid", lambda gid: events.append(("egid", gid)), raising=False
    )

    def seteuid(uid):
        if uid == 0 and state["uid"] == (1000, 1000, 1000):
            raise PermissionError("saved root UID was cleared")
        events.append(("euid", uid))

    monkeypatch.setattr(cli.os, "seteuid", seteuid)
    monkeypatch.setattr(cli.os, "getuid", lambda: state["uid"][0])
    monkeypatch.setattr(cli.os, "getgid", lambda: state["gid"][0])
    monkeypatch.setattr(cli.os, "getresuid", lambda: state["uid"], raising=False)
    monkeypatch.setattr(cli.os, "getresgid", lambda: state["gid"], raising=False)
    monkeypatch.setattr(cli.os, "getgroups", lambda: state["groups"], raising=False)
    monkeypatch.setattr(cli, "logger", Mock())

    cli.drop_privileges("conpot", "conpot")

    assert state == {"uid": (1000, 1000, 1000), "gid": (1000, 1000, 1000), "groups": []}
    assert events == ["groups", "gid", "uid"]


def test_drop_privileges_rejects_saved_root_uid(monkeypatch):
    user = SimpleNamespace(pw_name="conpot", pw_uid=1000, pw_gid=1000)
    group = SimpleNamespace(gr_name="conpot", gr_gid=1000)
    state = {"uid": (0, 0, 0), "gid": (0, 0, 0)}
    monkeypatch.setattr(cli.pwd, "getpwnam", lambda name: user)
    monkeypatch.setattr(cli.grp, "getgrnam", lambda name: group)
    monkeypatch.setattr(cli.pwd, "getpwuid", lambda uid: user)
    monkeypatch.setattr(cli.grp, "getgrgid", lambda gid: group)
    monkeypatch.setattr(cli.os, "getuid", lambda: state["uid"][0])
    monkeypatch.setattr(cli.os, "geteuid", lambda: state["uid"][1])
    monkeypatch.setattr(cli.os, "getgid", lambda: state["gid"][0])
    monkeypatch.setattr(cli.os, "getegid", lambda: state["gid"][1], raising=False)
    monkeypatch.setattr(cli.os, "getgroups", lambda: [], raising=False)
    monkeypatch.setattr(cli.os, "getresuid", lambda: state["uid"], raising=False)
    monkeypatch.setattr(cli.os, "getresgid", lambda: state["gid"], raising=False)
    monkeypatch.setattr(cli.os, "setgroups", lambda groups: None)
    monkeypatch.setattr(cli.os, "setgid", lambda gid: state.update(gid=(gid, gid, gid)))
    monkeypatch.setattr(cli.os, "setuid", lambda uid: state.update(uid=(uid, uid, 0)))
    monkeypatch.setattr(cli.os, "seteuid", lambda uid: None)

    with pytest.raises(RuntimeError, match="clear all user IDs"):
        cli.drop_privileges("conpot", "conpot")
