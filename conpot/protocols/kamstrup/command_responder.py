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
from lxml import etree

import conpot.core as conpot_core


logger = logging.getLogger(__name__)


class CommandResponder(object):
    def __init__(self, template):
        # key: kamstrup register, value: databus key
        self.registers = {}
        self.databus = conpot_core.get_databus()

        dom = etree.parse(template)
        registers = dom.xpath('//conpot_template/protocols/kamstrup/registers/*')
        self.communication_address = int(dom.xpath('//conpot_template/protocols/kamstrup/config/communication_address/text()')[0])
        for register in registers:
            register_name = int(register.attrib['name'])
            register_databuskey = register.xpath('./value/text()')[0]
            assert register_name not in self.registers
            self.registers[register_name] = register_databuskey

    def respond(self, request):
        if isinstance(request, messages.KamstrupRequestGetRegisters):
            response = messages.KamstrupResponseRegister(self.communication_address)
            for register in request.registers:
                if register in self.registers:
                    register_value = self.databus.get_value(self.registers[register])
                    # TODO: lookup units, "unknown" and length - last three params in add_register
                    #       these values is revealed by the prober and should be included in the template
                    response.add_register(register, register_value, 0, 0, 4)
            return response
        else:
            assert False


