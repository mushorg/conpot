# Copyright (C) 2013 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""Start protocol servers, LogWorker, and proxy from a template directory."""

import ast
import asyncio
import inspect
import logging
import os
import sys

from lxml import etree
from schema import SchemaError

from conpot import protocols
import conpot.protocols.schemas as protocol_schemas
from conpot.core.log_worker import LogWorker
from conpot.core.templates import validate_template
from conpot.protocols.proxy.proxy import Proxy
from conpot.templates import parse as template_parse
from conpot.templates import validate as template_validate
from conpot.utils.greenlet import AsyncioTaskHandle, spawn_startable_task

logger = logging.getLogger(__name__)


def on_unhandled_task_exception(dead):
    logger.exception(
        "Stopping because %s died: %s", dead, getattr(dead, "exception", dead)
    )
    sys.exit(1)


def _create_protocol_from_toml(
    protocol_name, server_class, protocol_template, root_template_directory, args
):
    """Build a protocol server from a TOML template. Returns (server, host, port) or None."""
    try:
        protocol = template_parse.parse_toml_config(protocol_template)
        schema = getattr(protocol_schemas, protocol_name)
        template_validate.validate_toml_template(protocol, schema)
    except (AttributeError, SchemaError, OSError, ValueError) as exc:
        logger.error("Failed to load %s TOML template: %s", protocol_name, exc)
        sys.exit(1)

    protocol_cfg = protocol[protocol_name]
    if not protocol_cfg.get("enabled"):
        logger.info("%s available but disabled by configuration.", protocol_name)
        return None

    host = protocol_cfg["host"]
    if "testing.cfg" in args.config and "127." not in host:
        logger.warning("Running on non-local interface: %s", host)
    port = protocol_cfg["port"]
    server = server_class(protocol_cfg, root_template_directory, args)
    logger.info("Found and enabled %s protocol.", protocol_name)
    return server, host, port


def _create_protocol_from_xml(
    protocol_name,
    server_class,
    protocol_template,
    root_template_directory,
    package_directory,
    args,
):
    """Build a protocol server from an XML template. Returns (server, host, port) or None."""
    xsd_file = os.path.join(
        package_directory,
        "protocols",
        protocol_name,
        "{0}.xsd".format(protocol_name),
    )
    validate_template(protocol_template, xsd_file)
    dom_protocol = etree.parse(protocol_template)
    if not dom_protocol.xpath("//{0}".format(protocol_name)):
        logger.info("%s available but disabled by configuration.", protocol_name)
        return None

    if not ast.literal_eval(
        dom_protocol.xpath("//{0}/@enabled".format(protocol_name))[0]
    ):
        logger.info("%s available but disabled by configuration.", protocol_name)
        return None

    host = dom_protocol.xpath("//{0}/@host".format(protocol_name))[0]
    if "testing.cfg" in args.config and "127." not in host:
        logger.warning("Running on non-local interface: %s", host)
    port = ast.literal_eval(dom_protocol.xpath("//{0}/@port".format(protocol_name))[0])
    server = server_class(protocol_template, root_template_directory, args)
    logger.info("Found and enabled %s protocol.", protocol_name)
    return server, host, port


def collect_protocols(root_template_directory, package_directory, args):
    """Instantiate enabled protocol servers. Returns list of (server, host, port)."""
    servers = []

    for protocol_name, server_class in protocols.name_mapping.items():
        protocol_toml = os.path.join(
            root_template_directory, "{0}.toml".format(protocol_name)
        )
        protocol_xml = os.path.join(
            root_template_directory, "{0}.xml".format(protocol_name)
        )

        started = None
        if os.path.isfile(protocol_toml):
            started = _create_protocol_from_toml(
                protocol_name,
                server_class,
                protocol_toml,
                root_template_directory,
                args,
            )
        elif os.path.isfile(protocol_xml):
            started = _create_protocol_from_xml(
                protocol_name,
                server_class,
                protocol_xml,
                root_template_directory,
                package_directory,
                args,
            )
        else:
            logger.debug(
                "No %s template found. Service will remain unconfigured/stopped.",
                protocol_name,
            )

        if started is not None:
            servers.append(started)

    return servers


