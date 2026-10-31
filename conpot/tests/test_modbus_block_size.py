# Copyright (C) 2026  MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""Template ``size``/``content`` are authoritative for Modbus blocks."""

import struct

import pytest

import conpot.core as conpot_core
from conpot.protocols.modbus import modbus_server
from conpot.protocols.modbus.slave import BLOCK_TYPES, MBSlave

HOLDING = BLOCK_TYPES["HOLDING_REGISTERS"]
ILLEGAL_ADDRESS = 0x02


def _databus(**values):
    conpot_core.get_databus().initialize(
        {"core": {"databus": {"key_value_mappings": values}}}
    )


def _read_holding(slave, address, count):
    return slave.handle_request(struct.pack(">BHH", HOLDING, address, count))


@pytest.fixture(autouse=True)
def reset_databus():
    yield
    conpot_core.get_databus().reset()


def _template(size, content="regs"):
    return {
        "enabled": True,
        "host": "127.0.0.1",
        "port": 0,
        "mode": "tcp",
        "delay": 100,
        "device_info": {
            "VendorName": "Test",
            "ProductCode": "Size",
            "MajorMinorRevision": "1.0",
        },
        "slaves": [
            {
                "id": 1,
                "blocks": [
                    {
                        "name": "block",
                        "type": "HOLDING_REGISTERS",
                        "starting_address": 40001,
                        "size": size,
                        "content": content,
                    }
                ],
            }
        ],
    }


def test_size_mismatch_raises():
    _databus(regs=list(range(32)))
    slave = MBSlave(1, {})
    with pytest.raises(ValueError, match="size 8 .* holds 32"):
        slave.add_block("regs", HOLDING, 40001, 8)


def test_reads_past_size_are_illegal_address():
    _databus(regs=list(range(8)))
    slave = MBSlave(1, {})
    slave.add_block("regs", HOLDING, 40001, 8)

    response = _read_holding(slave, 40001, 8)
    assert response[0] == HOLDING
    assert struct.unpack(">8H", response[2:]) == tuple(range(8))

    for address, count in ((40001, 9), (40009, 1)):
        response = _read_holding(slave, address, count)
        assert response == bytes((HOLDING | 0x80, ILLEGAL_ADDRESS))


def test_content_selects_databus_key():
    _databus(other=[7] * 4, block=[0] * 99)
    slave = MBSlave(1, {})
    slave.add_block("block", HOLDING, 40001, 4, content="other")

    response = _read_holding(slave, 40001, 4)
    assert struct.unpack(">4H", response[2:]) == (7, 7, 7, 7)


def test_server_refuses_mismatched_template():
    _databus(regs=list(range(32)))
    with pytest.raises(ValueError, match="holds 32"):
        modbus_server.ModbusServer(_template(size=8), None, None)


def test_server_accepts_matching_template():
    _databus(regs=list(range(8)))
    modbus_server.ModbusServer(_template(size=8), None, None)
