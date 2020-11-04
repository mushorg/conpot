# Copyright (C) 2020  srenfo
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
from .IEC104.IEC104_server import IEC104Server
from .bacnet.bacnet_server import BacnetServer
from .enip.enip_server import EnipServer
from .ftp.ftp_server import FTPServer
from .guardian_ast.guardian_ast_server import GuardianASTServer
from .http.web_server import HTTPServer
from .ipmi.ipmi_server import IpmiServer
from .kamstrup.management_protocol.kamstrup_management_server import (
    KamstrupManagementServer,
)
from .kamstrup.meter_protocol.kamstrup_server import KamstrupServer
from .modbus.modbus_server import ModbusServer
from .s7comm.s7_server import S7Server
from .snmp.snmp_server import SNMPServer
from .tftp.tftp_server import TftpServer


# Defines protocol directory names inside template directories
name_mapping = {
    "bacnet": BacnetServer,
    "enip": EnipServer,
    "ftp": FTPServer,
    "guardian_ast": GuardianASTServer,
    "http": HTTPServer,
    "IEC104": IEC104Server,
    "ipmi": IpmiServer,
    "kamstrup_management": KamstrupManagementServer,
    "kamstrup_meter": KamstrupServer,
    "modbus": ModbusServer,
    "s7comm": S7Server,
    "snmp": SNMPServer,
    "tftp": TftpServer,
}
