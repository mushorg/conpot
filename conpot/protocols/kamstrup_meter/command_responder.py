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
from . import messages
import copy

from .register import KamstrupRegister

logger = logging.getLogger(__name__)


class CommandResponder(object):
    # Metertool default meter password (deception PIN for the honeypot).
    DEFAULT_LOGIN_PIN = 12345

    def __init__(self, template):
        # key: kamstrup_meter register, value: databus key
        self.registers = {}
        self.communication_address = int(template["communication_address"])
        self.login_pin = int(template.get("login_pin", self.DEFAULT_LOGIN_PIN))
        for register in template.get("registers", []):
            name = int(register["name"])
            length = int(register["length"])
            units = int(register["units"])
            unknown = int(register["unknown"])
            databuskey = register["value"]
            kamstrup_register = KamstrupRegister(
                name, units, length, unknown, databuskey
            )
            assert name not in self.registers
            self.registers[name] = kamstrup_register

    def respond(self, request):
        if request.communication_address != self.communication_address:
            logger.warning(
                "Kamstrup request received with wrong communication address, got {} but expected {}.".format(
                    request.communication_address, self.communication_address
                )
            )
            return None
        elif isinstance(request, messages.KamstrupRequestGetRegisters):
            response = messages.KamstrupResponseRegister(self.communication_address)
            for register in request.registers:
                if register in self.registers:
                    response.add_register(copy.deepcopy(self.registers[register]))
            return response
        elif isinstance(request, messages.KamstrupRequestLogin):
            if request.pin_code == self.login_pin:
                status = messages.KamstrupResponseLogin.STATUS_OK
                logger.info("Kamstrup login accepted (pin_code=%s).", request.pin_code)
            else:
                status = messages.KamstrupResponseLogin.STATUS_DENIED
                logger.info("Kamstrup login denied (pin_code=%s).", request.pin_code)
            return messages.KamstrupResponseLogin(self.communication_address, status)
        else:
            logger.warning("Unsupported Kamstrup request: %s", request)
            return None
