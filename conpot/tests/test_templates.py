# Copyright (C) 2026  Lukas Rist <glaslos@gmail.com>
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
from conpot.core.templates import (
    format_template_list,
    get_template_metadata,
    list_available_templates,
    resolve_template_directory,
    validate_template,
)

package_directory = os.path.dirname(os.path.abspath(conpot.__file__))


def test_validate_default_template():
    template_xml = os.path.join(
        package_directory, "templates", "default", "template.xml"
    )
    xsd = os.path.join(package_directory, "template.xsd")
    validate_template(template_xml, xsd)


def test_validate_invalid_template_exits():
    xsd = os.path.join(package_directory, "template.xsd")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as fh:
        fh.write("<not-a-valid-template/>")
        fh.flush()
        invalid_path = fh.name
    try:
        with pytest.raises(SystemExit) as exc:
            validate_template(invalid_path, xsd)
        assert exc.value.code == 1
    finally:
        os.unlink(invalid_path)


def test_resolve_packaged_default():
    resolved = resolve_template_directory("default", package_directory)
    assert resolved == os.path.join(package_directory, "templates", "default")


def test_resolve_custom_template_dir():
    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, "template.xml"), "w").close()
        assert resolve_template_directory(tmp, package_directory) == tmp


def test_resolve_missing_returns_none():
    assert resolve_template_directory("no-such-template", package_directory) is None


def test_list_available_includes_default():
    templates = list_available_templates(package_directory)
    names = [name for name, _ in templates]
    assert "default" in names
    default_meta = dict(templates)["default"]
    assert default_meta["vendor"] == "Siemens"
    assert default_meta["unit"] == "S7-200"
    assert "HTTP" in default_meta["protocols"]


def test_get_template_metadata():
    template_xml = os.path.join(
        package_directory, "templates", "default", "template.xml"
    )
    meta = get_template_metadata(template_xml)
    assert meta["creator"] == "the conpot team"
    assert meta["description"]


def test_format_template_list():
    text = format_template_list(
        [
            (
                "default",
                {
                    "unit": "S7-200",
                    "vendor": "Siemens",
                    "description": "desc",
                    "protocols": "HTTP",
                    "creator": "team",
                },
            )
        ]
    )
    assert "--template default" in text
    assert "Siemens - S7-200" in text
    assert "Created by:  team" in text
