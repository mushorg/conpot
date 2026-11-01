# Copyright (C) 2026 MushMush Foundation
# Originally by Sooky Peter <xsooky00@stud.fit.vutbr.cz>
# Brno University of Technology, Faculty of Information Technology
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
"""Fingerprint a Modbus/TCP + SNMP device and emit a Conpot template skeleton.

Uses only Conpot's own dependencies (asyncio, pymodbus PDUs, pysnmp hlapi):

    uv run python tools/conpot_cloner.py 192.0.2.10 --output-dir clone/

Only point this at devices you own or are authorised to test. The Modbus scan
issues many read requests; tune ``--stride``/``--max-address``/``--unit-ids``
for fragile targets. Nothing is ever written to the target.
"""

import argparse
import asyncio
import json
import logging
import os
import re
import struct
import sys

from pymodbus.pdu.bit_message import (
    ReadCoilsRequest,
    ReadCoilsResponse,
    ReadDiscreteInputsRequest,
    ReadDiscreteInputsResponse,
)
from pymodbus.pdu.register_message import (
    ReadHoldingRegistersRequest,
    ReadHoldingRegistersResponse,
    ReadInputRegistersRequest,
    ReadInputRegistersResponse,
)
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    bulk_walk_cmd,
)
from pyasn1.type import univ
from pysnmp.proto import rfc1902

logger = logging.getLogger("conpot_cloner")

# Conpot block type -> (function code, request, response, max per read).
MODBUS_TABLES = {
    "COILS": (1, ReadCoilsRequest, ReadCoilsResponse, 2000),
    "DISCRETE_INPUTS": (2, ReadDiscreteInputsRequest, ReadDiscreteInputsResponse, 2000),
    "HOLDING_REGISTERS": (
        3,
        ReadHoldingRegistersRequest,
        ReadHoldingRegistersResponse,
        125,
    ),
    "ANALOG_INPUTS": (4, ReadInputRegistersRequest, ReadInputRegistersResponse, 125),
}
BIT_TABLES = ("COILS", "DISCRETE_INPUTS")
# Exception codes that prove a unit exists: it parsed the request and
# rejected the function, address or value. Anything else (0x04 slave device
# failure, 0x0A/0x0B gateway errors) is what gateways and Conpot itself return
# for unit ids that have nobody behind them.
PRESENCE_EXCEPTIONS = (0x01, 0x02, 0x03)
MEI_DEVICE_INFO_OBJECTS = {
    0: "VendorName",
    1: "ProductCode",
    2: "MajorMinorRevision",
}
# MBAP length is unit id + PDU; a PDU is at most 253 bytes.
MAX_MBAP_LENGTH = 254


class ModbusNoResponse(Exception):
    """Peer closed, timed out, or sent an unusable frame."""


class ModbusException(Exception):
    def __init__(self, function_code, code):
        super().__init__("function 0x%02x exception 0x%02x" % (function_code, code))
        self.code = code


def parse_id_ranges(text):
    ids = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            low, high = (int(x) for x in part.split("-", 1))
        else:
            low = high = int(part)
        if not 0 <= low <= high <= 255:
            raise argparse.ArgumentTypeError("unit id out of range: %s" % part)
        ids.extend(range(low, high + 1))
    return sorted(set(ids))


