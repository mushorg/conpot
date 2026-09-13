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

"""Template discovery, resolution, and XSD validation."""

import logging
import os
import sys

from lxml import etree

logger = logging.getLogger(__name__)


def validate_template(xml_file, xsd_file):
    xml_schema = etree.parse(xsd_file)
    xsd = etree.XMLSchema(xml_schema)
    xml = etree.parse(xml_file)
    xsd.validate(xml)
    if xsd.error_log:
        logger.error("Error parsing XML template: {}".format(xsd.error_log))
        sys.exit(1)


def get_template_metadata(template_xml):
    """Parse core template metadata from a template.xml path.

    Returns a dict with keys unit, vendor, description, protocols, creator.
    Missing fields default to "N/A".
    """
    metadata = {
        "unit": "N/A",
        "vendor": "N/A",
        "description": "N/A",
        "protocols": "N/A",
        "creator": "N/A",
    }
    dom_template = etree.parse(template_xml)
    template_details = dom_template.xpath("//core/template/*")
    if not template_details:
        return metadata

    for entity in template_details:
        name = entity.attrib.get("name")
        if name in metadata:
            metadata[name] = entity.text

    return metadata


def list_available_templates(package_directory):
    """Return list of (folder_name, metadata_dict) for packaged templates."""
    templates_root = os.path.join(package_directory, "templates")
    available = []
    if not os.path.isdir(templates_root):
        return available

    for folder in os.listdir(templates_root):
        template_xml = os.path.join(templates_root, folder, "template.xml")
        if os.path.isfile(template_xml):
            available.append((folder, get_template_metadata(template_xml)))
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
    if os.path.exists(os.path.join(template_arg, "template.xml")):
        return template_arg

    packaged = os.path.join(
        package_directory, "templates", template_arg, "template.xml"
    )
    if os.path.isfile(packaged):
        return os.path.join(package_directory, "templates", template_arg)

    return None
