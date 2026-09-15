# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""Databus-backed S7 memory areas (DB / M / I / Q)."""

import logging

import conpot.core as conpot_core

logger = logging.getLogger(__name__)

# S7 area codes (any-type addressing)
AREA_I = 0x81
AREA_Q = 0x82
AREA_M = 0x83
AREA_DB = 0x84

AREA_NAME_TO_CODE = {
    "DB": AREA_DB,
    "M": AREA_M,
    "MK": AREA_M,
    "I": AREA_I,
    "PE": AREA_I,
    "Q": AREA_Q,
    "PA": AREA_Q,
}

# Cap a single item to avoid unbounded PDU assembly from untrusted clients.
MAX_ITEM_BYTES = 1024


class S7AddressError(Exception):
    """Requested address is outside a configured area or unknown."""


class S7MemoryMap(object):
    """Maps S7 (area, db_number) pairs to databus keys holding byte stores."""

    def __init__(self):
        # (area_code, db_number) -> databus key name
        self._keys = {}

    def register(self, area_type, number, databus_key, size=None):
        area_type = area_type.upper()
        if area_type not in AREA_NAME_TO_CODE:
            raise ValueError("unsupported S7 area type: {0}".format(area_type))
        area_code = AREA_NAME_TO_CODE[area_type]
        db_number = int(number) if number is not None else 0
        if area_code != AREA_DB:
            db_number = 0
        self._keys[(area_code, db_number)] = databus_key
        logger.debug(
            "S7 memory map: area=0x%02x db=%s key=%s size=%s",
            area_code,
            db_number,
            databus_key,
            size,
        )

    def load_xml(self, dom):
        """Load ``//s7comm/memory_areas/area`` entries from a parsed template."""
        for area in dom.xpath("//s7comm/memory_areas/area"):
            area_type = area.attrib.get("type", "")
            number = area.attrib.get("number")
            name = area.attrib.get("name")
            size = area.attrib.get("size")
            if not name:
                raise ValueError("s7comm memory area missing name (databus key)")
            size_int = int(size) if size is not None else None
            num = int(number) if number is not None else 0
            self.register(area_type, num, name.strip(), size_int)

    def _lookup_key(self, area_code, db_number):
        if area_code != AREA_DB:
            db_number = 0
        return self._keys.get((area_code, db_number))

    @staticmethod
    def _store(databus_key):
        return conpot_core.get_databus().get_value(databus_key)

    @staticmethod
    def _length(store):
        return len(store)

    def read(self, area_code, db_number, offset, length):
        """
        Read ``length`` bytes from the mapped area.

        Raises:
            S7AddressError: unknown area or out-of-range access.
        """
        if length < 0 or length > MAX_ITEM_BYTES:
            raise S7AddressError("invalid read length")
        key = self._lookup_key(area_code, db_number)
        if key is None:
            raise S7AddressError("area not configured")
        store = self._store(key)
        size = self._length(store)
        if offset < 0 or offset + length > size:
            raise S7AddressError("address out of range")
        if isinstance(store, (bytes, bytearray)):
            return bytes(store[offset : offset + length])
        if isinstance(store, list):
            return bytes(int(x) & 0xFF for x in store[offset : offset + length])
        raise S7AddressError("unsupported databus value type for S7 memory")

    def write(self, area_code, db_number, offset, data):
        """
        Write ``data`` bytes in-place into the mapped databus store.

        Raises:
            S7AddressError: unknown area or out-of-range access.
        """
        if not isinstance(data, (bytes, bytearray)):
            data = bytes(data)
        if len(data) > MAX_ITEM_BYTES:
            raise S7AddressError("invalid write length")
        key = self._lookup_key(area_code, db_number)
        if key is None:
            raise S7AddressError("area not configured")
        store = self._store(key)
        size = self._length(store)
        if offset < 0 or offset + len(data) > size:
            raise S7AddressError("address out of range")
        if isinstance(store, bytearray):
            store[offset : offset + len(data)] = data
            return
        if isinstance(store, list):
            for i, byte in enumerate(data):
                store[offset + i] = int(byte) & 0xFF
            return
        if isinstance(store, bytes):
            # Immutable — replace whole value so the write is visible.
            updated = bytearray(store)
            updated[offset : offset + len(data)] = data
            conpot_core.get_databus().set_value(key, bytearray(updated))
            return
        raise S7AddressError("unsupported databus value type for S7 memory")
