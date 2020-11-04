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

import os
from conpot.protocols.http.command_responder import CommandResponder
import logging
from conpot.core.protocol_wrapper import conpot_protocol

logger = logging.getLogger(__name__)


@conpot_protocol
class HTTPServer(object):
    def __init__(self, template, template_directory, args):
        self.template = template
        self.template_directory = template_directory
        self.server_port = None
        self.cmd_responder = None

    def start(self, host, port):
        logger.info("HTTP server started on: %s", (host, port))
        self.cmd_responder = CommandResponder(
            host, port, self.template, os.path.join(self.template_directory, "http")
        )
        self.cmd_responder.httpd.allow_reuse_address = True
        self.server_port = self.cmd_responder.server_port
        self.cmd_responder.serve_forever()

    def stop(self):
        if self.cmd_responder:
            self.cmd_responder.stop()
