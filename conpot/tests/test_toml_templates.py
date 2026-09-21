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

import conpot
import conpot.core as conpot_core
from conpot.core.templates import (
    discover_protocol_ports,
    get_template_metadata,
    load_base_template,
)
from conpot.emulators.misc.uptime import Uptime
from conpot.protocols import schemas as protocol_schemas
from conpot.protocols.tftp.tftp_server import TftpServer
from conpot.templates.parse import parse_toml_config
from conpot.templates.validate import base_schema, validate_toml_template
from conpot.utils.server_tasks import spawn_test_server, teardown_test_server

package_directory = os.path.dirname(os.path.abspath(conpot.__file__))
default_dir = os.path.join(package_directory, "templates", "default")
guardian_ast_dir = os.path.join(package_directory, "templates", "guardian_ast")
kamstrup_382_dir = os.path.join(package_directory, "templates", "kamstrup_382")
goose_dir = os.path.join(package_directory, "templates", "goose")
iccp_dir = os.path.join(package_directory, "templates", "iccp")
opcua_dir = os.path.join(package_directory, "templates", "opcua")


def test_parse_and_validate_default_template_toml():
    template = parse_toml_config(os.path.join(default_dir, "template.toml"))
    validate_toml_template(template, base_schema)
    assert template["core"]["template"]["vendor"] == "Conpot"
    assert "Uptime" in template["core"]["databus"]["key_value_mappings"]


def test_parse_and_validate_tftp_toml():
    protocol = parse_toml_config(os.path.join(default_dir, "tftp.toml"))
    protocol_schemas.tftp.validate(protocol)
    assert protocol["tftp"]["enabled"] is True
    assert isinstance(protocol["tftp"]["port"], int)


def test_parse_and_validate_guardian_ast_toml():
    protocol = parse_toml_config(os.path.join(guardian_ast_dir, "guardian_ast.toml"))
    protocol_schemas.guardian_ast.validate(protocol)
    assert protocol["guardian_ast"]["port"] == 10001
    template = parse_toml_config(os.path.join(guardian_ast_dir, "template.toml"))
    validate_toml_template(template, base_schema)


def test_parse_and_validate_goose_toml():
    protocol = parse_toml_config(os.path.join(goose_dir, "goose.toml"))
    protocol_schemas.goose.validate(protocol)
    assert protocol["goose"]["port"] == 10200
    assert protocol["goose"]["enabled"] is True
    template = parse_toml_config(os.path.join(goose_dir, "template.toml"))
    validate_toml_template(template, base_schema)
    assert template["core"]["template"]["protocols"] == ["goose"]


def test_parse_and_validate_iccp_toml():
    protocol = parse_toml_config(os.path.join(iccp_dir, "iccp.toml"))
    protocol_schemas.iccp.validate(protocol)
    assert protocol["iccp"]["port"] == 102
    assert protocol["iccp"]["enabled"] is True
    assert protocol["iccp"]["domain"] == "VCC"
    template = parse_toml_config(os.path.join(iccp_dir, "template.toml"))
    validate_toml_template(template, base_schema)
    assert template["core"]["template"]["protocols"] == ["iccp"]


def test_parse_and_validate_opcua_toml():
    protocol = parse_toml_config(os.path.join(opcua_dir, "opcua.toml"))
    protocol_schemas.opcua.validate(protocol)
    assert protocol["opcua"]["port"] == 4840
    assert protocol["opcua"]["enabled"] is True
    assert protocol["opcua"]["server_name"] == "Conpot OPC UA Server"
    assert len(protocol["opcua"]["variables"]) == 4
    template = parse_toml_config(os.path.join(opcua_dir, "template.toml"))
    validate_toml_template(template, base_schema)
    assert template["core"]["template"]["protocols"] == ["opcua"]


def test_parse_and_validate_kamstrup_management_toml():
    protocol = parse_toml_config(
        os.path.join(kamstrup_382_dir, "kamstrup_management.toml")
    )
    protocol_schemas.kamstrup_management.validate(protocol)
    assert protocol["kamstrup_management"]["port"] == 50100


def test_parse_and_validate_ipmi_enip_kamstrup_meter_toml():
    protocol_schemas.ipmi.validate(
        parse_toml_config(os.path.join(default_dir, "ipmi.toml"))
    )
    protocol_schemas.enip.validate(
        parse_toml_config(os.path.join(default_dir, "enip.toml"))
    )
    protocol_schemas.kamstrup_meter.validate(
        parse_toml_config(os.path.join(kamstrup_382_dir, "kamstrup_meter.toml"))
    )
    validate_toml_template(
        parse_toml_config(os.path.join(kamstrup_382_dir, "template.toml")), base_schema
    )


def test_load_base_template_prefers_toml():
    template, path = load_base_template(default_dir, package_directory)
    assert path.endswith("template.toml")
    assert isinstance(template, dict)
    assert template["core"]["template"]["vendor"] == "Conpot"


def test_databus_initialize_from_toml():
    template = parse_toml_config(os.path.join(default_dir, "template.toml"))
    databus = conpot_core.get_databus()
    databus.reset()
    databus.initialize(template)
    assert databus.get_value("FacilityName") == "Mouser Factory"
    assert isinstance(databus._data["Uptime"], Uptime)
    assert isinstance(databus.get_value("Uptime"), int)
    block = databus.get_value("memoryModbusSlave0BlockA")
    assert isinstance(block, list)
    assert len(block) == 128
    databus.reset()


def test_get_template_metadata_from_toml():
    meta = get_template_metadata(os.path.join(default_dir, "template.toml"))
    assert meta["vendor"] == "Conpot"
    assert meta["creator"] == "the conpot team"
    assert "tftp" in meta["protocols"]


def test_discover_protocol_ports_from_toml():
    ports = discover_protocol_ports(default_dir, ["http", "tftp", "modbus"])
    assert ports["tftp"] == 6969
    assert "http" in ports
    assert "modbus" in ports


def test_spawn_test_server_passes_tftp_dict():
    conpot_core.initialize_vfs()
    server, handle = spawn_test_server(TftpServer, template="default", protocol="tftp")
    try:
        assert server.root_path == "/data/tftp/"
        assert server.data_fs_subdir == "tftp"
    finally:
        teardown_test_server(server, handle)
