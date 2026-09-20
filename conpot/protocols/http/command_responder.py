# Copyright (C) 2013  Daniel creo Haslinger <creo-conpot@blackmesa.at>
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
import logging
import os
import random
import re
import time
from datetime import datetime

import aiohttp
from aiohttp import hdrs, web
from lxml import etree

import conpot.core as conpot_core
from conpot.utils.networking import str_to_bytes

logger = logging.getLogger(__name__)

SUPPORTED_METHODS = frozenset({"GET", "POST", "HEAD", "OPTIONS", "TRACE"})
HTTP_STATE_KEY = web.AppKey("http_state", object)


def substitute_template_fields(payload):
    if isinstance(payload, bytes):
        payload = payload.decode()
    databus = conpot_core.get_databus()
    pattern = r'<condata\s+source="([^"]+)"\s+key="([^"]+)"\s*/>'

    def replacer(match):
        source = match.group(1)
        key = match.group(2)
        if source == "databus":
            result = databus.get_value(key)
            return str(result) if result is not None else match.group(0)
        elif source == "eval":
            try:
                return str(eval(key))
            except Exception as e:
                logger.exception(e)
                return match.group(0)
        return match.group(0)

    return re.sub(pattern, replacer, payload)


def _frame_chunked(payload, chunks, trailers):
    """Build a chunked-transfer body with optional trailers (wire bytes)."""
    if isinstance(payload, str):
        payload = payload.encode()
    chunk_list = chunks.split(",")
    parts = []
    pointer = 0
    for cwidth in chunk_list:
        cwidth = int(cwidth)
        parts.append(format(cwidth, "x").upper().encode("ascii") + b"\r\n")
        parts.append(payload[pointer : pointer + cwidth] + b"\r\n")
        pointer += cwidth
    if len(payload) > pointer:
        remaining = len(payload) - pointer
        parts.append(format(remaining, "x").upper().encode("ascii") + b"\r\n")
        parts.append(payload[pointer:] + b"\r\n")
    parts.append(b"0\r\n")
    for trailer in trailers:
        name, value = trailer[0], trailer[1]
        parts.append(f"{name}: {value}\r\n".encode("ascii", errors="replace"))
    parts.append(b"\r\n")
    return b"".join(parts)


