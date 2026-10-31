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

import logging
import threading
import time

import pytest

import conpot.core as conpot_core
from conpot.core.databus import Databus
from conpot.tests.helpers.modbus_client import (
    READ_DISCRETE_INPUTS,
    READ_HOLDING_REGISTERS,
    READ_INPUT_REGISTERS,
    WRITE_MULTIPLE_COILS,
    TcpMaster,
    exchange_pdu,
)
from conpot.emulators.plc.awlsim_engine import AwlsimEngine
from conpot.emulators.plc.scan_cycle import PlcScanCycle, _make_engine
from conpot.protocols.modbus import modbus_server
from conpot.protocols.modbus.slave import MBSlave
from conpot.utils.server_tasks import spawn_test_server, teardown_test_server

SCAN_WAIT = 0.2


@pytest.fixture(scope="class")
def plc_modbus_server(request):
    server, handle = spawn_test_server(
        modbus_server.ModbusServer, "plc_modbus", "modbus"
    )
    request.cls.modbus = server
    request.cls.handle = handle
    request.cls.host = server.server.server_host
    request.cls.port = server.server.server_port
    yield
    teardown_test_server(server, handle)
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

    def test_umas_stop_pauses_scan_until_restart(self):
        master = self._master()
        master.execute(
            slave=1,
            function_code=WRITE_MULTIPLE_COILS,
            starting_address=1,
            output_value=[1, 0],
        )
        time.sleep(SCAN_WAIT)

        def umas_command(code):
            return exchange_pdu(self.host, self.port, bytes((0x5A, 0x00, code)))

        start_response = None
        try:
            assert umas_command(0x41) == (b"\x00\x00\x00\x00\x00\x04\x01\x5a\x00\xfe")
            assert not self.modbus._databank.get_slave(1).running
            time.sleep(SCAN_WAIT)
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
            assert second == first
        finally:
            start_response = umas_command(0x40)

        assert start_response == b"\x00\x00\x00\x00\x00\x04\x01\x5a\x00\xfe"
        assert self.modbus._databank.get_slave(1).running
        time.sleep(SCAN_WAIT)
        resumed = master.execute(
            slave=1,
            function_code=READ_HOLDING_REGISTERS,
            starting_address=40001,
            quantity_of_x=1,
        )[0]
        assert resumed > second

    def test_umas_and_scan_share_cpu_state_key(self):
        scan = conpot_core.get_databus().get_value("plc_scan")
        slave = self.modbus._databank.get_slave(1)
        assert slave._cpu_state_key == scan.cpu_state_key


def _scan_databus(cpu_state=None, include_cpu_state=True):
    databus = Databus()
    databus.set_value("memoryModbusSlave1BlockA", [1, 0])
    databus.set_value("memoryModbusSlave1BlockB", [0, 0])
    databus.set_value("memoryModbusSlave1BlockC", [0, 0])
    databus.set_value("memoryModbusSlave1BlockD", [0, 0])
    if include_cpu_state:
        databus.set_value("plc_cpu_running", cpu_state)
    databus.initialized.set()
    return databus


def test_scan_without_cpu_state_key_keeps_running(monkeypatch):
    databus = _scan_databus(include_cpu_state=False)
    monkeypatch.setattr(conpot_core, "get_databus", lambda: databus)
    scan = PlcScanCycle(scan_ms=1)
    try:
        deadline = time.monotonic() + 1.0
        while databus.get_value("memoryModbusSlave1BlockD")[0] == 0:
            assert time.monotonic() < deadline
            time.sleep(0.01)
    finally:
        scan.stop()


@pytest.mark.parametrize("cpu_state", [[], 1])
def test_malformed_cpu_state_stops_before_scan(monkeypatch, caplog, cpu_state):
    databus = _scan_databus(cpu_state=cpu_state)
    monkeypatch.setattr(conpot_core, "get_databus", lambda: databus)
    with caplog.at_level(logging.ERROR):
        scan = PlcScanCycle(scan_ms=1)
        assert scan.stopped.wait(timeout=1.0)
    assert databus.get_value("memoryModbusSlave1BlockD")[0] == 0
    assert [
        record.message
        for record in caplog.records
        if record.message == "PLC scan cycle failed to start"
    ] == ["PLC scan cycle failed to start"]


def test_umas_state_update_persists_and_notifies_observers(monkeypatch):
    databus = Databus()
    databus.set_value("cpu", lambda: [0])
    monkeypatch.setattr(conpot_core, "get_databus", lambda: databus)
    first = MBSlave(1, {"umas_enabled": True, "umas_cpu_state_key": "cpu"})
    second = MBSlave(2, {"umas_enabled": True, "umas_cpu_state_key": "cpu"})
    assert not first.running
    assert not second.running

    notified = threading.Event()
    databus.observe_value("cpu", lambda _key: notified.set())
    response = first.handle_request(b"\x5a\x00\x40")

    assert response == b"\x5a\x00\xfe"
    assert databus.get_value("cpu") == [1]
    assert notified.wait(timeout=1.0)
    assert first.running
    assert second.running


def test_failed_umas_state_write_keeps_event_type(monkeypatch):
    databus = Databus()
    monkeypatch.setattr(conpot_core, "get_databus", lambda: databus)
    slave = MBSlave(1, {"umas_enabled": True, "umas_cpu_state_key": "missing"})

    assert slave.handle_request(b"\x5a\x00\x41") == b"\xda\x04"
    assert slave.event_type == "UMAS_STOP"
    assert slave.running


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
