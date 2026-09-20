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

"""Template discovery, resolution, and TOML validation."""

import logging
import os
import sys

from conpot.templates import parse as template_parse
from conpot.templates import validate as template_validate

logger = logging.getLogger(__name__)

_TEMPLATE_BASENAME = "template.toml"


def _has_template_base(directory):
    return os.path.isfile(os.path.join(directory, _TEMPLATE_BASENAME))


def discover_template_protocols(template_dir):
    """Return comma-separated protocol names present under a template directory.

    Includes top-level ``<name>.toml`` files that are registered in
    ``protocols.name_mapping`` (plus ``proxy``). Auxiliary protocol directories
    (e.g. ``http/htdocs``) may still exist alongside the config files.
    """
    from conpot import protocols

    if not os.path.isdir(template_dir):
        return "N/A"

    known = set(protocols.name_mapping) | {"proxy"}
    found = sorted(
        name
        for name in known
        if os.path.isfile(os.path.join(template_dir, "{0}.toml".format(name)))
    )
    return ", ".join(found) if found else "N/A"


def discover_protocol_ports(template_dir, protocol_names):
    """Read listen ports for ``protocol_names`` from TOML protocol templates.

    Returns a dict of protocol name to int port for entries that could be resolved.
    Missing or unreadable files are skipped.
    """
    ports = {}
    if not os.path.isdir(template_dir):
        return ports

    for name in protocol_names:
        toml_path = os.path.join(template_dir, "{0}.toml".format(name))
        try:
            if os.path.isfile(toml_path):
                cfg = template_parse.parse_toml_config(toml_path)
                port = cfg.get(name, {}).get("port")
                if port is not None:
                    ports[name] = int(port)
        except (OSError, ValueError, TypeError) as exc:
            logger.debug("Could not resolve port for %s: %s", name, exc)
    return ports


def get_template_metadata(template_path):
    """Parse core template metadata from a template.toml path.

    Returns a dict with keys unit, vendor, description, protocols, creator.
    Missing fields default to "N/A". Protocols are derived from the template
    filesystem (not the template ``protocols`` entity) to avoid drift.
    """
    metadata = {
        "unit": "N/A",
        "vendor": "N/A",
        "description": "N/A",
        "protocols": "N/A",
        "creator": "N/A",
    }
    template_dir = os.path.dirname(template_path)

    template = template_parse.parse_toml_config(template_path)
    core_template = template.get("core", {}).get("template", {})
    for name in metadata:
        if name in core_template and name != "protocols":
            metadata[name] = core_template[name]

    metadata["protocols"] = discover_template_protocols(template_dir)
    return metadata


def list_available_templates(package_directory):
    """Return list of (folder_name, metadata_dict) for packaged templates."""
    templates_root = os.path.join(package_directory, "templates")
    available = []
    if not os.path.isdir(templates_root):
        return available

    for folder in os.listdir(templates_root):
        template_dir = os.path.join(templates_root, folder)
        template_base = os.path.join(template_dir, _TEMPLATE_BASENAME)
        if os.path.isfile(template_base):
            available.append((folder, get_template_metadata(template_base)))
    return available


def format_template_list(templates):
    """Format template catalog for CLI output."""
    lines = [
        "--------------------------------------------------",
        " Available templates:",
        "--------------------------------------------------",
        "",
    ]
    for folder, meta in templates:
        lines.append("   --template {0}".format(folder))
        lines.append(
            "       Unit:        {0} - {1}".format(meta["vendor"], meta["unit"])
        )
        lines.append("       Desc:        {0}".format(meta["description"]))
        lines.append("       Protocols:   {0}".format(meta["protocols"]))
        lines.append("       Created by:  {0}".format(meta["creator"]))
        lines.append("")
    return "\n".join(lines)


def resolve_template_directory(template_arg, package_directory):
    """Resolve a template name or path to an absolute template directory.

    Returns the directory path, or None if not found.
    """
    if _has_template_base(template_arg):
        return template_arg

    packaged_dir = os.path.join(package_directory, "templates", template_arg)
    if _has_template_base(packaged_dir):
        return packaged_dir

    return None


def load_base_template(root_template_directory, package_directory):
    """Load and validate the base template.toml.

    Returns ``(template, template_base_path)`` where ``template`` is a parsed TOML
    dict.
    """
    from schema import SchemaError

    template_toml = os.path.join(root_template_directory, "template.toml")

    if os.path.isfile(template_toml):
        try:
            template = template_parse.parse_toml_config(template_toml)
            template_validate.validate_toml_template(
                template, template_validate.base_schema
            )
        except SchemaError as se:
            logger.error("Template validation error: {}".format(se))
            sys.exit(1)
        return template, template_toml

    logger.error("Could not access template configuration")
    sys.exit(1)