class ModbusConnection(object):
    """One Modbus/TCP connection; reconnects transparently after a drop."""

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._reader = None
        self._writer = None
        self._transaction_id = 0

    async def _connect(self):
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), self.timeout
        )

    async def close(self):
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except OSError:
                pass
        self._reader = None
        self._writer = None

    async def request(self, unit_id, pdu):
        """Send ``pdu`` to ``unit_id``; return the response PDU bytes."""
        if self._writer is None:
            await self._connect()
        self._transaction_id = (self._transaction_id + 1) & 0xFFFF
        frame = struct.pack(">HHHB", self._transaction_id, 0, len(pdu) + 1, unit_id)
        try:
            self._writer.write(frame + pdu)
            await self._writer.drain()
            header = await asyncio.wait_for(self._reader.readexactly(7), self.timeout)
            _tid, _pid, length, _unit = struct.unpack(">HHHB", header)
            if not 2 <= length <= MAX_MBAP_LENGTH:
                raise ModbusNoResponse("bad MBAP length %d" % length)
            body = await asyncio.wait_for(
                self._reader.readexactly(length - 1), self.timeout
            )
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, OSError) as exc:
            # Either side may have given up; never reuse a half-read stream.
            await self.close()
            raise ModbusNoResponse(str(exc) or type(exc).__name__)
        if body[0] & 0x80:
            raise ModbusException(body[0] & 0x7F, body[1] if len(body) > 1 else 0)
        return body


async def modbus_read(conn, unit_id, table, address, count):
    _fc, req_cls, resp_cls, _max = MODBUS_TABLES[table]
    request = req_cls(address=address, count=count)
    body = await conn.request(
        unit_id, struct.pack(">B", request.function_code) + request.encode()
    )
    response = resp_cls()
    response.decode(body[1:])
    if table in BIT_TABLES:
        return [1 if bit else 0 for bit in response.bits[:count]]
    return list(response.registers)


async def modbus_readable(conn, unit_id, table, address):
    try:
        await modbus_read(conn, unit_id, table, address, 1)
        return True
    except ModbusException, ModbusNoResponse:
        return False


def parse_device_info(body):
    # 0x2B 0x0E read_code conformity more_follows next_obj count {id len data}*
    info = {}
    if len(body) < 7:
        return info
    count = body[6]
    pos = 7
    for _ in range(count):
        if pos + 2 > len(body):
            break
        object_id, length = body[pos], body[pos + 1]
        value = body[pos + 2 : pos + 2 + length]
        pos += 2 + length
        name = MEI_DEVICE_INFO_OBJECTS.get(object_id, "object_%d" % object_id)
        info[name] = value.decode("utf-8", errors="replace")
    return info


def parse_report_slave_id(body):
    """Return the device-specific Function 17 identifier as hex."""
    if (
        len(body) < 4
        or body[0] != 0x11
        or body[1] != len(body) - 2
        or body[-1] not in (0x00, 0xFF)
    ):
        return None
    return body[2:-1].hex()


async def modbus_probe_unit(host, port, timeout, unit_id):
    """Return a dict describing ``unit_id`` if something answers, else None."""
    result = {"id": unit_id}
    conn = ModbusConnection(host, port, timeout)
    try:
        alive = False
        try:
            # Read Device Identification, basic category, starting at object 0.
            body = await conn.request(unit_id, bytes((0x2B, 0x0E, 0x01, 0x00)))
            result["device_info"] = parse_device_info(body)
            alive = True
        except ModbusException as exc:
            alive = exc.code in PRESENCE_EXCEPTIONS
        except ModbusNoResponse:
            pass
        if not alive:
            # Many PLCs do not implement FC 43; any non-gateway answer to a
            # plain holding register read still proves the unit exists.
            try:
                await modbus_read(conn, unit_id, "HOLDING_REGISTERS", 0, 1)
                alive = True
            except ModbusException as exc:
                alive = exc.code in PRESENCE_EXCEPTIONS
            except ModbusNoResponse:
                pass
        if not alive:
            return None
        try:
            body = await conn.request(unit_id, bytes((0x11,)))
            report_slave_id = parse_report_slave_id(body)
            if report_slave_id is not None:
                result["report_slave_id"] = report_slave_id
        except ModbusException, ModbusNoResponse:
            pass
        return result
    except OSError as exc:
        logger.debug("unit %d: %s", unit_id, exc)
        return None
    finally:
        await conn.close()


