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
from conpot.snmp.command_responder import CommandResponder

logger = logging.getLogger()


class SNMPServer(object):
    def __init__(self, host, port, template, log_queue, mibpath):
        self.host = host
        self.port = port
        dom = etree.parse(template)
        mibs = dom.xpath('//conpot_template/snmp/mibs/*')
        #only enable snmp server if we have configuration items
        if not mibs:
            self.cmd_responder = None
        else:
            self.cmd_responder = CommandResponder(self.host, self.port, log_queue, mibpath)

        for mib in mibs:
            mib_name = mib.attrib['name']
            for symbol in mib:
                symbol_name = symbol.attrib['name']

                if 'instance' in symbol.attrib:
                    # convert instance to integer-filled tuple
                    symbol_instance = symbol.attrib['instance'].split('.')
                    symbol_instance = tuple(map(int, symbol_instance))
                else:
                    # use default instance (0)
                    symbol_instance = (0,)

                value = symbol.xpath('./value/text()')[0]
                self.cmd_responder.register(mib_name, symbol_name, symbol_instance, value)

    def start(self):
        if self.cmd_responder:
            logger.info('SNMP server started on: {0}'.format((self.host, self.port)))
            self.cmd_responder.serve_forever()

    def stop(self):
        if self.cmd_responder:
            self.cmd_responder.stop()
