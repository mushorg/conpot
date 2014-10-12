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

import conpot
import os
from conpot.protocols.http.command_responder import CommandResponder


logger = logging.getLogger()


class HTTPServer(object):
    def __init__(self, template):
        self.template = template
        self.server_port = None

        # self.cmd_responder = CommandResponder(host, port, template, docpath)
        #self.cmd_responder.httpd.allow_reuse_address = True
        #self.server_port = self.cmd_responder.server_port

    def start(self, host, port):
        package_directory = os.path.dirname(os.path.abspath(conpot.__file__))

        # TODO: This should be configurable, eg. not 'default'
        # In general we need a  way to send protocol specific data to protocols
        # maybe pass all cmdline args when creating protocol instances?
        docpath = os.path.join(package_directory,
                               'templates',
                               'default',
                               'http')

        logger.info('HTTP server started on: {0}'.format((host, port)))
        cmd_responder = CommandResponder(host, port, self.template, docpath)
        cmd_responder.httpd.allow_reuse_address = True
        self.server_port = cmd_responder.server_port
        cmd_responder.serve_forever()

    def stop(self):
        if self.cmd_responder:
            self.cmd_responder.stop()

    def shutdown(self):
        if self.cmd_responder:
            self.cmd_responder.httpd.shutdown()
