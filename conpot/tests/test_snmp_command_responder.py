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

import os
from tempfile import TemporaryDirectory

import pytest
from pysnmp.smi.error import MibNotFoundError

from conpot.protocols.snmp.command_responder import CommandResponder


def test_register_fails_on_unknown_mib():
    with TemporaryDirectory() as tmpdir:
        responder = CommandResponder("", 0, "/tmp", tmpdir)

        with pytest.raises(MibNotFoundError) as exc_info:
            responder.register("NONEXISTENT-MIB", "foobar", (0,), 42, None)

        assert str(exc_info.value).startswith("NONEXISTENT-MIB compilation error")
        assert not responder._get_mibSymbol("NONEXISTENT-MIB", "foobar")


def test_register_loads_custom_mib():
    raw_mibs = os.path.join(os.path.dirname(__file__), "data")

    with TemporaryDirectory() as tmpdir:
        responder = CommandResponder("", 0, raw_mibs, tmpdir)

        responder.register("VOGON-POEM-MIB", "poemNumber", (0,), 42, None)

        assert responder._get_mibSymbol("VOGON-POEM-MIB", "poemNumber")
