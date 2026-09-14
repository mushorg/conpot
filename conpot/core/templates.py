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

"""Template discovery, resolution, and XSD/TOML validation."""

import logging
import os
import sys

from lxml import etree

from conpot.templates import parse as template_parse
from conpot.templates import validate as template_validate

logger = logging.getLogger(__name__)

_TEMPLATE_BASENAMES = ("template.toml", "template.xml")


def validate_template(xml_file, xsd_file):
    xml_schema = etree.parse(xsd_file)
    xsd = etree.XMLSchema(xml_schema)
    xml = etree.parse(xml_file)
    xsd.validate(xml)
    if xsd.error_log:
        logger.error("Error parsing XML template: {}".format(xsd.error_log))
        sys.exit(1)


def _has_template_base(directory):
    return any(
        os.path.isfile(os.path.join(directory, name)) for name in _TEMPLATE_BASENAMES
    )


def discover_template_protocols(template_dir):
    """Return comma-separated protocol names present under a template directory.

    Includes top-level ``<name>.xml`` / ``<name>.toml`` files that are registered in
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
        if os.path.isfile(os.path.join(template_dir, "{0}.xml".format(name)))
        or os.path.isfile(os.path.join(template_dir, "{0}.toml".format(name)))
    )
    return ", ".join(found) if found else "N/A"


def get_template_metadata(template_path):
    """Parse core template metadata from a template.xml or template.toml path.

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

    if template_path.endswith(".toml"):
        template = template_parse.parse_toml_config(template_path)
        core_template = template.get("core", {}).get("template", {})
        for name in metadata:
            if name in core_template and name != "protocols":
                metadata[name] = core_template[name]
    else:
        dom_template = etree.parse(template_path)
        template_details = dom_template.xpath("//core/template/*")
        if template_details:
            for entity in template_details:
                name = entity.attrib.get("name")
                if name in metadata:
                    metadata[name] = entity.text

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
        template_base = None
        for name in _TEMPLATE_BASENAMES:
            candidate = os.path.join(template_dir, name)
            if os.path.isfile(candidate):
                template_base = candidate
                break
        if template_base:
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
    """Load and validate the base template (TOML preferred, XML fallback).

    Returns ``(template, template_base_path)`` where ``template`` is a parsed TOML
    dict or an lxml ElementTree for XML.
    """
    from schema import SchemaError

    template_toml = os.path.join(root_template_directory, "template.toml")
    template_xml = os.path.join(root_template_directory, "template.xml")

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

    if os.path.isfile(template_xml):
        validate_template(template_xml, os.path.join(package_directory, "template.xsd"))
        return etree.parse(template_xml), template_xml

    logger.error("Could not access template configuration")
    sys.exit(1)
