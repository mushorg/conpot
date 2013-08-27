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

import logging
from lxml import etree
import tempfile
import shutil

from conpot.snmp.dynrsp import DynamicResponder
from conpot.snmp.command_responder import CommandResponder
from conpot.snmp.build_pysnmp_mib_wrapper import find_mibs, compile_mib

logger = logging.getLogger()


class SNMPServer(object):
    def __init__(self, host, port, template, log_queue, mibpaths, rawmibs_dir):
        """
        :param host:        hostname or ip address on which to server the snmp service (string).
        :param port:        listen port (integer).
        :param template:    path to conpot xml configuration file (string).
        :param log_queue:   shared log queue (list).
        :param mibpaths:    collection of paths to search for COMPILED mib files (iterable collection of strings).
        :param rawmibs_dir: directory to search for raw mib files, these files will get compiled by conpot (string).
        """
        self.host = host
        self.port = port

        dyn_rsp = DynamicResponder()

        dom = etree.parse(template)
        mibs = dom.xpath('//conpot_template/snmp/mibs/*')

        # only enable snmp server if we have configuration items
        if mibs:
            try:
                tmp_mib_dir = tempfile.mkdtemp()
                mibpaths.append(tmp_mib_dir)
                mib_file_map = find_mibs(rawmibs_dir)
                self.cmd_responder = CommandResponder(self.host, self.port, log_queue, mibpaths, dyn_rsp)

                # parse global snmp configuration
                snmp_config = dom.xpath('//conpot_template/snmp/config/*')
                if snmp_config:

                    for entity in snmp_config:

                        # TARPIT: individual response delays
                        if entity.attrib['name'].lower() == 'tarpit':

                            if entity.attrib['command'].lower() == 'get':
                                self.cmd_responder.resp_app_get.tarpit = self.config_sanitize_tarpit(entity.text)
                            elif entity.attrib['command'].lower() == 'set':
                                self.cmd_responder.resp_app_set.tarpit = self.config_sanitize_tarpit(entity.text)
                            elif entity.attrib['command'].lower() == 'next':
                                self.cmd_responder.resp_app_next.tarpit = self.config_sanitize_tarpit(entity.text)
                            elif entity.attrib['command'].lower() == 'bulk':
                                self.cmd_responder.resp_app_bulk.tarpit = self.config_sanitize_tarpit(entity.text)

                # parse mibs and oid tables
                for mib in mibs:
                    mib_name = mib.attrib['name']
                    # compile the mib file if it is found and not already loaded.
                    if mib_name in mib_file_map and not self.cmd_responder.has_mib(mib_name):
                        compile_mib(mib_file_map[mib_name], tmp_mib_dir)
                    for symbol in mib:
                        symbol_name = symbol.attrib['name']

                        # retrieve instance from template
                        if 'instance' in symbol.attrib:
                            # convert instance to (int-)tuple
                            symbol_instance = symbol.attrib['instance'].split('.')
                            symbol_instance = tuple(map(int, symbol_instance))
                        else:
                            # use default instance (0)
                            symbol_instance = (0,)

                        # retrieve value from template
                        value = symbol.xpath('./value/text()')[0]

                        # retrieve engine from template
                        if len(symbol.xpath('./engine')) > 0:
                            engine_type = symbol.find('./engine').attrib['type']
                            engine_aux = symbol.findtext('./engine')
                        else:
                            # disable dynamic responses (static)
                            engine_type = 'static'
                            engine_aux = ''

                            # register this MIB instance to the command responder
                        self.cmd_responder.register(mib_name, symbol_name, symbol_instance, value, engine_type, engine_aux)
            finally:
                #cleanup compiled mib files
                shutil.rmtree(tmp_mib_dir)
        else:
            self.cmd_responder = None

    def config_sanitize_tarpit(self, value):

        # checks tarpit value for being either a single int or float,
        # or a series of two concatenated integers and/or floats seperated by semicolon and returns
        # either the (sanitized) value or zero.

        if value is not None:

            x, _, y = value.partition(';')

            try:
                _ = float(x)
            except ValueError:
                logger.error("Invalid tarpit value: '{0}'. Assuming no latency.".format(value))
                # first value is invalid, ignore the whole setting.
                return '0;0'

            try:
                _ = float(y)
                # both values are fine.
                return value
            except ValueError:
                # second value is invalid, use the first one.
                return x

        else:
            return '0;0'

    def start(self):
        if self.cmd_responder:
            logger.info('SNMP server started on: {0}'.format((self.host, self.port)))
            self.cmd_responder.serve_forever()

    def stop(self):
        if self.cmd_responder:
            self.cmd_responder.stop()
