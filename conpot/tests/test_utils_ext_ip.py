# Copyright (C) 2014 MushMush Foundation
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

import asyncio
import threading
import time
import unittest

from aiohttp import web

import conpot.utils.ext_ip


class _AiohttpMockServer:
    """Minimal aiohttp site on a background thread."""

    def __init__(self, host="127.0.0.1", port=8000):
        self.host = host
        self.port = port
        self.loop = None
        self._runner = None
        self._ready = threading.Event()
        self._error = None
        self._thread = None

    def start(self):
        async def handle(_request):
            return web.Response(text="127.0.0.1", content_type="text/html")

        def run():
            try:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)

                async def start_site():
                    app = web.Application()
                    app.router.add_get("/", handle)
                    self._runner = web.AppRunner(app, access_log=None)
                    await self._runner.setup()
                    site = web.TCPSite(self._runner, self.host, self.port)
                    await site.start()

                self.loop.run_until_complete(start_site())
                self._ready.set()
                self.loop.run_forever()
                self.loop.run_until_complete(self._runner.cleanup())
            except Exception as exc:
                self._error = exc
                self._ready.set()
            finally:
                if self.loop is not None:
                    self.loop.close()

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=10):
            raise RuntimeError("aiohttp mock server failed to start")
        if self._error is not None:
            raise self._error

    def stop(self):
        if self.loop is not None and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=10)


class TestExtIPUtil(unittest.TestCase):
    def test_ip_verify(self):
        self.assertTrue(conpot.utils.ext_ip._verify_address("127.0.0.1") is True)

    def test_ext_util(self):
        server = _AiohttpMockServer()
        server.start()
        try:
            # Give the site a moment to accept connections.
            time.sleep(0.1)
            ip_address = str(
                conpot.utils.ext_ip._fetch_data(urls=["http://127.0.0.1:8000"])
            )
            self.assertTrue(conpot.utils.ext_ip._verify_address(ip_address) is True)
        finally:
            server.stop()

    def test_fetch_ext_ip(self):
        self.assertIsNotNone(
            conpot.utils.ext_ip.get_ext_ip(urls=["https://api.ipify.org"])
        )
