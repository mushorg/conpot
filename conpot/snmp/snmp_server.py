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
from conpot.snmp.snmp_command_responder import CommandResponder

logger = logging.getLogger()


class SNMPServer(object):
    def __init__(self, host, port, template, log_queue):
        dom = etree.parse(template)
        mibs = dom.xpath('//conpot_template/snmp/mibs/*')
        #only enable snmp server if we have configuration items
        if not mibs:
            self.snmp_server = None
        else:
            self.snmp_server = CommandResponder(host, port, log_queue)

        for mib in mibs:
            mib_name = mib.attrib['name']
            for symbol in mib:
                symbol_name = symbol.attrib['name']
                value = symbol.xpath('./value/text()')[0]
                self.snmp_server.register(mib_name, symbol_name, value)

    def start(self):
        if self.snmp_server:
            logger.info('Starting SNMP server.')
            self.snmp_server.serve_forever()

    def stop(self):
        if self.snmp_server:
            self.snmp_server.stop()
