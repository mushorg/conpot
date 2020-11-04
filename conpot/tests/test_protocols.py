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

import pytest

from conpot import protocols
from conpot.utils.greenlet import init_test_server_by_name


@pytest.mark.parametrize("name", protocols.name_mapping.keys())
def test_protocols_can_be_stopped(name):
    server, greenlet = init_test_server_by_name(name)

    server.stop()
    greenlet.join(0.2)

    # Greenlets with working shutdown logic will have run to completion
    # Greenlets with broken shutdown logic will wait to be scheduled again
    assert greenlet.successful()


@pytest.mark.parametrize("name", protocols.name_mapping.keys())
def test_protocols_serve_forever(name):
    server, greenlet = init_test_server_by_name(name)

    assert not greenlet.ready()

    server.stop()
    greenlet.join(0.2)
