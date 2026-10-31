# Copyright (C) 2013 MushMush Foundation
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

import asyncio
import hashlib
import logging
import os
import struct

import conpot.core as conpot_core
from conpot.core.protocol_wrapper import conpot_protocol
from conpot.protocols.snmp.command_responder import CommandResponder

logger = logging.getLogger()

# Served when a template does not map sysObjectID itself; otherwise PySNMP
# answers with its own enterprise OID (1.3.6.1.4.1.20408). This is the Siemens
# AG automation subtree (AUTOMATION-SMI), matching the shipped templates.
DEFAULT_SYS_OBJECT_ID = "1.3.6.1.4.1.4329.6"
ENTERPRISE_PREFIX = (1, 3, 6, 1, 4, 1)
DEFAULT_ENTERPRISE = 4329
# RFC 3411 snmpEngineID is 5..32 octets.
ENGINE_ID_MIN_OCTETS = 5
ENGINE_ID_MAX_OCTETS = 32


def _databus_value(key):
    try:
        return conpot_core.get_databus().get_value(key)
    except AssertionError, KeyError:
        return None


@conpot_protocol
class SNMPServer(object):
    def __init__(self, template, template_directory, args):
        """
        :param template:    protocol config dict from snmp.toml.
        """

        self.template = template
        self.cmd_responder = None

        self.compiled_mibs = args.mibcache
        self.raw_mibs = os.path.join(template_directory, "snmp", "mibs")

    def apply_general_config(self):
        for entity in self.template.get("config", []):
            name = str(entity.get("name", "")).lower()
            command = str(entity.get("command", "")).lower()
            text = entity.get("value")
            # TARPIT: individual response delays
            if name == "tarpit":
                sanitized = self.config_sanitize_tarpit(text)
                if command == "get":
                    self.cmd_responder.resp_app_get.tarpit = sanitized
                elif command == "set":
                    self.cmd_responder.resp_app_set.tarpit = sanitized
                elif command == "next":
                    self.cmd_responder.resp_app_next.tarpit = sanitized
                elif command == "bulk":
                    self.cmd_responder.resp_app_bulk.tarpit = sanitized

            # EVASION: response thresholds
            if name == "evasion":
                sanitized = self.config_sanitize_threshold(text)
                if command == "get":
                    self.cmd_responder.resp_app_get.threshold = sanitized
                elif command == "set":
                    self.cmd_responder.resp_app_set.threshold = sanitized
                elif command == "next":
                    self.cmd_responder.resp_app_next.threshold = sanitized
                elif command == "bulk":
                    self.cmd_responder.resp_app_bulk.threshold = sanitized

    def apply_mib_config(self):
        has_sys_object_id = False
        for mib in self.template.get("mibs", []):
            mib_name = mib["name"]
            for symbol in mib.get("symbols", []):
                symbol_name = symbol["name"]
                if "instance" in symbol:
                    symbol_instance = tuple(
                        map(int, str(symbol["instance"]).split("."))
                    )
                else:
                    symbol_instance = (0,)
                profile_map_name = symbol["value"]
                value = conpot_core.get_databus().get_value(profile_map_name)
                self.cmd_responder.register(
                    mib_name, symbol_name, symbol_instance, value, profile_map_name
                )
                if (mib_name, symbol_name, symbol_instance) == (
                    "SNMPv2-MIB",
                    "sysObjectID",
                    (0,),
                ):
                    has_sys_object_id = True

        if not has_sys_object_id:
            # Never fall through to PySNMP's built-in sysObjectID.
            if _databus_value("sysObjectID") is None:
                conpot_core.get_databus().set_value(
                    "sysObjectID", DEFAULT_SYS_OBJECT_ID
                )
            self.cmd_responder.register(
                "SNMPv2-MIB",
                "sysObjectID",
                (0,),
                conpot_core.get_databus().get_value("sysObjectID"),
                "sysObjectID",
            )

    def _sys_object_id(self):
        """The sysObjectID this template will serve, as a dotted string."""
        for mib in self.template.get("mibs", []):
            if mib["name"] != "SNMPv2-MIB":
                continue
            for symbol in mib.get("symbols", []):
                if symbol["name"] == "sysObjectID" and "instance" not in symbol:
                    value = _databus_value(symbol["value"])
                    if value is not None:
                        return str(value)
        value = _databus_value("sysObjectID")
        return str(value) if value is not None else DEFAULT_SYS_OBJECT_ID

    def engine_id(self):
        """snmpEngineID bytes: the template's ``engine_id`` or a derived one.

        The derived ID follows RFC 3411 (enterprise number with the high bit
        set, format 0x05 = opaque octets) and is stable across restarts. It
        uses the enterprise from sysObjectID and a hash of the identity
        strings, never the host name.
        """
        configured = self.template.get("engine_id")
        if configured:
            try:
                engine_id = bytes.fromhex(str(configured).replace(":", ""))
            except ValueError:
                raise ValueError("SNMP engine_id must be hex: %r" % configured)
            if not (ENGINE_ID_MIN_OCTETS <= len(engine_id) <= ENGINE_ID_MAX_OCTETS):
                raise ValueError(
                    "SNMP engine_id must be %d..%d octets, got %d"
                    % (ENGINE_ID_MIN_OCTETS, ENGINE_ID_MAX_OCTETS, len(engine_id))
                )
            return engine_id

        sys_object_id = self._sys_object_id()
        enterprise = DEFAULT_ENTERPRISE
        try:
            arcs = tuple(int(x) for x in sys_object_id.strip(".").split("."))
            if len(arcs) > len(ENTERPRISE_PREFIX) and (
                arcs[: len(ENTERPRISE_PREFIX)] == ENTERPRISE_PREFIX
            ):
                enterprise = arcs[len(ENTERPRISE_PREFIX)]
        except ValueError:
            pass
        if not 0 < enterprise < 0x80000000:
            enterprise = DEFAULT_ENTERPRISE

        seed = "|".join(
            str(_databus_value(key) or "")
            for key in ("sysName", "SystemDescription", "sysDescr")
        )
        seed += "|" + sys_object_id
        suffix = hashlib.sha256(seed.encode("utf-8")).digest()[:8]
        return struct.pack(">IB", 0x80000000 | enterprise, 0x05) + suffix

    def config_sanitize_tarpit(self, value):
        # checks tarpit value for being either a single int or float,
        # or a series of two concatenated integers and/or floats separated by semicolon and returns
        # either the (sanitized) value or zero.

        if value is not None:
            x, _, y = value.partition(";")

            try:
                _ = float(x)
            except ValueError:
                logger.error(
                    "SNMP invalid tarpit value: '%s'. Assuming no latency.", value
                )
                # first value is invalid, ignore the whole setting.
                return "0;0"

            try:
                _ = float(y)
                # both values are fine.
                return value
            except ValueError:
                # second value is invalid, use the first one.
                return x

        else:
            return "0;0"

    def config_sanitize_threshold(self, value):
        # checks DoS thresholds for being either a single int or a series of two concatenated integers
        # separated by semicolon and returns either the (sanitized) value or zero.

        if value is not None:
            x, _, y = value.partition(";")

            try:
                _ = int(x)
            except ValueError:
                logger.error(
                    "SNMP invalid evasion threshold: '%s'. Assuming no DoS evasion.",
                    value,
                )
                # first value is invalid, ignore the whole setting.
                return "0;0"

            try:
                _ = int(y)
                # both values are fine.
                return value
            except ValueError:
                # second value is invalid, use the first and ignore the second.
                return str(x) + ";0"

        else:
            return "0;0"

    async def start(self, host, port):
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        self.cmd_responder = CommandResponder(
            host,
            port,
            self.raw_mibs,
            self.compiled_mibs,
            engine_id=self.engine_id(),
        )
        await self.cmd_responder.start()
        self.apply_general_config()
        self.apply_mib_config()

        logger.info("SNMP server started on: %s", (host, self.get_port()))
        self._ready.set()
        await self.cmd_responder.serve_forever()

    def stop(self):
        if self.cmd_responder:
            self.cmd_responder.stop()
        if hasattr(self, "_stop"):
            self._stop.set()

    def get_port(self):
        if self.cmd_responder:
            return self.cmd_responder.server_port
        else:
            return None
