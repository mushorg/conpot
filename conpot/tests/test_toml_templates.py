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
from conpot.utils.greenlet import spawn_test_server, teardown_test_server

package_directory = os.path.dirname(os.path.abspath(conpot.__file__))
default_dir = os.path.join(package_directory, "templates", "default")


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


def test_discover_protocol_ports_from_xml_and_toml():
    ports = discover_protocol_ports(default_dir, ["http", "tftp", "modbus"])
    assert ports["tftp"] == 6969
    assert "http" in ports
    assert "modbus" in ports


def test_stix_transformer_resolves_ports_from_template_dir():
    from conpot.core.loggers.stix_transform import StixTransformer

    transformer = StixTransformer(None, None, template_directory=default_dir)
    # Defaults overridden by protocol templates in the default profile.
    assert transformer.protocol_to_port_mapping["http"] == 8800
    assert transformer.protocol_to_port_mapping["modbus"] == 5020
    assert transformer.protocol_to_port_mapping["snmp"] == 16100
    assert transformer.protocol_to_port_mapping["s7comm"] == 10201


def test_spawn_test_server_passes_tftp_dict():
    conpot_core.initialize_vfs()
    server, greenlet = spawn_test_server(
        TftpServer, template="default", protocol="tftp"
    )
    try:
        assert server.root_path == "/data/tftp/"
        assert server.data_fs_subdir == "tftp"
    finally:
        teardown_test_server(server, greenlet)
