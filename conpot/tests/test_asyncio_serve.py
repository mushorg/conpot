# Copyright (C) 2026 MushMush Foundation
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

"""serve_tcp_sync_handler error handling."""

import asyncio
import logging
import socket
import threading
import unittest

from conpot.utils.asyncio_serve import serve_tcp_sync_handler


class RaisingHandler:
    def __init__(self, exc):
        self.exc = exc
        self.done = threading.Event()

    def handle(self, sock, addr):
        try:
            raise self.exc
        finally:
            self.done.set()


def _serve_one_connection(exc):
    async def main():
        stop = asyncio.Event()
        ready = asyncio.Event()
        handler = RaisingHandler(exc)
        task = asyncio.create_task(
            serve_tcp_sync_handler(
                "127.0.0.1",
                0,
                handler,
                stop_event=stop,
                ready_event=ready,
                name="TestServer",
            )
        )
        await ready.wait()
        await asyncio.to_thread(
            lambda: socket.create_connection(("127.0.0.1", handler.server_port)).close()
        )
        await asyncio.to_thread(handler.done.wait, 2)
        await asyncio.sleep(0.1)
        stop.set()
        await task

    asyncio.run(main())


class TestServeTcpSyncHandler(unittest.TestCase):
    def _log_of_one_connection(self, exc):
        with self.assertLogs("conpot.utils.asyncio_serve", level="INFO") as logs:
            _serve_one_connection(exc)
        return "\n".join(logs.output)

    def test_client_reset_is_not_logged_as_crash(self):
        output = self._log_of_one_connection(BrokenPipeError(32, "Broken pipe"))
        self.assertNotIn("crashed", output)
        self.assertIn("connection closed by", output)

    def test_handler_error_is_logged_as_crash(self):
        output = self._log_of_one_connection(ValueError("handler bug"))
        self.assertIn("connection handler crashed", output)
