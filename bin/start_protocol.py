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
import sys
from types import SimpleNamespace

import gevent

from conpot import protocols
from conpot.core import initialize_vfs
from conpot.utils.greenlet import spawn_test_server, teardown_test_server


def _init_test_server_by_name(name, port=0):
    server_class = protocols.name_mapping[name]

    template = {
        "guardian_ast": "guardian_ast",
        "IEC104": "IEC104",
        "kamstrup_management": "kamstrup_382",
        "kamstrup_meter": "kamstrup_382",
    }.get(name, "default")

    # Required by SNMP
    class Args(SimpleNamespace):
        mibcache = None

    if name in ("ftp", "tftp"):
        initialize_vfs()

    return spawn_test_server(server_class, template, name, args=Args(), port=port)


def main():
    """Start individual protocol instances (for debugging)"""
    name = sys.argv[1]

    ports = {
        "bacnet": 9999,
        "enip": 60002,
        "ftp": 10001,
        "guardian_ast": 10001,
        "http": 50001,
        "kamstrup_management": 50100,
        "kamstrup_meter": 1025,
        "ipmi": 10002,
        "s7comm": 9999,
        "tftp": 6090,
    }

    port = ports.get(name, 0)

    print(f"Starting '{name}'...")
    server, greenlet = _init_test_server_by_name(name, port=port)

    try:
        gevent.wait()
    except KeyboardInterrupt:
        teardown_test_server(server=server, greenlet=greenlet)


if __name__ == "__main__":
    main()