async def modbus_map_table(conn, unit_id, table, max_address, stride):
    """Find contiguous readable ranges in one table via a strided probe."""
    blocks = []
    address = 0
    while address <= max_address:
        if not await modbus_readable(conn, unit_id, table, address):
            address += stride
            continue
        floor = blocks[-1][1] if blocks else 0
        start = address
        while start > floor and await modbus_readable(conn, unit_id, table, start - 1):
            start -= 1
        end = address + 1
        while end <= max_address and await modbus_readable(conn, unit_id, table, end):
            end += 1
        blocks.append((start, end))
        address = end + stride - (end % stride) if stride > 1 else end
    return blocks


async def modbus_dump_block(conn, unit_id, table, start, end):
    chunk = MODBUS_TABLES[table][3]
    values = []
    address = start
    while address < end:
        count = min(chunk, end - address)
        values.extend(await modbus_read(conn, unit_id, table, address, count))
        address += count
    return values


async def clone_modbus(args):
    semaphore = asyncio.Semaphore(args.concurrency)

    async def probe(unit_id):
        async with semaphore:
            return await modbus_probe_unit(
                args.host, args.modbus_port, args.timeout, unit_id
            )

    units = [u for u in await asyncio.gather(*(probe(u) for u in args.unit_ids)) if u]
    logger.info("Modbus: %d unit(s) answered: %s", len(units), [u["id"] for u in units])

    async def map_unit(unit):
        async with semaphore:
            conn = ModbusConnection(args.host, args.modbus_port, args.timeout)
            unit["blocks"] = []
            try:
                for table in MODBUS_TABLES:
                    logger.info("Modbus unit %d: scanning %s", unit["id"], table)
                    ranges = await modbus_map_table(
                        conn, unit["id"], table, args.max_address, args.stride
                    )
                    for start, end in ranges:
                        values = await modbus_dump_block(
                            conn, unit["id"], table, start, end
                        )
                        unit["blocks"].append(
                            {
                                "type": table,
                                "starting_address": start,
                                "size": end - start,
                                "values": values,
                            }
                        )
                        logger.info(
                            "Modbus unit %d: %s %d..%d",
                            unit["id"],
                            table,
                            start,
                            end - 1,
                        )
            finally:
                await conn.close()

    await asyncio.gather(*(map_unit(u) for u in units))
    return units


def snmp_value_for_template(value):
    """Return the databus string for a varbind value, or None if unsupported.

    Conpot feeds this string to ``syntax.clone()``, so emit raw numbers (not
    enum labels) and dotted OIDs (not MIB names).
    """
    # IpAddress is an OctetString subclass; handle it before generic strings.
    if isinstance(value, rfc1902.IpAddress):
        return ".".join(str(b) for b in value.asNumbers())
    if isinstance(value, univ.OctetString):
        try:
            text = value.asOctets().decode("utf-8")
        except UnicodeDecodeError:
            return None
        if text.isprintable():
            return text
        return None
    if isinstance(value, univ.Integer):
        return str(int(value))
    if isinstance(value, univ.ObjectIdentifier):
        return ".".join(str(x) for x in value)
    # With lookupMib=True pysnmp wraps OID-typed values (sysObjectID) in SMI.
    if isinstance(value, ObjectIdentity):
        return ".".join(str(x) for x in value.get_oid())
    return None


def snmp_engine_owned(mib, symbol):
    """True for objects the agent's SNMP engine serves itself.

    Conpot's pysnmp engine already exports these; registering them again from
    a template would collide, and their values are the scanner's own traffic.
    """
    if mib.startswith("SNMP-") or mib == "SNMPv2-MIB" and symbol.startswith("snmp"):
        return True
    return mib == "SNMPv2-MIB" and symbol.startswith("sysOR")


