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

import time

import pytest

import conpot.core as conpot_core
from conpot.tests.helpers.modbus_client import (
    READ_DISCRETE_INPUTS,
    READ_HOLDING_REGISTERS,
    READ_INPUT_REGISTERS,
    WRITE_MULTIPLE_COILS,
    TcpMaster,
)
from conpot.emulators.plc.awlsim_engine import AwlsimEngine
from conpot.emulators.plc.scan_cycle import _make_engine
from conpot.protocols.modbus import modbus_server
from conpot.utils.greenlet import spawn_test_server, teardown_test_server

SCAN_WAIT = 0.2


@pytest.fixture(scope="class")
def plc_modbus_server(request):
    server, greenlet = spawn_test_server(
        modbus_server.ModbusServer, "plc_modbus", "modbus"
    )
    request.cls.modbus = server
    request.cls.greenlet = greenlet
    request.cls.host = server.server.server_host
    request.cls.port = server.server.server_port
    yield
    teardown_test_server(server, greenlet)
    conpot_core.get_databus().reset()


@pytest.mark.usefixtures("plc_modbus_server")
class TestPlcModbus:
    def _master(self):
        master = TcpMaster(host=self.host, port=self.port)
        master.set_timeout(1.0)
        return master

    def test_start_coil_sets_running_and_increments_holding(self):
        master = self._master()
        master.execute(
            slave=1,
            function_code=WRITE_MULTIPLE_COILS,
            starting_address=1,
            output_value=[1, 0],
        )
        time.sleep(SCAN_WAIT)
        running = master.execute(
            slave=1,
            function_code=READ_DISCRETE_INPUTS,
            starting_address=10001,
            quantity_of_x=1,
        )
        assert running[0] == 1

        first = master.execute(
            slave=1,
            function_code=READ_HOLDING_REGISTERS,
            starting_address=40001,
            quantity_of_x=1,
        )[0]
        time.sleep(SCAN_WAIT)
        second = master.execute(
            slave=1,
            function_code=READ_HOLDING_REGISTERS,
            starting_address=40001,
            quantity_of_x=1,
        )[0]
        analog = master.execute(
            slave=1,
            function_code=READ_INPUT_REGISTERS,
            starting_address=30001,
            quantity_of_x=1,
        )[0]
        assert second > first
        expected = {
            (h * 10) % 65536
            for h in (second, (second + 1) & 0xFFFF, (second - 1) & 0xFFFF)
        }
        assert analog in expected

    def test_stop_coil_clears_running_and_freezes_holding(self):
        master = self._master()
        master.execute(
            slave=1,
            function_code=WRITE_MULTIPLE_COILS,
            starting_address=1,
            output_value=[1, 0],
        )
        time.sleep(SCAN_WAIT)
        master.execute(
            slave=1,
            function_code=WRITE_MULTIPLE_COILS,
            starting_address=1,
            output_value=[0, 1],
        )
        time.sleep(SCAN_WAIT)
        running = master.execute(
            slave=1,
            function_code=READ_DISCRETE_INPUTS,
            starting_address=10001,
            quantity_of_x=1,
        )
        assert running[0] == 0

        frozen = master.execute(
            slave=1,
            function_code=READ_HOLDING_REGISTERS,
            starting_address=40001,
            quantity_of_x=1,
        )[0]
        time.sleep(SCAN_WAIT)
        later = master.execute(
            slave=1,
            function_code=READ_HOLDING_REGISTERS,
            starting_address=40001,
            quantity_of_x=1,
        )[0]
        assert later == frozen


def test_awlsim_engine_requires_package():
    try:
        import awlsim  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError, match="awlsim"):
            AwlsimEngine()
    else:
        with pytest.raises(NotImplementedError, match="not wired"):
            AwlsimEngine()


def test_unknown_engine_name_rejected():
    with pytest.raises(ValueError, match="Unknown PLC engine"):
        _make_engine("openplc")
