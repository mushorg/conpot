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

"""Start protocol servers, LogWorker, and proxy from a template directory."""

import ast
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
from conpot.utils.greenlet import spawn_startable_greenlet

logger = logging.getLogger(__name__)


def on_unhandled_greenlet_exception(dead_greenlet):
    logger.exception(
        "Stopping because {} died: {}".format(dead_greenlet, dead_greenlet.exception)
    )
    sys.exit(1)


def _start_protocol_from_toml(
    protocol_name, server_class, protocol_template, root_template_directory, args
):
    """Start a protocol server from a TOML template. Returns (server, greenlet) or None."""
    try:
        protocol = template_parse.parse_toml_config(protocol_template)
        schema = getattr(protocol_schemas, protocol_name)
        template_validate.validate_toml_template(protocol, schema)
    except (AttributeError, SchemaError, OSError, ValueError) as exc:
        logger.error("Failed to load {} TOML template: {}".format(protocol_name, exc))
        sys.exit(1)

    protocol_cfg = protocol[protocol_name]
    if not protocol_cfg.get("enabled"):
        logger.info("{} available but disabled by configuration.".format(protocol_name))
        return None

    host = protocol_cfg["host"]
    if "testing.cfg" in args.config and "127." not in host:
        logger.warning("Running on non-local interface: {}".format(host))
    port = protocol_cfg["port"]
    server = server_class(protocol_cfg, root_template_directory, args)
    greenlet = spawn_startable_greenlet(server, host, port)
    greenlet.link_exception(on_unhandled_greenlet_exception)
    logger.info("Found and enabled {} protocol.".format(protocol_name, server))
    return server, greenlet


def _start_protocol_from_xml(
    protocol_name,
    server_class,
    protocol_template,
    root_template_directory,
    package_directory,
    args,
):
    """Start a protocol server from an XML template. Returns (server, greenlet) or None."""
    xsd_file = os.path.join(
        package_directory,
        "protocols",
        protocol_name,
        "{0}.xsd".format(protocol_name),
    )
    validate_template(protocol_template, xsd_file)
    dom_protocol = etree.parse(protocol_template)
    if not dom_protocol.xpath("//{0}".format(protocol_name)):
        logger.info("{} available but disabled by configuration.".format(protocol_name))
        return None

    if not ast.literal_eval(
        dom_protocol.xpath("//{0}/@enabled".format(protocol_name))[0]
    ):
        logger.info("{} available but disabled by configuration.".format(protocol_name))
        return None

    host = dom_protocol.xpath("//{0}/@host".format(protocol_name))[0]
    if "testing.cfg" in args.config and "127." not in host:
        logger.warning("Running on non-local interface: {}".format(host))
    port = ast.literal_eval(dom_protocol.xpath("//{0}/@port".format(protocol_name))[0])
    server = server_class(protocol_template, root_template_directory, args)
    greenlet = spawn_startable_greenlet(server, host, port)
    greenlet.link_exception(on_unhandled_greenlet_exception)
    logger.info("Found and enabled {} protocol.".format(protocol_name, server))
    return server, greenlet


def start_protocols(root_template_directory, package_directory, args):
    """Start enabled protocol servers from name_mapping.

    Prefers ``<protocol>.toml`` when present, otherwise falls back to XML.

    Returns a list of (server, greenlet) tuples.
    """
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
            started = _start_protocol_from_toml(
                protocol_name,
                server_class,
                protocol_toml,
                root_template_directory,
                args,
            )
        elif os.path.isfile(protocol_xml):
            started = _start_protocol_from_xml(
                protocol_name,
                server_class,
                protocol_xml,
                root_template_directory,
                package_directory,
                args,
            )
        else:
            logger.debug(
                "No {} template found. Service will remain unconfigured/stopped.".format(
                    protocol_name
                )
            )

        if started is not None:
            servers.append(started)

    return servers


def start_log_worker(
    config, template, session_manager, public_ip, template_directory=None
):
    """Spawn LogWorker greenlet. Returns (log_worker, greenlet)."""
    log_worker = LogWorker(
        config,
        template,
        session_manager,
        public_ip,
        template_directory=template_directory,
    )
    greenlet = spawn_startable_greenlet(log_worker)
    greenlet.link_exception(on_unhandled_greenlet_exception)
    return log_worker, greenlet


def start_proxy(root_template_directory):
    """Start proxy services if enabled in the template.

    Returns a list of (proxy_instance, greenlet) tuples.
    """
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

                        # if path is absolute we assert that the cert and key is located in
                        # the templates ssl standard location

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
                    proxy_server = proxy_instance.get_server(host, port)
                    proxy_greenlet = spawn_startable_greenlet(proxy_server)
                    proxy_greenlet.link_exception(on_unhandled_greenlet_exception)
                    servers.append((proxy_instance, proxy_greenlet))
            else:
                logger.info("Proxy available but disabled by template.")
    else:
        logger.info(
            "No proxy template found. Service will remain unconfigured/stopped."
        )

    return servers


def start_services(
    root_template_directory,
    package_directory,
    config,
    args,
    template,
    session_manager,
    public_ip,
):
    """Start protocols, LogWorker, and proxy. Returns list of (server, greenlet)."""
    servers = start_protocols(root_template_directory, package_directory, args)
    log_worker, greenlet = start_log_worker(
        config,
        template,
        session_manager,
        public_ip,
        template_directory=root_template_directory,
    )
    servers.append((log_worker, greenlet))
    servers.extend(start_proxy(root_template_directory))
    return servers