def create_log_worker(
    config, template, session_manager, public_ip, template_directory=None
):
    """Create LogWorker instance (not yet started)."""
    return LogWorker(
        config,
        template,
        session_manager,
        public_ip,
        template_directory=template_directory,
    )


def collect_proxies(root_template_directory):
    """Instantiate proxy services if enabled. Returns list of (proxy_instance, host, port)."""
    servers = []
    template_proxy = os.path.join(root_template_directory, "proxy.xml")
    if os.path.isfile(template_proxy):
        xsd_file = os.path.join(os.path.dirname(inspect.getfile(Proxy)), "proxy.xsd")
        validate_template(template_proxy, xsd_file)
        dom_proxy = etree.parse(template_proxy)
        if dom_proxy.xpath("//proxies"):
            if ast.literal_eval(dom_proxy.xpath("//proxies/@enabled")[0]):
                proxies = dom_proxy.xpath("//proxies/*")
                for p in proxies:
                    name = p.attrib["name"]
                    host = p.attrib["host"]
                    keyfile = None
                    certfile = None
                    if "keyfile" in p.attrib and "certfile" in p.attrib:
                        keyfile = p.attrib["keyfile"]
                        certfile = p.attrib["certfile"]
                        if not os.path.isabs(keyfile):
                            keyfile = os.path.join(
                                os.path.dirname(root_template_directory),
                                "ssl",
                                keyfile,
                            )
                            certfile = os.path.join(
                                os.path.dirname(root_template_directory),
                                "ssl",
                                certfile,
                            )
                    port = ast.literal_eval(p.attrib["port"])
                    proxy_host = p.xpath("./proxy_host/text()")[0]
                    proxy_port = ast.literal_eval(p.xpath("./proxy_port/text()")[0])
                    decoder = p.xpath("./decoder/text()")
                    if len(decoder) > 0:
                        decoder = decoder[0]
                    else:
                        decoder = None
                    proxy_instance = Proxy(
                        name, proxy_host, proxy_port, decoder, keyfile, certfile
                    )
                    # Proxy.start(host, port) binds the listen socket.
                    servers.append((proxy_instance, host, port))
            else:
                logger.info("Proxy available but disabled by template.")
    else:
        logger.info(
            "No proxy template found. Service will remain unconfigured/stopped."
        )

    return servers


async def start_services(
    root_template_directory,
    package_directory,
    config,
    args,
    template,
    session_manager,
    public_ip,
):
    """Start protocols, LogWorker, and proxy as asyncio tasks.

    Returns a list of (server, AsyncioTaskHandle) for shutdown.
    """
    handles = []

    for server, host, port in collect_protocols(
        root_template_directory, package_directory, args
    ):
        handle = spawn_startable_task(server, host, port)
        handle.link_exception(on_unhandled_task_exception)
        # Wait until listening so bind failures surface early.
        if hasattr(server, "_ready"):
            try:
                await asyncio.wait_for(server._ready.wait(), timeout=30.0)
            except asyncio.TimeoutError:
                logger.error("%s did not become ready in time", type(server).__name__)
                sys.exit(1)
        handles.append((server, handle))

    log_worker = create_log_worker(
        config,
        template,
        session_manager,
        public_ip,
        template_directory=root_template_directory,
    )
    log_handle = spawn_startable_task(log_worker)
    log_handle.link_exception(on_unhandled_task_exception)
    handles.append((log_worker, log_handle))

    for proxy_instance, host, port in collect_proxies(root_template_directory):
        handle = spawn_startable_task(proxy_instance, host, port)
        handle.link_exception(on_unhandled_task_exception)
        if hasattr(proxy_instance, "_ready"):
            try:
                await asyncio.wait_for(proxy_instance._ready.wait(), timeout=30.0)
            except asyncio.TimeoutError:
                logger.error("Proxy did not become ready in time")
                sys.exit(1)
        handles.append((proxy_instance, handle))

    return handles


# Back-compat aliases used by older call sites / docs.
start_protocols = collect_protocols
start_log_worker = create_log_worker
start_proxy = collect_proxies
