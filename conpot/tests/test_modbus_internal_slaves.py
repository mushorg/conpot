# Copyright (C) 2026  MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""Tests for template-backed internal Modbus slaves (issue #353)."""

import asyncio
import os
import tempfile
import threading
import unittest

import conpot
import conpot.core as conpot_core
from conpot.protocols.modbus import modbus_server
from conpot.tests.helpers.modbus_client import (
    READ_COILS,
    READ_HOLDING_REGISTERS,
    SLAVE_DEVICE_FAILURE,
    WRITE_MULTIPLE_COILS,
    WRITE_MULTIPLE_REGISTERS,
    ModbusError,
    TcpMaster,
)
from conpot.utils.greenlet import AsyncioTaskHandle, teardown_test_server

PACKAGE_DIR = os.path.dirname(os.path.abspath(conpot.__file__))


def _write_tcp_mode_template(path):
    """Minimal template: mode=tcp with two distinct internal slaves."""
    xml = """\
<modbus enabled="True" host="0.0.0.0" port="0">
    <device_info>
        <VendorName>Test</VendorName>
        <ProductCode>Internal</ProductCode>
        <MajorMinorRevision>1.0</MajorMinorRevision>
    </device_info>
    <mode>tcp</mode>
    <delay>100</delay>
    <slaves>
        <slave id="1">
            <blocks>
                <block name="memoryModbusSlave1BlockA">
                    <type>COILS</type>
                    <starting_address>1</starting_address>
                    <size>8</size>
                    <content>memoryModbusSlave1BlockA</content>
                </block>
            </blocks>
        </slave>
        <slave id="2">
            <blocks>
                <block name="memoryModbusSlave2BlockD">
                    <type>HOLDING_REGISTERS</type>
                    <starting_address>40001</starting_address>
                    <size>8</size>
                    <content>memoryModbusSlave2BlockD</content>
                </block>
            </blocks>
        </slave>
        <slave id="255">
            <blocks>
                <block name="memoryModbusSlave255BlockA">
                    <type>COILS</type>
                    <starting_address>1</starting_address>
                    <size>8</size>
                    <content>memoryModbusSlave255BlockA</content>
                </block>
            </blocks>
        </slave>
    </slaves>
</modbus>
"""
    with open(path, "w") as fh:
        fh.write(xml)


class TestModbusInternalSlaves(unittest.TestCase):
    def setUp(self):
        conpot_core.get_sessionManager().purge_sessions()
        template_dir = os.path.join(PACKAGE_DIR, "templates", "default")
        conpot_core.get_databus().initialize(os.path.join(template_dir, "template.xml"))

        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False)
        self.tmp.close()
        _write_tcp_mode_template(self.tmp.name)

        self.modbus = modbus_server.ModbusServer(
            template=self.tmp.name, template_directory=template_dir, args=None
        )

        loop = asyncio.new_event_loop()
        conpot_core.get_sessionManager().attach_event_loop(loop)
        serve_task_ref = {}

        async def _serve():
            serve_task_ref["task"] = asyncio.current_task()
            await self.modbus.start("127.0.0.1", 0)

        loop_ready = threading.Event()

        def loop_worker():
            asyncio.set_event_loop(loop)
            loop.create_task(_serve())
            loop_ready.set()
            loop.run_forever()

        th = threading.Thread(target=loop_worker, daemon=True)
        th.start()
        if not loop_ready.wait(timeout=15.0):
            raise RuntimeError("asyncio test loop thread failed to start")

        async def _wait_ready():
            for _ in range(300):
                ready = getattr(self.modbus, "_ready", None)
                if ready is not None:
                    await asyncio.wait_for(ready.wait(), timeout=30.0)
                    return
                await asyncio.sleep(0.01)
            raise RuntimeError("Modbus server never became ready")

        asyncio.run_coroutine_threadsafe(_wait_ready(), loop).result(timeout=35.0)
        task = serve_task_ref.get("task")
        if task is None:
            raise RuntimeError("protocol serve task was not registered")
        self.greenlet = AsyncioTaskHandle(loop, task, self.modbus, th)

        self.host = self.modbus.server.server_host
        self.port = self.modbus.server.server_port
        self.databus = conpot_core.get_databus()

    def tearDown(self):
        teardown_test_server(self.modbus, self.greenlet)
        os.unlink(self.tmp.name)
        conpot_core.get_sessionManager().purge_sessions()

    def test_tcp_mode_serves_configured_unit_ids(self):
        """mode=tcp must address every internal <slave>, not only UID 255."""
        self.databus.set_value("memoryModbusSlave1BlockA", [1, 0, 1, 0, 1, 0, 1, 0])
        self.databus.set_value("memoryModbusSlave255BlockA", [0, 0, 0, 0, 0, 0, 0, 1])

        master = TcpMaster(host=self.host, port=self.port)
        master.set_timeout(1.0)

        bits_uid1 = master.execute(
            slave=1,
            function_code=READ_COILS,
            starting_address=1,
            quantity_of_x=8,
        )
        bits_uid255 = master.execute(
            slave=255,
            function_code=READ_COILS,
            starting_address=1,
            quantity_of_x=8,
        )
        master.close()

        self.assertSequenceEqual([1, 0, 1, 0, 1, 0, 1, 0], bits_uid1)
        self.assertSequenceEqual([0, 0, 0, 0, 0, 0, 0, 1], bits_uid255)

    def test_internal_slaves_are_independent(self):
        """Writes to one unit id must not affect another slave's memory."""
        self.databus.set_value("memoryModbusSlave1BlockA", [0] * 8)
        self.databus.set_value("memoryModbusSlave2BlockD", [0] * 8)

        master = TcpMaster(host=self.host, port=self.port)
        master.set_timeout(1.0)

        master.execute(
            slave=1,
            function_code=WRITE_MULTIPLE_COILS,
            starting_address=1,
            output_value=[1, 1, 1, 1, 0, 0, 0, 0],
        )
        master.execute(
            slave=2,
            function_code=WRITE_MULTIPLE_REGISTERS,
            starting_address=40001,
            output_value=[10, 20, 30, 40],
        )

        coils = master.execute(
            slave=1,
            function_code=READ_COILS,
            starting_address=1,
            quantity_of_x=8,
        )
        regs = master.execute(
            slave=2,
            function_code=READ_HOLDING_REGISTERS,
            starting_address=40001,
            quantity_of_x=4,
        )
        master.close()

        self.assertSequenceEqual([1, 1, 1, 1, 0, 0, 0, 0], coils)
        self.assertSequenceEqual((10, 20, 30, 40), regs)

    def test_missing_internal_slave_returns_failure(self):
        master = TcpMaster(host=self.host, port=self.port)
        master.set_timeout(1.0)
        with self.assertRaises(ModbusError) as cm:
            master.execute(
                slave=9,
                function_code=READ_COILS,
                starting_address=1,
                quantity_of_x=1,
            )
        master.close()
        self.assertEqual(cm.exception.get_exception_code(), SLAVE_DEVICE_FAILURE)