async def clone_snmp(args):
    engine = SnmpEngine()
    target = await UdpTransportTarget.create(
        (args.host, args.snmp_port), timeout=args.timeout, retries=1
    )
    results = []
    try:
        walker = bulk_walk_cmd(
            engine,
            CommunityData(args.community, mpModel=1),
            target,
            ContextData(),
            0,
            args.max_repetitions,
            ObjectType(ObjectIdentity(args.snmp_root)),
            lexicographicMode=False,
            lookupMib=True,
        )
        async for error_indication, error_status, error_index, var_binds in walker:
            if error_indication:
                logger.warning("SNMP: %s", error_indication)
                break
            if error_status:
                logger.warning(
                    "SNMP: %s at %s", error_status.prettyPrint(), error_index
                )
                break
            for name, value in var_binds:
                mib, symbol, _index = name.get_mib_symbol()
                oid = tuple(name.get_oid())
                instance = oid[len(name.get_mib_node().name) :]
                results.append(
                    {
                        "oid": ".".join(str(x) for x in oid),
                        "mib": mib,
                        "symbol": symbol,
                        "instance": ".".join(str(x) for x in instance),
                        "type": value.__class__.__name__,
                        "value": value.prettyPrint(),
                        "template_value": snmp_value_for_template(value),
                    }
                )
            if len(results) >= args.max_oids:
                logger.warning("SNMP: stopping at --max-oids %d", args.max_oids)
                break
    finally:
        engine.close_dispatcher()
    logger.info("SNMP: collected %d varbind(s)", len(results))
    return results


def toml_str(value):
    # JSON string escapes are a subset of TOML basic string escapes.
    return json.dumps(value, ensure_ascii=False)


def databus_key(*parts):
    key = "".join(p[:1].upper() + p[1:] for p in parts if p)
    key = re.sub(r"[^A-Za-z0-9_]", "_", key)
    return key[:1].lower() + key[1:]


def render_modbus_toml(units, port):
    device_info = {"VendorName": "", "ProductCode": "", "MajorMinorRevision": ""}
    for unit in units:
        found = unit.get("device_info") or {}
        if any(found.get(k) for k in device_info):
            device_info.update({k: found.get(k, "") for k in device_info})
            break
    for unit in units:
        if unit.get("report_slave_id"):
            device_info["ReportSlaveId"] = unit["report_slave_id"]
            break
    lines = [
        "[modbus]",
        "enabled = true",
        'host = "0.0.0.0"',
        "port = %d" % port,
        'mode = "tcp"',
        "delay = 100",
        "",
        "[modbus.device_info]",
    ]
    lines += ["%s = %s" % (k, toml_str(v)) for k, v in device_info.items()]
    databus = {}
    for unit in units:
        lines += ["", "[[modbus.slaves]]", "id = %d" % unit["id"], "blocks = ["]
        for n, block in enumerate(unit.get("blocks", [])):
            name = "memoryModbusSlave%dBlock%d" % (unit["id"], n)
            lines.append(
                '  { name = "%s", type = "%s", starting_address = %d, size = %d, '
                'content = "%s" },'
                % (name, block["type"], block["starting_address"], block["size"], name)
            )
            databus[name] = '{ value = "%s" }' % block["values"]
        lines.append("]")
    return "\n".join(lines) + "\n", databus


def render_snmp_toml(varbinds, port):
    by_mib = {}
    databus = {}
    for vb in varbinds:
        if vb["template_value"] is None or not vb["mib"]:
            continue
        if snmp_engine_owned(vb["mib"], vb["symbol"]):
            continue
        # Bare OIDs that no loaded MIB resolves cannot be registered by name.
        if not re.match(r"^[A-Za-z][A-Za-z0-9-]*$", vb["mib"]):
            continue
        if vb["mib"] == "SNMPv2-MIB" and vb["symbol"] == "sysUpTime":
            key = "Uptime"
            databus[key] = '{ function = "conpot.emulators.misc.uptime.Uptime" }'
        else:
            suffix = "" if vb["instance"] == "0" else vb["instance"]
            key = databus_key(vb["symbol"], suffix)
            databus[key] = toml_str(vb["template_value"])
        by_mib.setdefault(vb["mib"], []).append((vb["symbol"], vb["instance"], key))
    lines = ["[snmp]", "enabled = true", 'host = "0.0.0.0"', "port = %d" % port]
    for mib, symbols in by_mib.items():
        lines += ["", "[[snmp.mibs]]", "name = %s" % toml_str(mib), "symbols = ["]
        for symbol, instance, key in symbols:
            entry = "    { name = %s, value = %s" % (toml_str(symbol), toml_str(key))
            if instance != "0":
                entry += ", instance = %s" % toml_str(instance)
            lines.append(entry + " },")
        lines.append("]")
    return "\n".join(lines) + "\n", databus


