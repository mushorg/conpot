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

import asyncio
import os
import socket
import ssl
import threading
import unittest

import conpot
import conpot.core as conpot_core
from conpot.protocols.proxy.ascii_decoder import AsciiDecoder
from conpot.protocols.proxy.proxy import Proxy
from conpot.utils.server_tasks import AsyncioTaskHandle, teardown_test_server

package_directory = os.path.dirname(os.path.abspath(conpot.__file__))


def _start_echo_backend(ssl_files=None):
    """Threaded stdlib echo server. Returns (host, port, stop_event, thread)."""
    ready = threading.Event()
    stop = threading.Event()
    holder = {}

    def run():
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(5)
        srv.settimeout(0.2)
        holder["port"] = srv.getsockname()[1]
        ready.set()
        while not stop.is_set():
            try:
                conn, _addr = srv.accept()
            except socket.timeout:
                continue
            try:
                if ssl_files is not None:
                    keyfile, certfile = ssl_files
                    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                    ctx.load_cert_chain(certfile=certfile, keyfile=keyfile)
                    conn = ctx.wrap_socket(conn, server_side=True)
                data = conn.recv(1024)
                if data:
                    conn.sendall(data)
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        srv.close()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    if not ready.wait(5):
        raise RuntimeError("echo backend failed to start")
    return "127.0.0.1", holder["port"], stop, thread


def _start_proxy(proxy, host="127.0.0.1", port=0):
    loop = asyncio.new_event_loop()
    conpot_core.get_sessionManager().attach_event_loop(loop)
    serve_task_ref = {}

    async def _serve():
        serve_task_ref["task"] = asyncio.current_task()
        await proxy.start(host, port)

    loop_ready = threading.Event()

    def worker():
        asyncio.set_event_loop(loop)
        loop.create_task(_serve())
        loop_ready.set()
        loop.run_forever()

    thread = threading.Thread(target=worker, daemon=True, name="conpot-proxy-test")
    thread.start()
    if not loop_ready.wait(5):
        raise RuntimeError("proxy loop failed to start")

    async def _wait_ready():
        await asyncio.wait_for(proxy._ready.wait(), timeout=10.0)

    asyncio.run_coroutine_threadsafe(_wait_ready(), loop).result(timeout=15)
    task = serve_task_ref.get("task")
    if task is None:
        for _ in range(50):
            task = serve_task_ref.get("task")
            if task is not None:
                break
            threading.Event().wait(0.02)
    if task is None:
        raise RuntimeError("proxy serve task was not registered")
    return AsyncioTaskHandle(loop, task, proxy, thread)


class TestProxy(unittest.TestCase):
    def _exchange(self, proxy, payload, ssl_files=None):
        sock = socket.socket()
        sock.settimeout(5)
        if ssl_files is not None:
            keyfile, certfile = ssl_files
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ctx.load_cert_chain(certfile=certfile, keyfile=keyfile)
            sock = ctx.wrap_socket(sock)
        sock.connect(("127.0.0.1", proxy.server.server_port))
        sock.sendall(payload)
        received = sock.recv(len(payload))
        sock.close()
        return received

    def test_proxy(self):
        self.test_input = "Hiya, this is a test".encode("utf-8")
        _host, backend_port, stop, thread = _start_echo_backend()
        try:
            proxy = Proxy("proxy", "127.0.0.1", backend_port)
            handle = _start_proxy(proxy)
            try:
                received = self._exchange(proxy, self.test_input)
                self.assertEqual(self.test_input, received)
            finally:
                teardown_test_server(proxy, handle)
        finally:
            stop.set()
            thread.join(timeout=5)

    def test_ssl_proxy(self):
        self.test_input = "Hiya, this is a test".encode("utf-8")
        keyfile = os.path.join(package_directory, "templates/default/ssl/ssl.key")
        certfile = os.path.join(package_directory, "templates/default/ssl/ssl.crt")
        ssl_files = (keyfile, certfile)

        _host, backend_port, stop, thread = _start_echo_backend(ssl_files=ssl_files)
        try:
            proxy = Proxy(
                "proxy",
                "127.0.0.1",
                backend_port,
                keyfile=keyfile,
                certfile=certfile,
            )
            handle = _start_proxy(proxy)
            try:
                received = self._exchange(proxy, self.test_input, ssl_files=ssl_files)
                self.assertEqual(self.test_input, received)
            finally:
                teardown_test_server(proxy, handle)
        finally:
            stop.set()
            thread.join(timeout=5)

    def test_ascii_decoder(self):
        test_decoder = AsciiDecoder()
        # should not raise a UnicodeDecodeError
        self.assertTrue(
            (test_decoder.decode_in(b"\x80abc") == b"\xef\xbf\xbdabc")
            and (test_decoder.decode_out(b"\x80abc") == b"\xef\xbf\xbdabc")
        )

    def test_proxy_with_decoder(self):
        self.test_input = "Hiya, this is a test".encode("utf-8")
        _host, backend_port, stop, thread = _start_echo_backend()
        try:
            proxy = Proxy(
                "proxy",
                "127.0.0.1",
                backend_port,
                decoder="conpot.protocols.proxy.ascii_decoder.AsciiDecoder",
            )
            handle = _start_proxy(proxy)
            try:
                received = self._exchange(proxy, self.test_input)
                self.assertEqual(self.test_input, received)
            finally:
                teardown_test_server(proxy, handle)
        finally:
            stop.set()
            thread.join(timeout=5)

    def test_ssl_proxy_with_decoder(self):
        self.test_input = "Hiya, this is a test".encode("utf-8")
        keyfile = os.path.join(package_directory, "templates/default/ssl/ssl.key")
        certfile = os.path.join(package_directory, "templates/default/ssl/ssl.crt")
        ssl_files = (keyfile, certfile)

        _host, backend_port, stop, thread = _start_echo_backend(ssl_files=ssl_files)
        try:
            proxy = Proxy(
                "proxy",
                "127.0.0.1",
                backend_port,
                decoder="conpot.protocols.proxy.ascii_decoder.AsciiDecoder",
                keyfile=keyfile,
                certfile=certfile,
            )
            handle = _start_proxy(proxy)
            try:
                received = self._exchange(proxy, self.test_input, ssl_files=ssl_files)
                self.assertEqual(self.test_input, received)
            finally:
                teardown_test_server(proxy, handle)
        finally:
            stop.set()
            thread.join(timeout=5)
