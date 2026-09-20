# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""Sync EtherNet/IP encapsulation + CIP dispatch using cm-ethernetip.

Socket I/O stays in :mod:`enip_server`; this module is the codec / object model.
"""

from __future__ import annotations

import logging
import socket
import struct

from ethernetip.cip.attribute import AttributeAccess, CipAttribute
from ethernetip.cip.cip_class import CipClass
from ethernetip.cip.cpf import CpfItem, CpfItemType, encode_cpf
from ethernetip.cip.data_types import CipDataType
from ethernetip.cip.dispatcher import CipDispatcher
from ethernetip.cip.encapsulation import (
    SIZE as HEADER_SIZE,
    EncapsulationCommand,
    EncapsulationHeader,
    EncapsulationStatus,
)
from ethernetip.cip.identity_info import IdentityInfo
from ethernetip.cip import mr_codec
from ethernetip.cip import standard_services as std
from ethernetip.cip.path import CipPath
from ethernetip.device.identity_object import create_identity_class
from ethernetip.protocol.messages import (
    EncapsulationMessage,
    EncapsulationMessageManager,
    ListIdentityMessage,
    ListServicesMessage,
    NopMessage,
    RegisterSessionMessage,
    SendRRDataMessage,
    SendUnitDataMessage,
    UnregisterSessionMessage,
)
from ethernetip.protocol.session_manager import SessionManager

logger = logging.getLogger(__name__)

# Wire sizes for CIP atomic types used in template tags.
_TYPE_WIRE = {
    "BOOL": (CipDataType.BOOL, 1, lambda v: bytes([1 if bool(v) else 0])),
    "SINT": (CipDataType.SINT, 1, lambda v: struct.pack("<b", int(v))),
    "INT": (CipDataType.INT, 2, lambda v: struct.pack("<h", int(v))),
    "DINT": (CipDataType.DINT, 4, lambda v: struct.pack("<i", int(v))),
    "REAL": (CipDataType.REAL, 4, lambda v: struct.pack("<f", float(v))),
}


def identity_from_config(config) -> IdentityInfo:
    """Map template device_info (incl. ProductRevision INT) to IdentityInfo."""
    rev = int(config.product_rev)
    return IdentityInfo(
        vendor_id=int(config.vendor_id),
        device_type=int(config.device_type),
        product_code=int(config.product_code),
        major_revision=(rev >> 8) & 0xFF,
        minor_revision=rev & 0xFF,
        serial_number=int(config.serial_number),
        product_name=str(config.product_name),
    )


def _parse_addr(addr: str) -> tuple[int, int, int]:
    parts = [int(p) for p in addr.split("/")]
    if len(parts) != 3:
        raise AssertionError("Tag addr must be cls/ins/att: %r" % addr)
    cls, ins, att = parts
    assert ins > 0, "Cannot specify the Class' instance for a tag's address"
    return cls, ins, att


def _initial_attr_data(
    tag_type: str, size: int, value: str
) -> tuple[CipDataType, bytes]:
    tag_type = tag_type.upper()
    if tag_type == "SSTRING":
        text = str(value)
        # Length byte + payload; pad to configured capacity when larger than value.
        payload = text.encode("ascii", errors="replace")[:255]
        capacity = max(size, len(payload))
        data = bytearray(1 + capacity)
        data[0] = len(payload)
        data[1 : 1 + len(payload)] = payload
        return CipDataType.SHORT_STRING, bytes(data)
    if tag_type == "STRING":
        text = str(value)
        payload = text.encode("ascii", errors="replace")
        capacity = max(size, len(payload))
        data = bytearray(2 + capacity)
        struct.pack_into("<H", data, 0, len(payload))
        data[2 : 2 + len(payload)] = payload
        return CipDataType.STRING, bytes(data)
    if tag_type not in _TYPE_WIRE:
        raise AssertionError(
            "Invalid tag type; must be one of %r"
            % (list(_TYPE_WIRE) + ["SSTRING", "STRING"])
        )
    cip_type, elem_size, encode = _TYPE_WIRE[tag_type]
    elem = encode(value)
    if size <= 1:
        return cip_type, elem
    return cip_type, elem * size


def build_dispatcher(identity: IdentityInfo, tags) -> CipDispatcher:
    """Register Identity plus template tag classes/instances/attributes."""
    dispatcher = CipDispatcher()
    dispatcher.register_class(create_identity_class(identity))

    # class_code -> CipClass
    classes: dict[int, CipClass] = {}

    for tag in tags:
        if not tag.addr:
            continue
        cls_id, ins_id, att_id = _parse_addr(tag.addr)
        cip_type, initial = _initial_attr_data(tag.type, tag.size, tag.value)

        cip_class = classes.get(cls_id)
        if cip_class is None:
            cip_class = CipClass(cls_id, "TagClass_%d" % cls_id)
            cip_class.add_standard_instance_services()
            classes[cls_id] = cip_class
            dispatcher.register_class(cip_class)

        instance = cip_class.get_instance(ins_id)
        if instance is None:
            instance = cip_class.create_instance(ins_id)

        existing = instance.get_attribute(att_id)
        if existing is not None:
            assert existing.data_type is cip_type and existing.data_length == len(
                initial
            ), ("Incompatible Attribute types for tag %r" % tag.name)
            continue

        access = (
            AttributeAccess.GET_SINGLE
            | AttributeAccess.SET_SINGLE
            | AttributeAccess.GET_ALL
        )
        instance.add_attribute(CipAttribute(att_id, cip_type, access, initial))
        logger.debug(
            "Creating tag: %-14s@%-10s %s[%d]",
            tag.name,
            tag.addr,
            cip_type.name,
            tag.size,
        )

    return dispatcher


class EnipProtocol:
    """Parse encapsulation frames and build replies via a CipDispatcher."""

    def __init__(self, dispatcher: CipDispatcher, identity: IdentityInfo, port: int):
        self.dispatcher = dispatcher
        self.identity = identity
        self.port = port
        self.sessions = SessionManager()
        self._manager = EncapsulationMessageManager()

    def try_parse(self, data: bytes, remote_addr: tuple[str, int]):
        return self._manager.try_parse(data, remote_addr)

    def dispatch_message(
        self, msg, session_handle: int, local_addr: str
    ) -> tuple[bytes | None, int, bool]:
        """Route a parsed message.

        Returns ``(response_bytes_or_None, session_handle, is_nop)``.
        """
        if isinstance(msg, NopMessage):
            return None, session_handle, True

        if isinstance(msg, ListIdentityMessage):
            return (
                self._handle_list_identity(msg, local_addr),
                session_handle,
                False,
            )

        if isinstance(msg, ListServicesMessage):
            return self._handle_list_services(msg), session_handle, False

        if isinstance(msg, RegisterSessionMessage):
            reply = self._handle_register_session(msg)
            new_handle = EncapsulationHeader.parse(reply).session_handle
            return reply, new_handle, False

        if isinstance(msg, UnregisterSessionMessage):
            self.sessions.unregister(msg.session_handle)
            return None, 0, False

        if isinstance(msg, SendRRDataMessage):
            return (
                self._handle_send_rr_data(msg, session_handle),
                session_handle,
                False,
            )

        if isinstance(msg, SendUnitDataMessage):
            return (
                self._handle_send_unit_data(msg, session_handle),
                session_handle,
                False,
            )

        if isinstance(msg, EncapsulationMessage):
            if msg.header.command == EncapsulationCommand.LIST_INTERFACES:
                return (
                    self._handle_list_interfaces(msg),
                    session_handle,
                    False,
                )
            return (
                _build_error_response(
                    msg.header.command,
                    msg.header.session_handle,
                    msg.header.sender_context,
                    EncapsulationStatus.INVALID_COMMAND,
                ),
                session_handle,
                False,
            )

        return None, session_handle, False

    def _handle_list_identity(self, msg: ListIdentityMessage, local_addr: str) -> bytes:
        identity_data = bytearray(512)
        offset = 0
        struct.pack_into("<H", identity_data, offset, 1)
        offset += 2
        struct.pack_into(">hH", identity_data, offset, 2, self.port)
        offset += 4
        try:
            addr_bytes = socket.inet_aton(local_addr)
        except OSError:
            addr_bytes = socket.inet_aton("0.0.0.0")
        identity_data[offset : offset + 4] = addr_bytes
        offset += 4
        offset += 8  # sin_zero

        id_path = CipPath(class_id=0x01, instance_id=1)
        get_all = self.dispatcher.dispatch(std.GET_ATTRIBUTE_ALL, id_path, b"")
        if get_all.status.is_success and get_all.data:
            identity_data[offset : offset + len(get_all.data)] = get_all.data
            offset += len(get_all.data)

        identity_data[offset] = 0xFF
        offset += 1

        items = [CpfItem(CpfItemType.CIP_IDENTITY, bytes(identity_data[:offset]))]
        return _build_response(
            EncapsulationCommand.LIST_IDENTITY,
            msg.session_handle,
            msg.sender_context,
            encode_cpf(items),
        )

    def _handle_list_services(self, msg: ListServicesMessage) -> bytes:
        service_data = bytearray(20)
        struct.pack_into("<HH", service_data, 0, 1, 0x0120)
        service_data[4:20] = b"Communications\x00\x00"
        items = [CpfItem(CpfItemType.LIST_SERVICES_RESPONSE, bytes(service_data))]
        return _build_response(
            EncapsulationCommand.LIST_SERVICES,
            msg.session_handle,
            msg.sender_context,
            encode_cpf(items),
        )

    def _handle_list_interfaces(self, msg: EncapsulationMessage) -> bytes:
        # Empty interface list: CPF item count = 0.
        return _build_response(
            EncapsulationCommand.LIST_INTERFACES,
            msg.header.session_handle,
            msg.header.sender_context,
            struct.pack("<H", 0),
        )

    def _handle_register_session(self, msg: RegisterSessionMessage) -> bytes:
        handle = self.sessions.register()
        reply = RegisterSessionMessage(
            session_handle=handle,
            status=EncapsulationStatus.SUCCESS,
            sender_context=msg.sender_context,
            protocol_version=1,
            options_flags=0,
        )
        return reply.to_bytes()

    def _handle_send_rr_data(
        self, msg: SendRRDataMessage, session_handle: int
    ) -> bytes:
        if session_handle == 0 or not self.sessions.is_valid(msg.session_handle):
            return _build_error_response(
                EncapsulationCommand.SEND_RR_DATA,
                msg.session_handle,
                msg.sender_context,
                EncapsulationStatus.INVALID_SESSION_HANDLE,
            )

        result = mr_codec.try_parse_request(msg.cip_data)
        if result is None:
            return _build_error_response(
                EncapsulationCommand.SEND_RR_DATA,
                msg.session_handle,
                msg.sender_context,
                EncapsulationStatus.INCORRECT_DATA,
            )

        service_code, path, data = result
        cip_response = self.dispatcher.dispatch(service_code, path, data)
        mr_buf = bytearray(4096)
        mr_len = cip_response.encode(mr_buf)
        reply_cpf = encode_cpf(
            [
                CpfItem(CpfItemType.NULL_ADDRESS, b""),
                CpfItem(CpfItemType.UNCONNECTED_DATA, bytes(mr_buf[:mr_len])),
            ]
        )
        response_payload = bytearray(6 + len(reply_cpf))
        response_payload[6:] = reply_cpf
        return _build_response(
            EncapsulationCommand.SEND_RR_DATA,
            session_handle,
            msg.sender_context,
            bytes(response_payload),
        )

    def _handle_send_unit_data(
        self, msg: SendUnitDataMessage, session_handle: int
    ) -> bytes:
        if session_handle == 0 or not self.sessions.is_valid(msg.session_handle):
            return _build_error_response(
                EncapsulationCommand.SEND_UNIT_DATA,
                msg.session_handle,
                msg.sender_context,
                EncapsulationStatus.INVALID_SESSION_HANDLE,
            )
        if len(msg.cip_data) < 2:
            return _build_error_response(
                EncapsulationCommand.SEND_UNIT_DATA,
                msg.session_handle,
                msg.sender_context,
                EncapsulationStatus.INCORRECT_DATA,
            )
        (seq_count,) = struct.unpack_from("<H", msg.cip_data, 0)
        result = mr_codec.try_parse_request(msg.cip_data[2:])
        if result is None:
            return _build_error_response(
                EncapsulationCommand.SEND_UNIT_DATA,
                msg.session_handle,
                msg.sender_context,
                EncapsulationStatus.INCORRECT_DATA,
            )
        service_code, path, data = result
        cip_response = self.dispatcher.dispatch(service_code, path, data)
        mr_buf = bytearray(4096)
        mr_len = cip_response.encode(mr_buf)
        reply = SendUnitDataMessage(
            session_handle=session_handle,
            status=EncapsulationStatus.SUCCESS,
            sender_context=msg.sender_context,
            connection_id=msg.connection_id,
            cip_data=struct.pack("<H", seq_count) + bytes(mr_buf[:mr_len]),
        )
        return reply.to_bytes()


def _build_response(
    command: EncapsulationCommand,
    session_handle: int,
    sender_context: int,
    payload: bytes,
) -> bytes:
    reply = EncapsulationHeader(
        command=command,
        length=len(payload),
        session_handle=session_handle,
        sender_context=sender_context,
    )
    buf = bytearray(HEADER_SIZE + len(payload))
    reply.write_to(buf)
    buf[HEADER_SIZE:] = payload
    return bytes(buf)


def _build_error_response(
    command: EncapsulationCommand,
    session_handle: int,
    sender_context: int,
    status: EncapsulationStatus,
) -> bytes:
    reply = EncapsulationHeader(
        command=command,
        session_handle=session_handle,
        status=status,
        sender_context=sender_context,
    )
    buf = bytearray(HEADER_SIZE)
    reply.write_to(buf)
    return bytes(buf)
