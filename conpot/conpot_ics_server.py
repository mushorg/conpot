# Copyright (C) 2013  Lukas Rist <glaslos@gmail.com>
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

import sys
import logging
import json
import argparse
import os.path

import gevent
from gevent.queue import Queue

from lxml import etree
from conpot.modules import modbus_server, snmp_command_responder

import config
from conpot.modules.loggers import sqlite_log, feeder


__version__ = "0.1.0"

logger = logging.getLogger()


def log_worker(log_queue):
    if config.sqlite_enabled:
        sqlite_logger = sqlite_log.SQLiteLogger()
    if config.hpfriends_enabled:
        friends_feeder = feeder.HPFriendsLogger()

    while True:
        event = log_queue.get()
        assert "data_type" in event
        assert "timestamp" in event

        if config.hpfriends_enabled:
            friends_feeder.log(json.dumps(event))

        if config.sqlite_enabled:
            sqlite_logger.log(event)


def create_snmp_server(template, log_queue):
    dom = etree.parse(template)
    mibs = dom.xpath("//conpot_template/snmp/mibs/*")
    #only enable snmp server if we have configuration items
    if not mibs:
        snmp_server = None
    else:
        snmp_server = snmp_command_responder.CommandResponder(log_queue)

    for mib in mibs:
        mib_name = mib.attrib["name"]
        for symbol in mib:
            symbol_name = symbol.attrib["name"]
            value = symbol.xpath("./value/text()")[0]
            snmp_server.register(mib_name, symbol_name, value)
    return snmp_server


def logo():
    print """
                       _
   ___ ___ ___ ___ ___| |_
  |  _| . |   | . | . |  _|
  |___|___|_|_|  _|___|_|
              |_|

  Version {0}
  Glastopf Project
""".format(__version__)


def main():
    logo()
    root_logger = logging.getLogger()

    console_log = logging.StreamHandler()
    console_log.setLevel(logging.DEBUG)
    console_log.setFormatter(logging.Formatter("%(asctime)-15s %(message)s"))
    root_logger.addHandler(console_log)

    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--template",
                        help="define the template to use",
                        type=str,
                        default="templates/default.xml"
                        )
    args = parser.parse_args()
    if not os.path.isfile(args.template):
        print("Invalid template path/name")
        print("bye")
        sys.exit(1)
    else:
        print("Using template {0}".format(args.template))
    servers = []

    log_queue = Queue()
    gevent.spawn(log_worker, log_queue)

    logger.setLevel(logging.DEBUG)
    modbus_daemon = modbus_server.ModbusServer(args.template, log_queue).get_server(config.modbus_host,
                                                                                              config.modbus_port)
    servers.append(gevent.spawn(modbus_daemon.serve_forever))

    snmp_server = create_snmp_server(args.template, log_queue)
    if snmp_server:
        logger.info("SNMP server started.")
        servers.append(gevent.spawn(snmp_server.serve_forever))
    try:
        gevent.joinall(servers)
    except KeyboardInterrupt:
        print(" really? bye")


if __name__ == "__main__":
    main()