class HttpServerState:
    """Template-backed HTTP honeypot configuration (test surface: cmd_responder.httpd)."""

    def __init__(self, template, docpath):
        self.docpath = docpath
        self.allow_reuse_address = True
        self.server_port = None

        self.update_header_date = True
        self.disable_method_head = False
        self.disable_method_trace = False
        self.disable_method_options = False
        self.tarpit = "0"
        self.protocol_version = "HTTP/1.1"

        self.configuration = etree.parse(template)

        xml_config = self.configuration.xpath("//http/global/config/*")
        if xml_config:
            for entity in xml_config:
                name = entity.attrib["name"]
                if name == "protocol_version":
                    self.protocol_version = entity.text
                elif name == "update_header_date":
                    if entity.text.lower() == "false":
                        self.update_header_date = False
                    elif entity.text.lower() == "true":
                        self.update_header_date = True
                elif name == "disable_method_head":
                    self.disable_method_head = entity.text.lower() == "true"
                elif name == "disable_method_trace":
                    self.disable_method_trace = entity.text.lower() == "true"
                elif name == "disable_method_options":
                    self.disable_method_options = entity.text.lower() == "true"
                elif name == "tarpit":
                    if entity.text:
                        self.tarpit = self.config_sanitize_tarpit(entity.text)

        self.global_headers = []
        xml_headers = self.configuration.xpath("//http/global/headers/*")
        if xml_headers:
            for header in xml_headers:
                if (
                    header.attrib["name"].lower() == "date"
                    and self.update_header_date is True
                ):
                    self.global_headers.append(
                        (
                            header.attrib["name"],
                            time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime()),
                        )
                    )
                else:
                    self.global_headers.append((header.attrib["name"], header.text))

    def config_sanitize_tarpit(self, value):
        if value is not None:
            x, _, y = value.partition(";")
            try:
                float(x)
            except ValueError:
                logger.error("Invalid tarpit value: '%s'. Assuming no latency.", value)
                return "0;0"
            try:
                float(y)
                return value
            except ValueError:
                return x
        return "0;0"

    async def do_tarpit(self, delay):
        lbound, _, ubound = delay.partition(";")
        if not lbound:
            return
        elif not ubound:
            await asyncio.sleep(float(lbound))
        else:
            await asyncio.sleep(random.uniform(float(lbound), float(ubound)))

    def get_entity_headers(self, rqfilename, headers):
        xml_headers = self.configuration.xpath(
            '//http/htdocs/node[@name="' + rqfilename + '"]/headers/*'
        )
        if xml_headers:
            for header in xml_headers:
                headers.append((header.attrib["name"], header.text))
        return headers

    def get_trigger_appendix(self, rqfilename, rqparams):
        xml_triggers = self.configuration.xpath(
            '//http/htdocs/node[@name="' + rqfilename + '"]/triggers/*'
        )
        if xml_triggers:
            paramlist = rqparams.split("&")
            for triggers in xml_triggers:
                triggerlist = triggers.text.split(";")
                trigger_missed = False
                for trigger in triggerlist:
                    if trigger not in paramlist:
                        trigger_missed = True
                if not trigger_missed:
                    return triggers.attrib["appendix"]
        return None

    def get_entity_trailers(self, rqfilename):
        trailers = []
        xml_trailers = self.configuration.xpath(
            '//http/htdocs/node[@name="' + rqfilename + '"]/trailers/*'
        )
        if xml_trailers:
            for trailer in xml_trailers:
                trailers.append((trailer.attrib["name"], trailer.text))
        return trailers

    def get_status_headers(self, status, headers):
        xml_headers = self.configuration.xpath(
            '//http/statuscodes/status[@name="' + str(status) + '"]/headers/*'
        )
        if xml_headers:
            for header in xml_headers:
                headers.append((header.attrib["name"], header.text))
        return headers

    def get_status_trailers(self, status):
        trailers = []
        xml_trailers = self.configuration.xpath(
            '//http/statuscodes/status[@name="' + str(status) + '"]/trailers/*'
        )
        if xml_trailers:
            for trailer in xml_trailers:
                trailers.append((trailer.attrib["name"], trailer.text))
        return trailers

    async def load_status(
        self,
        status,
        requeststring,
        requestheaders,
        headers,
        method="GET",
        body=None,
    ):
        configuration = self.configuration
        docpath = self.docpath

        entity_proxy = configuration.xpath(
            '//http/statuscodes/status[@name="' + str(status) + '"]/proxy'
        )
        if entity_proxy:
            source = "proxy"
            target = entity_proxy[0].xpath("./text()")[0]
        else:
            source = "filesystem"

        entity_tarpit = configuration.xpath(
            '//http/statuscodes/status[@name="' + str(status) + '"]/tarpit'
        )
        if entity_tarpit:
            tarpit = self.config_sanitize_tarpit(entity_tarpit[0].xpath("./text()")[0])
        else:
            tarpit = None

        if tarpit is not None:
            await self.do_tarpit(tarpit)
        elif self.tarpit is not None:
            await self.do_tarpit(self.tarpit)

        if source == "filesystem":
            headers = self.get_status_headers(status, headers)
            trailers = self.get_status_trailers(status)
            try:
                if not isinstance(status, int):
                    status = status.value
                with open(
                    os.path.join(docpath, "statuscodes", str(int(status)) + ".status"),
                    "rb",
                ) as f:
                    payload = f.read()
            except IOError as e:
                logger.exception("%s", e)
                payload = b""

            payload = substitute_template_fields(payload)

            chunked_transfer = configuration.xpath(
                '//http/htdocs/node[@name="' + str(status) + '"]/chunks'
            )
            if chunked_transfer:
                headers.append(("Transfer-Encoding", "chunked"))
                chunks = str(chunked_transfer[0].xpath("./text()")[0])
            else:
                if isinstance(payload, str):
                    payload_len = len(payload.encode())
                else:
                    payload_len = len(payload)
                headers.append(("Content-Length", str(payload_len)))
                chunks = "0"
            return status, headers, trailers, payload, chunks

        elif source == "proxy":
            trailers = []
            chunks = "0"
            try:
                headers_dict = dict(requestheaders)
                headers_dict["Host"] = target
                headers_dict["Connection"] = "close"
                url = f"http://{target}{requeststring}"
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.request(
                        method, url, headers=headers_dict, data=body
                    ) as response:
                        remotestatus = response.status
                        headers = list(response.headers.items())
                        payload = await response.read()

                for i, header in enumerate(headers):
                    if (
                        header[0].lower() == "transfer-encoding"
                        and header[1].lower() == "chunked"
                    ):
                        del headers[i]
                        break
                status = remotestatus
            except Exception:
                if status != 503:
                    status, headers, trailers, payload, chunks = await self.load_status(
                        503, requeststring, requestheaders, headers, method, body
                    )
                else:
                    status = 503
                    payload = b""
                    chunks = "0"
                    headers.append(("Content-Length", "0"))
            return status, headers, trailers, payload, chunks

    async def load_entity(self, requeststring, headers):
        configuration = self.configuration
        docpath = self.docpath

        rqfilename = requeststring.partition("?")[0]
        rqparams = requeststring.partition("?")[2]

        entity_alias = configuration.xpath(
            '//http/htdocs/node[@name="' + rqfilename + '"]/alias'
        )
        if entity_alias:
            rqfilename = entity_alias[0].xpath("./text()")[0]

        rqfilename_appendix = self.get_trigger_appendix(rqfilename, rqparams)
        if rqfilename_appendix:
            rqfilename += "_" + rqfilename_appendix

        entity_proxy = configuration.xpath(
            '//http/htdocs/node[@name="' + rqfilename + '"]/proxy'
        )
        if entity_proxy:
            source = "proxy"
            target = entity_proxy[0].xpath("./text()")[0]
        else:
            source = "filesystem"

        entity_tarpit = configuration.xpath(
            '//http/htdocs/node[@name="' + rqfilename + '"]/tarpit'
        )
        if entity_tarpit:
            tarpit = self.config_sanitize_tarpit(entity_tarpit[0].xpath("./text()")[0])
        else:
            tarpit = None

        if tarpit is not None:
            await self.do_tarpit(tarpit)
        elif self.tarpit is not None:
            await self.do_tarpit(self.tarpit)

        if source == "filesystem":
            entity_status = configuration.xpath(
                '//http/htdocs/node[@name="' + rqfilename + '"]/status'
            )
            if entity_status:
                status = int(entity_status[0].xpath("./text()")[0])
            else:
                status = 200

            headers = self.get_entity_headers(rqfilename, headers)
            trailers = self.get_entity_trailers(rqfilename)

            if os.path.isabs(rqfilename):
                relrqfilename = rqfilename[1:]
            else:
                relrqfilename = rqfilename

            try:
                with open(os.path.join(docpath, "htdocs", relrqfilename), "rb") as f:
                    payload = f.read()
            except IOError as e:
                if not os.path.isdir(os.path.join(docpath, "htdocs", relrqfilename)):
                    logger.error("Failed to get template content: %s", e)
                payload = b""

            templated = False
            for header in headers:
                if (
                    header[0].lower() == "content-type"
                    and header[1].lower() == "text/html"
                ):
                    templated = True
            if templated:
                payload = substitute_template_fields(payload)

            chunked_transfer = configuration.xpath(
                '//http/htdocs/node[@name="' + rqfilename + '"]/chunks'
            )
            if chunked_transfer:
                headers.append(("Transfer-Encoding", "chunked"))
                chunks = str(chunked_transfer[0].xpath("./text()")[0])
            else:
                if isinstance(payload, str):
                    payload_len = len(payload.encode())
                else:
                    payload_len = len(payload)
                headers.append(("Content-Length", str(payload_len)))
                chunks = "0"
            return status, headers, trailers, payload, chunks

        elif source == "proxy":
            trailers = []
            try:
                url = f"http://{target}{requeststring}"
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as response:
                        status = response.status
                        headers = list(response.headers.items())
                        payload = await response.read()
                        chunks = "0"
            except Exception:
                status = 503
                status, headers, trailers, payload, chunks = await self.load_status(
                    status, requeststring, {}, headers
                )
            return status, headers, trailers, payload, chunks


