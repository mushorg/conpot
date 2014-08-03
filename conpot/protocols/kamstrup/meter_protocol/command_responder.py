# Copyright (C) 2014  Johnny Vestergaard <jkv@unixcluster.dk>
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
import messages
import copy
from lxml import etree

from register import KamstrupRegister


logger = logging.getLogger(__name__)


class CommandResponder(object):
    def __init__(self, template):
        # key: kamstrup register, value: databus key
        self.registers = {}

        dom = etree.parse(template)
        registers = dom.xpath('//conpot_template/protocols/kamstrup/registers/*')
        self.communication_address = int(dom.xpath('//conpot_template/protocols/kamstrup/config/communication_address/text()')[0])
        for register in registers:
            name = int(register.attrib['name'])
            length = int(register.attrib['length'])
            units = int(register.attrib['units'])
            unknown = int(register.attrib['unknown'])
            databuskey = register.xpath('./value/text()')[0]
            kamstrup_register = KamstrupRegister(name, units, length, unknown, databuskey)
            assert name not in self.registers
            self.registers[name] = kamstrup_register

    def respond(self, request):
        if isinstance(request, messages.KamstrupRequestGetRegisters):
            response = messages.KamstrupResponseRegister(self.communication_address)
            for register in request.registers:
                if register in self.registers:
                    response.add_register(copy.deepcopy(self.registers[register]))
            return response
        else:
            assert False


