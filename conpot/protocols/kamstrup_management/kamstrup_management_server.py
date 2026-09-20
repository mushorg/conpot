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

import asyncio
import logging
import socket
import time

import conpot.core as conpot_core
from .command_responder import CommandResponder
from conpot.core.protocol_wrapper import conpot_protocol
from conpot.utils.asyncio_serve import serve_tcp_sync_handler
from conpot.utils.networking import str_to_bytes

logger = logging.getLogger(__name__)


@conpot_protocol
class KamstrupManagementServer(object):
    def __init__(self, template, template_directory, args):
        # template is a dict from kamstrup_management.toml (enabled/host/port).
        self.command_responder = CommandResponder()
        self.banner = "\r\nWelcome...\r\nConnected to [{0}]\r\n"
        logger.info("Kamstrup management protocol server initialized.")
        self.server = None

    def handle(self, sock, address):
        sock.settimeout(5)
        session = conpot_core.get_session(
            "kamstrup_management_protocol",
            address[0],
            address[1],
            sock.getsockname()[0],
            sock.getsockname()[1],
        )
        logger.info(
            "New Kamstrup connection from %s:%s. (%s)",
            address[0],
            address[1],
            session.id,
        )
        session.log_event(event_type="NEW_CONNECTION")

        try:
            sock.send(
                str_to_bytes(
                    self.banner.format(
                        conpot_core.get_databus().get_value("mac_address")
                    )
                )
            )

            while True:
                data = sock.recv(1024)
                if not data:
                    logger.info("Kamstrup client disconnected. (%s)", session.id)
                    session.log_event(event_type="CONNECTION_LOST")
                    break
                request = data.decode()
                response = self.command_responder.respond(request)
                logger.info(
                    "Kamstrup management traffic from %s: %s (%s)",
                    address[0],
                    {"request": request, "response": response},
                    session.id,
                )
                session.log_event(request=request, response=response)
                time.sleep(0.25)  # TODO measure delay and/or RTT

                if response is None:
                    session.log_event(event_type="CONNECTION_LOST")
                    break
                # encode data before sending
                reply = str_to_bytes(response)
                sock.send(reply)

        except socket.timeout:
            logger.debug("Socket timeout, remote: %s. (%s)", address[0], session.id)
            session.log_event(event_type="CONNECTION_LOST")

        sock.close()

    async def start(self, host, port):
        self.host = host
        self.port = port
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        logger.info(
            "Kamstrup management protocol server started on: {0}".format((host, port))
        )
        await serve_tcp_sync_handler(
            host,
            port,
            self,
            stop_event=self._stop,
            ready_event=self._ready,
            name="KamstrupManagementServer",
        )

    def stop(self):
        if hasattr(self, "_stop"):
            self._stop.set()
