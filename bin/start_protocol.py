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

import gevent

from conpot.utils.greenlet import init_test_server_by_name, teardown_test_server


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
    server, greenlet = init_test_server_by_name(name, port=port)

    try:
        gevent.wait()
    except KeyboardInterrupt:
        teardown_test_server(server=server, greenlet=greenlet)


if __name__ == "__main__":
    main()
