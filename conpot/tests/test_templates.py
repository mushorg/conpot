# Copyright (C) 2026 MushMush Foundation
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

import os
import tempfile

import pytest

import conpot
from conpot import protocols
from conpot.core.templates import (
    discover_template_protocols,
    format_template_list,
    get_template_metadata,
    list_available_templates,
    resolve_template_directory,
)
from conpot.templates.parse import parse_toml_config
from conpot.templates.validate import base_schema, validate_toml_template

package_directory = os.path.dirname(os.path.abspath(conpot.__file__))


def test_validate_default_template():
    template_toml = os.path.join(
        package_directory, "templates", "default", "template.toml"
    )
    validate_toml_template(parse_toml_config(template_toml), base_schema)


def test_validate_invalid_template_raises():
    with pytest.raises(Exception):
        validate_toml_template({"not": "valid"}, base_schema)


def test_resolve_packaged_default():
    resolved = resolve_template_directory("default", package_directory)
    assert resolved == os.path.join(package_directory, "templates", "default")


def test_resolve_custom_template_dir():
    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, "template.toml"), "w").close()
        assert resolve_template_directory(tmp, package_directory) == tmp


def test_resolve_missing_returns_none():
    assert resolve_template_directory("no-such-template", package_directory) is None


def test_list_available_includes_default():
    templates = list_available_templates(package_directory)
    names = [name for name, _ in templates]
    assert "default" in names
    default_meta = dict(templates)["default"]
    assert default_meta["vendor"] == "Conpot"
    assert default_meta["unit"] == "multi-protocol sample"
    assert "Sample profile" in default_meta["description"]
    for protocol in ("bacnet", "enip", "ftp", "http", "tftp"):
        assert protocol in default_meta["protocols"]


def test_default_protocols_match_filesystem():
    default_dir = os.path.join(package_directory, "templates", "default")
    known = set(protocols.name_mapping) | {"proxy"}
    expected = sorted(
        name
        for name in known
        if os.path.isfile(os.path.join(default_dir, "{0}.toml".format(name)))
    )
    assert discover_template_protocols(default_dir) == ", ".join(expected)
    template_base = os.path.join(default_dir, "template.toml")
    meta = get_template_metadata(template_base)
    assert meta["protocols"] == ", ".join(expected)


def test_get_template_metadata():
    template_toml = os.path.join(
        package_directory, "templates", "default", "template.toml"
    )
    meta = get_template_metadata(template_toml)
    assert meta["creator"] == "the conpot team"
    assert meta["description"]


def test_format_template_list():
    text = format_template_list(
        [
            (
                "default",
                {
                    "unit": "multi-protocol sample",
                    "vendor": "Conpot",
                    "description": "desc",
                    "protocols": "http",
                    "creator": "team",
                },
            )
        ]
    )
    assert "--template default" in text
    assert "Conpot - multi-protocol sample" in text
    assert "Created by:  team" in text
