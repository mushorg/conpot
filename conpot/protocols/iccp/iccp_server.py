# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""ICCP / TASE.2 (IEC 60870-6) called-endpoint honeypot over ISO-on-TCP."""

from __future__ import annotations

import asyncio
import logging
import socket
from struct import unpack

import conpot.core as conpot_core
from conpot.core.protocol_wrapper import conpot_protocol
from conpot.protocols.iccp.cotp import (
    TPDU_CC,
    TPDU_CR,
    TPDU_DT,
    COTP,
    COTPConnection,
    COTPError,
    pack_dt_tpkt,
)
from conpot.protocols.iccp.iso_upper import (
    build_initiate_accept,
    extract_mms_pdu,
    is_session_connect,
    wrap_presentation_user,
    wrap_session_data,
)
from conpot.protocols.iccp.mms import (
    SVC_GET_NAME_LIST,
    SVC_IDENTIFY,
    SVC_READ,
    PointValue,
    build_conclude_response,
    build_confirmed_error,
    build_get_name_list_response,
    build_identify_response,
    build_read_response,
    parse_get_name_list_scope,
    parse_mms_pdu,
    parse_read_variable_names,
)
from conpot.protocols.iccp.tpkt import TPKT, TPKTError
from conpot.utils.asyncio_serve import serve_tcp_sync_handler

logger = logging.getLogger(__name__)