class HoneyStreamResponse(web.StreamResponse):
    """StreamResponse that omits aiohttp's default Server header."""

    async def _prepare_headers(self):
        await super()._prepare_headers()
        self.headers.popall(hdrs.SERVER, ())


def _refresh_date_headers(state):
    """Rebuild Date values in global headers when auto-update is enabled."""
    if not state.update_header_date:
        return list(state.global_headers)
    refreshed = []
    for name, value in state.global_headers:
        if name.lower() == "date":
            refreshed.append(
                (
                    name,
                    time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime()),
                )
            )
        else:
            refreshed.append((name, value))
    return refreshed


def _log_request(state, version, request_type, addr, local, request, response=None):
    session = conpot_core.get_session(
        "http",
        addr[0],
        addr[1],
        local[0],
        local[1],
    )
    logger.info(
        "%s %s request from %s: %s. %s",
        version,
        request_type,
        addr,
        request,
        session.id,
    )
    if response is not None:
        logger.info("%s response to %s: %s. %s", version, addr, response, session.id)
        session.log_event(request=str(request), response=str(response))
    else:
        session.log_event(request=str(request))


def _peer_addrs(request):
    peername = request.transport.get_extra_info("peername")
    sockname = request.transport.get_extra_info("sockname")
    if peername is None:
        remote = request.remote or "0.0.0.0"
        peername = (remote, 0)
    if sockname is None:
        state = request.app[HTTP_STATE_KEY]
        sockname = ("0.0.0.0", state.server_port or 0)
    return peername, sockname