def render_template_toml(host, protocols, databus):
    lines = [
        "[core.template]",
        'unit = "cloned device"',
        "vendor = %s" % toml_str("unknown"),
        "description = %s" % toml_str("Cloned from %s by conpot_cloner" % host),
        "protocols = [%s]" % ", ".join(toml_str(p) for p in protocols),
        'creator = "conpot_cloner"',
        "",
        "[core.databus.key_value_mappings]",
    ]
    lines += ["%s = %s" % (k, v) for k, v in databus.items()]
    return "\n".join(lines) + "\n"


def write_template(output_dir, host, report, args):
    os.makedirs(output_dir, exist_ok=True)
    databus = {}
    protocols = []
    if report.get("modbus"):
        text, extra = render_modbus_toml(report["modbus"], args.modbus_port)
        databus.update(extra)
        protocols.append("modbus")
        with open(os.path.join(output_dir, "modbus.toml"), "w") as f:
            f.write(text)
    if report.get("snmp"):
        text, extra = render_snmp_toml(report["snmp"], args.snmp_port)
        databus.update(extra)
        protocols.append("snmp")
        with open(os.path.join(output_dir, "snmp.toml"), "w") as f:
            f.write(text)
    with open(os.path.join(output_dir, "template.toml"), "w") as f:
        f.write(render_template_toml(host, protocols, databus))
    with open(os.path.join(output_dir, "report.json"), "w") as f:
        json.dump(report, f, indent=2)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("host", help="target address")
    parser.add_argument(
        "--protocols",
        default="modbus,snmp",
        help="comma-separated subset of: modbus,snmp (default: both)",
    )
    parser.add_argument("--modbus-port", type=int, default=502)
    parser.add_argument(
        "--unit-ids",
        type=parse_id_ranges,
        default=parse_id_ranges("1-247,255"),
        help="Modbus unit ids to probe, e.g. '1-10,255' (default: 1-247,255)",
    )
    parser.add_argument(
        "--max-address",
        type=int,
        default=65535,
        help="highest Modbus address to probe per table (default: 65535)",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=8,
        help="Modbus probe step; blocks shorter than this may be missed "
        "(default: 8)",
    )
    parser.add_argument("--snmp-port", type=int, default=161)
    parser.add_argument("--community", default="public")
    parser.add_argument("--snmp-root", default="1.3.6.1")
    parser.add_argument("--max-oids", type=int, default=5000)
    parser.add_argument("--max-repetitions", type=int, default=25)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="parallel Modbus connections (default: 8)",
    )
    parser.add_argument(
        "--output-dir",
        help="write template.toml, modbus.toml, snmp.toml and report.json here; "
        "otherwise print the JSON report to stdout",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


async def run(args):
    protocols = {p.strip() for p in args.protocols.split(",") if p.strip()}
    unknown = protocols - {"modbus", "snmp"}
    if unknown:
        raise SystemExit("unknown protocol(s): %s" % ", ".join(sorted(unknown)))
    if args.stride < 1 or not 0 <= args.max_address <= 65535:
        raise SystemExit("--stride must be >= 1 and --max-address in 0..65535")
    report = {"host": args.host}
    if "modbus" in protocols:
        report["modbus"] = await clone_modbus(args)
    if "snmp" in protocols:
        report["snmp"] = await clone_snmp(args)
    return report


def main(argv=None):
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    report = asyncio.run(run(args))
    if args.output_dir:
        write_template(args.output_dir, args.host, report, args)
        logger.info("Wrote template skeleton to %s", args.output_dir)
    else:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
