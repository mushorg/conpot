# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# IEC 61850-8-1 GOOSE APDU helpers. The pyasn1 field layout is adapted from
# GooseStalker goose/goose_pdu.py (MIT License, Copyright (c) 2016 Keith Gray /
# Cutaway Security) — APDU schema reference only; no L2 or attack tooling.

"""Minimal IEC 61850-8-1 GOOSE PDU encode/decode via pyasn1."""

from __future__ import annotations

import struct
import time
from typing import Any

from pyasn1.codec.ber import decoder, encoder
from pyasn1.type import char, namedtype, tag, univ

MAX_APDU_LEN = 65535


class UtcTime(univ.OctetString):
    """IEC 61850 UtcTime: 8 octets (seconds + fraction + quality)."""

    subtypeSpec = univ.OctetString.subtypeSpec


class Data(univ.Choice):
    pass


Data.componentType = namedtype.NamedTypes(
    namedtype.NamedType(
        "boolean",
        univ.Boolean().subtype(
            implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 3)
        ),
    ),
    namedtype.NamedType(
        "integer",
        univ.Integer().subtype(
            implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 5)
        ),
    ),
)


class AllData(univ.SequenceOf):
    componentType = Data()


class IECGoosePDU(univ.Sequence):
    """GOOSE PDU as APPLICATION 1 IMPLICIT SEQUENCE (tag 0x61)."""

    tagSet = univ.Sequence.tagSet.tagImplicitly(
        tag.Tag(tag.tagClassApplication, tag.tagFormatConstructed, 1)
    )
    componentType = namedtype.NamedTypes(
        namedtype.NamedType(
            "gocbRef",
            char.VisibleString().subtype(
                implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0)
            ),
        ),
        namedtype.NamedType(
            "timeAllowedtoLive",
            univ.Integer().subtype(
                implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1)
            ),
        ),
        namedtype.NamedType(
            "datSet",
            char.VisibleString().subtype(
                implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2)
            ),
        ),
        namedtype.OptionalNamedType(
            "goID",
            char.VisibleString().subtype(
                implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 3)
            ),
        ),
        namedtype.NamedType(
            "t",
            UtcTime().subtype(
                implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 4)
            ),
        ),
        namedtype.NamedType(
            "stNum",
            univ.Integer().subtype(
                implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 5)
            ),
        ),
        namedtype.NamedType(
            "sqNum",
            univ.Integer().subtype(
                implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 6)
            ),
        ),
        namedtype.NamedType(
            "test",
            univ.Boolean().subtype(
                implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 7)
            ),
        ),
        namedtype.NamedType(
            "confRev",
            univ.Integer().subtype(
                implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 8)
            ),
        ),
        namedtype.NamedType(
            "ndsCom",
            univ.Boolean().subtype(
                implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 9)
            ),
        ),
        namedtype.NamedType(
            "numDatSetEntries",
            univ.Integer().subtype(
                implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 10)
            ),
        ),
        namedtype.NamedType(
            "allData",
            AllData().subtype(
                implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 11)
            ),
        ),
    )


def encode_utc_time(seconds: float | None = None) -> bytes:
    """Encode wall-clock time as IEC 61850 UtcTime (8 bytes)."""
    if seconds is None:
        seconds = time.time()
    whole = int(seconds)
    frac = int((seconds - whole) * (2**24)) & 0xFFFFFF
    quality = 0x0A  # clock synchronized, accuracy unspecified
    return (
        struct.pack("!I", whole & 0xFFFFFFFF)
        + struct.pack("!I", frac)[1:]
        + bytes([quality])
    )


def encode_goose_apdu(
    *,
    gocb_ref: str,
    time_allowed_to_live: int,
    dat_set: str,
    go_id: str,
    st_num: int,
    sq_num: int,
    conf_rev: int,
    all_data: list[Any] | None = None,
    test: bool = False,
    nds_com: bool = False,
    timestamp: float | None = None,
) -> bytes:
    """BER-encode a GOOSE APDU (APPLICATION 1)."""
    entries = list(all_data or [])
    pdu = IECGoosePDU()
    pdu.setComponentByName("gocbRef", gocb_ref)
    pdu.setComponentByName("timeAllowedtoLive", int(time_allowed_to_live))
    pdu.setComponentByName("datSet", dat_set)
    pdu.setComponentByName("goID", go_id)
    pdu.setComponentByName("t", encode_utc_time(timestamp))
    pdu.setComponentByName("stNum", int(st_num))
    pdu.setComponentByName("sqNum", int(sq_num))
    pdu.setComponentByName("test", bool(test))
    pdu.setComponentByName("confRev", int(conf_rev))
    pdu.setComponentByName("ndsCom", bool(nds_com))
    pdu.setComponentByName("numDatSetEntries", len(entries))
    pdu.setComponentByName("allData")
    all_data_comp = pdu.getComponentByName("allData")
    for idx, value in enumerate(entries):
        item = Data()
        if isinstance(value, bool):
            item.setComponentByName("boolean", value)
        elif isinstance(value, int):
            item.setComponentByName("integer", value)
        else:
            raise ValueError(
                f"unsupported allData entry type at index {idx}: {type(value)}"
            )
        all_data_comp.setComponentByPosition(idx, item)
    encoded = encoder.encode(pdu)
    if len(encoded) > MAX_APDU_LEN:
        raise ValueError("GOOSE APDU too large")
    return encoded


def _decode_all_data(all_data_comp) -> list[Any]:
    values: list[Any] = []
    if all_data_comp is None:
        return values
    for idx in range(len(all_data_comp)):
        item = all_data_comp.getComponentByPosition(idx)
        name = item.getName()
        if name == "boolean":
            values.append(bool(item.getComponent()))
        elif name == "integer":
            values.append(int(item.getComponent()))
        else:
            values.append(None)
    return values


def decode_goose_apdu(data: bytes) -> dict[str, Any]:
    """Decode a GOOSE APDU; raise ValueError on malformed input."""
    if not data:
        raise ValueError("empty GOOSE APDU")
    if len(data) > MAX_APDU_LEN:
        raise ValueError("GOOSE APDU too large")
    try:
        pdu, rest = decoder.decode(data, asn1Spec=IECGoosePDU())
    except Exception as exc:
        raise ValueError(f"GOOSE APDU decode failed: {exc}") from exc
    if rest:
        raise ValueError("trailing bytes after GOOSE APDU")

    go_id = None
    if pdu.getComponentByName("goID") is not None:
        go_id = str(pdu.getComponentByName("goID"))

    t_raw = bytes(pdu.getComponentByName("t"))
    all_data = _decode_all_data(pdu.getComponentByName("allData"))
    return {
        "gocb_ref": str(pdu.getComponentByName("gocbRef")),
        "time_allowed_to_live": int(pdu.getComponentByName("timeAllowedtoLive")),
        "dat_set": str(pdu.getComponentByName("datSet")),
        "go_id": go_id,
        "t": t_raw,
        "st_num": int(pdu.getComponentByName("stNum")),
        "sq_num": int(pdu.getComponentByName("sqNum")),
        "test": bool(pdu.getComponentByName("test")),
        "conf_rev": int(pdu.getComponentByName("confRev")),
        "nds_com": bool(pdu.getComponentByName("ndsCom")),
        "num_dat_set_entries": int(pdu.getComponentByName("numDatSetEntries")),
        "all_data": all_data,
    }