def _headers_to_list(headers):
    return [(k, v) for k, v in headers.items()]


async def _send_payload(request, status, headers, trailers, payload, chunks, head_only):
    header_list = [(str(n), str(v) if v is not None else "") for n, v in headers]

    if chunks != "0":
        body = _frame_chunked(payload, chunks, trailers)
        # Pre-framed chunked body: disable aiohttp auto-chunking / length checks.
        resp = HoneyStreamResponse(status=status, headers=header_list)
        resp._length_check = False
        if head_only:
            await resp.prepare(request)
            await resp.write_eof()
            return resp
        await resp.prepare(request)
        await resp.write(body)
        await resp.write_eof()
        return resp

    if isinstance(payload, str):
        payload = payload.encode()
    elif not isinstance(payload, (bytes, bytearray)):
        payload = str_to_bytes(str(payload))

    # Ensure Content-Length is present and correct for non-chunked responses.
    has_cl = any(n.lower() == "content-length" for n, _ in header_list)
    if not has_cl:
        header_list.append(("Content-Length", str(len(payload))))

    if head_only:
        resp = HoneyStreamResponse(status=status, headers=header_list)
        await resp.prepare(request)
        await resp.write_eof()
        return resp

    resp = HoneyStreamResponse(status=status, headers=header_list)
    await resp.prepare(request)
    if payload:
        await resp.write(payload)
    await resp.write_eof()
    return resp


