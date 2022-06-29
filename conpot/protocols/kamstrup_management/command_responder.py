# Copyright (C) 2014  Andrea De Pasquale <andrea@de-pasquale.name>
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

from . import commands


logger = logging.getLogger(__name__)


class CommandResponder(object):
    COMMAND_NOT_FOUND = "\r\n" "? Command not found.\r\n" "Send 'H' for help.\r\n"

    def __init__(self):
        self.commands = {
            "!AC": commands.AccessControlCommand(),
            "!AS": commands.AlarmServerCommand(),
            "!GC": commands.GetConfigCommand(),
            "!GV": commands.SoftwareVersionCommand(),
            "!SA": commands.SetKap1Command(),
            "!SB": commands.SetKap2Command(),
            "!SC": commands.SetConfigCommand(),
            "!SD": commands.SetDeviceNameCommand(),
            "!SH": commands.SetLookupCommand(),
            "!SI": commands.SetIPCommand(),
            "!SK": commands.SetWatchdogCommand(),
            "!SN": commands.SetNameserverCommand(),
            "!SP": commands.SetPortsCommand(),
            "!SS": commands.SetSerialCommand(),
            "!RC": commands.RequestConnectCommand(),
            "!RR": commands.RequestRestartCommand(),
            "!WM": commands.WinkModuleCommand(),
        }

        self.help_command = commands.HelpCommand(self.commands)

    def respond(self, request):
        stripped_request = request.strip()

        if len(stripped_request) == 0:
            return ""  # idle

        split_request = stripped_request.split(" ", 1)
        command = split_request[0].upper()

        if len(command) > 3:
            return self.COMMAND_NOT_FOUND
        elif command.startswith("Q"):
            return  # quit

        params = None
        if len(split_request) > 1:
            params = split_request[1]

        if command.startswith("H"):
            return self.help_command.run(params)
        if command.startswith("!"):
            if command in list(self.commands.keys()):
                return self.commands[command].run(params)

        return self.COMMAND_NOT_FOUND