@conpot_protocol
class ICCPServer(object):
    def __init__(self, template, template_directory, args):
        self.template = template
        self.timeout = float(template.get("timeout", 5))
        self.vendor = str(template.get("vendor", "Conpot"))
        self.model = str(template.get("model", "ICCP-TASE2"))
        self.revision = str(template.get("revision", "1.0"))
        self.domain = str(template.get("domain", "VCC"))
        self.points: dict[str, PointValue] = {}
        for entry in template.get("points", []) or []:
            name = str(entry["name"])
            kind = str(entry.get("type", "integer"))
            if kind == "boolean":
                value = bool(entry.get("value", False))
            elif kind == "float":
                value = float(entry.get("value", 0.0))
            else:
                kind = "integer"
                value = int(entry.get("value", 0))
            self.points[name] = PointValue(name=name, kind=kind, value=value)
        self.databus = conpot_core.get_databus()
        self.server = None
        logger.info("Conpot ICCP/TASE.2 initialized (domain=%s)", self.domain)

    def _recv_tpkt(self, sock: socket.socket) -> bytes | None:
        header = sock.recv(4, socket.MSG_WAITALL)
        if not header:
            return None
        if len(header) < 4:
            raise TPKTError("short TPKT header")
        _, _, length = unpack("!BBH", header)
        if length < 4:
            raise TPKTError("invalid TPKT length")
        rest = sock.recv(length - 4, socket.MSG_WAITALL)
        if len(rest) < length - 4:
            raise TPKTError("short TPKT payload")
        return header + rest

    def _send_bytes(self, sock: socket.socket, payload: bytes) -> None:
        sock.sendall(payload)

    def _send_mms_data(self, sock: socket.socket, mms_pdu: bytes) -> None:
        presentation = wrap_presentation_user(mms_pdu)
        session = wrap_session_data(presentation)
        self._send_bytes(sock, pack_dt_tpkt(session))

    def _handle_mms(
        self, sock: socket.socket, session, mms_pdu: bytes, request_hex: str
    ) -> None:
        kind, payload = parse_mms_pdu(mms_pdu)
        response = None
        event_request = request_hex
        event_response = None

        if kind == "initiate_request":
            accept = build_initiate_accept()
            packed = pack_dt_tpkt(accept)
            self._send_bytes(sock, packed)
            session.log_event(
                event_type="REQUEST",
                request=event_request,
                response=packed.hex(),
                service="mms_initiate",
            )
            return

        if kind == "conclude_request":
            response = build_conclude_response()
            self._send_mms_data(sock, response)
            session.log_event(
                event_type="REQUEST",
                request=event_request,
                response=response.hex(),
                service="mms_conclude",
            )
            return

        if kind == "confirmed_request":
            req = payload
            if req.service == SVC_IDENTIFY:
                response = build_identify_response(
                    req.invoke_id, self.vendor, self.model, self.revision
                )
                service = "mms_identify"
            elif req.service == SVC_GET_NAME_LIST:
                scope, domain_id = parse_get_name_list_scope(req.body)
                if scope == "vmd":
                    names = [self.domain]
                elif scope == "domain":
                    if domain_id and domain_id != self.domain:
                        names = []
                    else:
                        names = sorted(self.points.keys())
                else:
                    names = sorted(self.points.keys())
                response = build_get_name_list_response(req.invoke_id, names)
                service = "mms_get_name_list"
            elif req.service == SVC_READ:
                refs = parse_read_variable_names(req.body)
                results: list[PointValue | None] = []
                if not refs:
                    # No parseable names — return all configured points as success list empty error
                    results = [None]
                for domain, item in refs:
                    if domain and domain != self.domain:
                        results.append(None)
                    else:
                        results.append(self.points.get(item))
                response = build_read_response(req.invoke_id, results)
                service = "mms_read"
            else:
                response = build_confirmed_error(req.invoke_id)
                service = f"mms_service_{req.service}"

            self._send_mms_data(sock, response)
            session.log_event(
                event_type="REQUEST",
                request=event_request,
                response=response.hex(),
                service=service,
            )
            return

        session.log_event(
            event_type="REQUEST",
            request=event_request,
            error="unsupported_mms_pdu",
        )

    def handle(self, sock, addr):
        sock.settimeout(self.timeout)
        session = conpot_core.get_session(
            "iccp",
            addr[0],
            addr[1],
            sock.getsockname()[0],
            sock.getsockname()[1],
        )
        logger.info(
            "New ICCP connection from %s:%s. (%s)", addr[0], addr[1], session.id
        )
        session.log_event(event_type="NEW_CONNECTION")
        associated = False

        try:
            while True:
                raw = self._recv_tpkt(sock)
                if raw is None:
                    break
                try:
                    tpkt = TPKT().parse(raw)
                    cotp = COTP().parse(tpkt.payload)
                except (TPKTError, COTPError) as exc:
                    logger.debug("ICCP framing error from %s: %s", addr, exc)
                    session.log_event(error=str(exc))
                    break

                if cotp.tpdu_type == TPDU_CR:
                    cr = COTPConnection().dissect(cotp.payload)
                    cc = COTPConnection(
                        dst_ref=cr.src_ref,
                        src_ref=0x0001,
                        opt_field=0,
                        src_tsap=cr.dst_tsap,
                        dst_tsap=cr.src_tsap,
                        tpdu_size=cr.tpdu_size or 0x0A,
                    )
                    cc_payload = cc.assemble_cc()
                    cc_tpdu = COTP(tpdu_type=TPDU_CC, payload=cc_payload).pack()
                    self._send_bytes(sock, TPKT(payload=cc_tpdu).pack())
                    session.log_event(
                        event_type="REQUEST",
                        request=raw.hex(),
                        response=TPKT(payload=cc_tpdu).pack().hex(),
                        service="cotp_cr",
                    )
                    continue

                if cotp.tpdu_type != TPDU_DT:
                    session.log_event(
                        event_type="REQUEST",
                        request=raw.hex(),
                        error=f"unsupported_cotp_{cotp.tpdu_type:#x}",
                    )
                    break

                user = cotp.trailer if cotp.trailer else cotp.payload
                # DT user data sits after the 3-byte DT header; our parser puts
                # remaining bytes in trailer when length==2.
                if not user and cotp.payload:
                    user = cotp.payload

                if is_session_connect(user) or not associated:
                    mms = extract_mms_pdu(user)
                    if mms is not None:
                        self._handle_mms(sock, session, mms, raw.hex())
                        associated = True
                        continue
                    if is_session_connect(user):
                        # CONNECT without extractable MMS — still send accept.
                        accept = build_initiate_accept()
                        self._send_bytes(sock, pack_dt_tpkt(accept))
                        associated = True
                        session.log_event(
                            event_type="REQUEST",
                            request=raw.hex(),
                            response=pack_dt_tpkt(accept).hex(),
                            service="mms_initiate",
                        )
                        continue

                mms = extract_mms_pdu(user)
                if mms is None:
                    session.log_event(
                        event_type="REQUEST",
                        request=raw.hex(),
                        error="mms_pdu_not_found",
                    )
                    continue
                self._handle_mms(sock, session, mms, raw.hex())

        except socket.timeout:
            logger.debug("ICCP timeout from %s:%s (%s)", addr[0], addr[1], session.id)
        except socket.error as err:
            logger.debug(
                "ICCP socket error from %s:%s (%s): %s",
                addr[0],
                addr[1],
                session.id,
                err,
            )
        finally:
            session.log_event(event_type="CONNECTION_LOST")
            try:
                sock.close()
            except Exception:
                pass

    async def start(self, host, port):
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        await serve_tcp_sync_handler(
            host,
            port,
            self,
            stop_event=self._stop,
            ready_event=self._ready,
            name="ICCPServer",
        )

    def stop(self):
        if hasattr(self, "_stop"):
            self._stop.set()