def create_app(state):
    app = web.Application()
    app[HTTP_STATE_KEY] = state

    async def handle(request):
        state = request.app[HTTP_STATE_KEY]
        method = request.method.upper()
        # BaseHTTPRequestHandler.path includes the query string.
        path = request.path_qs
        body = await request.read()
        request_headers = _headers_to_list(request.headers)
        peername, sockname = _peer_addrs(request)
        version = state.protocol_version
        headers = list(_refresh_date_headers(state))
        head_only = method == "HEAD"

        if method not in SUPPORTED_METHODS:
            status, headers, trailers, payload, chunks = await state.load_status(
                501, path, request_headers, headers, method, body
            )
            _log_request(
                state,
                version,
                method,
                peername,
                sockname,
                (path, request_headers, body or None),
                status,
            )
            return await _send_payload(
                request, status, headers, trailers, payload, chunks, head_only=False
            )

        if method == "TRACE":
            if state.disable_method_trace:
                status, headers, trailers, payload, chunks = await state.load_status(
                    501, path, request_headers, headers, method, body
                )
            else:
                status = 200
                trailers = []
                chunks = "0"
                payload = ""
                headers.append(("Content-Type", "message/http"))
                for rqheader in request.headers:
                    payload += f"{rqheader}: {request.headers.get(rqheader)}\n"
                headers.append(("Content-Length", str(len(payload.encode()))))
            _log_request(
                state,
                version,
                method,
                peername,
                sockname,
                (path, request_headers, body or None),
                status,
            )
            return await _send_payload(
                request, status, headers, trailers, payload, chunks, head_only=False
            )

        if method == "OPTIONS":
            if state.disable_method_options:
                status, headers, trailers, payload, chunks = await state.load_status(
                    501, path, request_headers, headers, method, body
                )
            else:
                status = 200
                payload = ""
                trailers = []
                chunks = "0"
                allowed_methods = "GET"
                if not state.disable_method_head:
                    allowed_methods += ",HEAD"
                allowed_methods += ",POST,OPTIONS"
                if not state.disable_method_trace:
                    allowed_methods += ",TRACE"
                headers.append(("Allow", allowed_methods))
                headers.append(("Content-Length", "0"))
                headers.append(("Connection", "close"))
                headers.append(("Content-Type", "text/html"))
            _log_request(
                state,
                version,
                method,
                peername,
                sockname,
                (path, request_headers, body or None),
                status,
            )
            return await _send_payload(
                request, status, headers, trailers, payload, chunks, head_only=False
            )

        if method == "HEAD" and state.disable_method_head:
            status, headers, trailers, payload, chunks = await state.load_status(
                501, path, request_headers, headers, method, body
            )
            _log_request(
                state,
                version,
                method,
                peername,
                sockname,
                (path, request_headers, body or None),
                status,
            )
            return await _send_payload(
                request, status, headers, trailers, payload, chunks, head_only=True
            )

        try:
            entity_xml = state.configuration.xpath(
                '//http/htdocs/node[@name="' + path.partition("?")[0] + '"]'
            )
        except etree.XPathEvalError:
            entity_xml = None
            logger.debug(
                "Malformed HTTP:%s URN. Failed to handle <%s>. (Client: %s)",
                method,
                path,
                peername,
            )

        if entity_xml:
            status, headers, trailers, payload, chunks = await state.load_entity(
                path, headers
            )
        else:
            status, headers, trailers, payload, chunks = await state.load_status(
                404, path, request_headers, headers, method, body
            )

        _log_request(
            state,
            version,
            method,
            peername,
            sockname,
            (path, request_headers, body or None),
            status,
        )
        return await _send_payload(
            request,
            status,
            headers,
            trailers,
            payload,
            chunks,
            head_only=head_only,
        )

    # Register known + uncommon methods so unsupported ones become 501 (not 405).
    methods = (
        "GET",
        "POST",
        "HEAD",
        "OPTIONS",
        "TRACE",
        "PUT",
        "DELETE",
        "PATCH",
        "CONNECT",
    )
    for method in methods:
        app.router.add_route(method, "/", handle)
        app.router.add_route(method, "/{path:.*}", handle)

    return app


class CommandResponder(object):
    def __init__(self, host, port, template, docpath):
        self.httpd = HttpServerState(template, docpath)
        self._host = host
        self._port = port
        self.server_port = None
        self._runner = None
        self._site = None
        self._ready = None
        self._stop = None

    async def start(self):
        """Create AppRunner/TCPSite on the current (supervisor) event loop."""
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        app = create_app(self.httpd)
        self._runner = web.AppRunner(app, access_log=None, shutdown_timeout=5.0)
        await self._runner.setup()
        self._site = web.TCPSite(
            self._runner,
            self._host,
            self._port,
            reuse_address=True,
        )
        await self._site.start()
        sockets = self._site._server.sockets
        if sockets:
            self.server_port = sockets[0].getsockname()[1]
            self.httpd.server_port = self.server_port
        self._ready.set()

    async def serve_forever(self):
        if self._stop is None:
            self._stop = asyncio.Event()
        await self._stop.wait()
        await self._cleanup()

    async def _cleanup(self):
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None

    def stop(self):
        logging.info(
            "HTTP server will shut down gracefully as soon as all connections are closed."
        )
        if self._stop is not None:
            self._stop.set()
