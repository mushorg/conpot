# Copyright (C) 2014 Johnny Vestergaard <jkv@unixcluster.dk>
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

import logging
import socket
import json
from datetime import datetime
import calendar
import time
import argparse
import crc16
import xml.dom.minidom
from conpot.protocols.kamstrup.meter_protocol import kamstrup_constants

logger = logging.getLogger(__name__)

port_start_range = 1
port_end_range = 65535
default_comm_port = 63


class KamstrupRegisterCopier(object):
    def __init__(self, ip_address, port, comm_address):
        self._sock = None
        self.ip_address = ip_address
        self.port = port
        self.comm_address = comm_address
        self._connect()

    def _connect(self):
        logger.info("Connecting to {0}:{1}".format(self.ip_address, self.port))
        if self._sock is not None:
            self._sock.close()
            time.sleep(1)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(2)
        try:
            self._sock.connect((self.ip_address, self.port))
        except socket.error as socket_err:
            logger.exception("Error while connecting: {0}".format(str(socket_err)))
            self._connect()

    def get_register(self, register):
        message = [
            kamstrup_constants.REQUEST_MAGIC,
            self.comm_address,
            0x10,
            0x01,
            register >> 8,
            register & 0xFF,
        ]
        crc = crc16.crc16xmodem("".join([chr(item) for item in message[1:]]))
        message.append(crc >> 8)
        message.append(crc & 0xFF)
        message_length = len(message)
        y = 1
        while y < message_length:
            if message[y] in kamstrup_constants.NEED_ESCAPE:
                message[y] ^= 0xFF
                message.insert(y, kamstrup_constants.ESCAPE)
                y += 1
                message_length += 1
            y += 1
        message.append(kamstrup_constants.EOT_MAGIC)

        received_data = None
        while received_data is None:
            try:
                self._sock.send(bytearray(message))
                received_data = self._sock.recv(1024)
                received_data = bytearray(received_data)
            except socket.error as socket_err:
                logger.exception(
                    "Error while communicating: {0}".format(str(socket_err))
                )
                self._connect()
        data_length = len(received_data)

        # remove escaped bytes
        p = 0
        while p < data_length:
            if received_data[p] is kamstrup_constants.ESCAPE:
                del received_data[p]
                received_data[p] ^= 0xFF
                data_length -= 1
            p += 1

        return received_data


def find_registers_in_candidates(args):
    if args.registerfile:
        candidate_registers_values = []
        with open(args.registerfile, "r") as register_file:
            old_register_values = json.load(register_file)
        for value in old_register_values.iterkeys():
            candidate_registers_values.append(int(value))
    else:
        candidate_registers_values = range(port_start_range, port_end_range)

    found_registers = registers_from_candidates(candidate_registers_values, args)

    logger.info(
        "Scanned {0} registers, found {1}.".format(
            len(candidate_registers_values), len(found_registers)
        )
    )
    # with open('kamstrup_dump_{0}.json'.format(calendar.timegm(datetime.utcnow().utctimetuple())), 'w') as json_file:
    #    json_file.write(json.dumps(found_registers, indent=4, default=json_default))
    logger.info("""*** Sample Conpot configuration from this scrape:""")
    logger.info(generate_conpot_config(found_registers))


def registers_from_candidates(candidate_registers_values, args):
    kamstrupRegisterCopier = KamstrupRegisterCopier(
        args.host, args.port, int(args.communication_address)
    )
    found_registers = {}
    not_found_counts = 0
    scanned = 0
    dumpfile = "kamstrup_dump_{0}.json".format(
        calendar.timegm(datetime.utcnow().utctimetuple())
    )
    for register_id in candidate_registers_values:
        result = kamstrupRegisterCopier.get_register(register_id)
        if len(result) > 12:
            units = result[5]
            length = result[6]
            unknown = result[7]

            register_value = 0
            for p in range(length):
                register_value += result[8 + p] << (8 * ((length - p) - 1))

            found_registers[register_id] = {
                "timestamp": datetime.utcnow(),
                "units": units,
                "value": register_value,
                "value_length": length,
                "unknown": unknown,
            }
            logger.info(
                "Found register value at {0}:{1}".format(
                    hex(register_id), register_value
                )
            )
            with open(dumpfile, "w") as json_file:
                json_file.write(
                    json.dumps(found_registers, indent=4, default=json_default)
                )
        else:
            not_found_counts += 1
            if not_found_counts % 10 == 0:
                logger.info(
                    "Hang on, still scanning, so far scanned {0} and found {1} registers".format(
                        scanned, len(found_registers)
                    )
                )
        scanned += 1

    return found_registers


def generate_conpot_config(result_list):
    config_xml = """<conpot_template name="Kamstrup-Auto382" description="Register clone of an existing Kamstrup meter">
    <core><databus><key_value_mappings>"""
    for key, value in result_list.items():
        config_xml += (
            """<key name="register_{0}"><value type="value">{1}</value></key>""".format(
                key, value["value"]
            )
        )
    config_xml += """</key_value_mappings></databus></core><protocols><kamstrup_meter enabled="True" host="0.0.0.0" port="1025"><registers>"""

    for key, value in result_list.items():
        config_xml += """<register name="{0}" units="{1}" unknown="{2}" length="{3}"><value>register_{0}</value></register>""".format(
            key, value["units"], value["unknown"], value["value_length"]
        )
    config_xml += "</registers></kamstrup_meter></protocols></conpot_template>"

    parsed_xml = xml.dom.minidom.parseString(config_xml)
    pretty_xml = parsed_xml.toprettyxml()
    return pretty_xml


def json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Probes kamstrup_meter meter registers."
    )
    parser.add_argument("host", help="Hostname or IP or Kamstrup meter")
    parser.add_argument("port", type=int, help="TCP port")
    parser.add_argument(
        "--registerfile",
        dest="registerfile",
        help="Reads registers from previous dumps files instead of bruteforcing the meter.",
    )
    parser.add_argument(
        "--comm-addr", dest="communication_address", default=default_comm_port
    )

    find_registers_in_candidates(parser.parse_args())
