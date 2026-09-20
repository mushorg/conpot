# Copyright (C) 2020  srenfo
# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# Test / debug helpers: run asyncio protocol servers from synchronous pytest
# code using a dedicated event loop thread per server.

import asyncio
import os
import threading
from types import SimpleNamespace

import conpot
from conpot import core, protocols


class AsyncioTaskHandle:
    """Mimics gevent Greenlet API used by legacy tests (join, successful, ready, dead)."""

    def __init__(self, loop, task, server, loop_thread: threading.Thread | None = None):
        self._loop = loop
        self._task = task
        self._server = server
        self._loop_thread = loop_thread
        self.name = type(server).__name__

    def __iter__(self):
        return iter((self._loop, self._task))

    @property
    def scheduled_once(self):
        r = getattr(self._server, "_ready", None)
        if r is None:
            return True
        try:
            return r.is_set()
        except AttributeError:
            return True

    def join(self, timeout=None):
        """Wait for the task from another thread (tests). Do not call on the loop thread."""

        async def _join():
            if timeout is not None:
                await asyncio.wait_for(asyncio.shield(self._task), timeout=timeout)
            else:
                await self._task

        try:
            wait = (timeout + 5.0) if timeout is not None else None
            asyncio.run_coroutine_threadsafe(_join(), self._loop).result(timeout=wait)
        except Exception:
            pass

    async def wait(self, timeout=None):
        """Await the task on the running loop (production shutdown)."""
        if self._task.done():
            return
        try:
            if timeout is not None:
                await asyncio.wait_for(asyncio.shield(self._task), timeout=timeout)
            else:
                await self._task
        except asyncio.TimeoutError, asyncio.CancelledError:
            if not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError, Exception:
                    pass

    def get(self, timeout=None):
        """Alias for join(); for other-thread use only (was greenlet.get())."""
        self.join(timeout=timeout)

    def successful(self):
        if not self._task.done():
            return False
        if self._task.cancelled():
            return True
        return self._task.exception() is None

    def ready(self):
        return self._task.done()

    @property
    def dead(self):
        return self._task.done()

    def link_exception(self, callback):
        def _done(task):
            if task.cancelled():
                return
            exc = task.exception()
            if exc is not None:
                # Build a greenlet-like object for the callback.
                class _Dead:
                    def __init__(self, name, exception):
                        self.name = name
                        self.exception = exception

                    def __str__(self):
                        return self.name

                try:
                    callback(_Dead(self.name, exc))
                except Exception:
                    pass

        self._task.add_done_callback(
            lambda t: (
                self._loop.call_soon_threadsafe(_done, t)
                if self._loop.is_running()
                else _done(t)
            )
        )


def spawn_startable_task(instance, *args, **kwargs):
    """Schedule ``instance.start(*args, **kwargs)`` on the running loop."""
    loop = asyncio.get_running_loop()
    task = loop.create_task(instance.start(*args, **kwargs))
    handle = AsyncioTaskHandle(loop, task, instance)
    return handle


async def spawn_startable_greenlet(instance, *args, **kwargs):
    """Back-compat name: create a Task for ``instance.start`` and return a handle."""
    return spawn_startable_task(instance, *args, **kwargs)


def spawn_test_server(server_class, template, protocol, args=None, port=0):
    conpot_dir = os.path.dirname(conpot.__file__)

    template_dir = f"{conpot_dir}/templates/{template}"
    template_toml = f"{template_dir}/template.toml"
    protocol_toml = f"{template_dir}/{protocol}.toml"

    from conpot.templates.parse import parse_toml_config

    core.get_databus().initialize(parse_toml_config(template_toml))
    if os.path.isfile(protocol_toml):
        protocol_cfg = parse_toml_config(protocol_toml)[protocol]
    else:
        # Stub protocols used in unit tests (e.g. "Fake") have no config file.
        protocol_cfg = {}
    server = server_class(
        template=protocol_cfg, template_directory=template_dir, args=args
    )

    loop = asyncio.new_event_loop()
    core.get_sessionManager().attach_event_loop(loop)

    serve_task_ref: dict = {}

    async def _serve():
        serve_task_ref["task"] = asyncio.current_task()
        await server.start("127.0.0.1", port)

    loop_ready = threading.Event()

    def loop_worker():
        asyncio.set_event_loop(loop)
        loop.create_task(_serve())
        loop_ready.set()
        loop.run_forever()

    th = threading.Thread(target=loop_worker, daemon=True, name="conpot-test-loop")
    th.start()
    if not loop_ready.wait(timeout=15.0):
        raise RuntimeError("asyncio test loop thread failed to start")

    async def _wait_ready():
        if hasattr(server, "_ready"):
            await asyncio.wait_for(server._ready.wait(), timeout=30.0)
        elif hasattr(server, "ready") and hasattr(server.ready, "wait"):
            # asyncio.Event or threading.Event
            ready = server.ready
            if isinstance(ready, asyncio.Event):
                await asyncio.wait_for(ready.wait(), timeout=30.0)
            else:
                await asyncio.get_running_loop().run_in_executor(
                    None, lambda: ready.wait(timeout=30.0)
                )
        else:
            await asyncio.sleep(0.05)

    asyncio.run_coroutine_threadsafe(_wait_ready(), loop).result(timeout=35.0)

    task = serve_task_ref.get("task")
    if task is None:
        # Give the serve task a moment to register.
        for _ in range(50):
            task = serve_task_ref.get("task")
            if task is not None:
                break
            threading.Event().wait(0.02)
    if task is None:
        raise RuntimeError("protocol serve task was not registered")

    return server, AsyncioTaskHandle(loop, task, server, th)


def get_log_event(handle, timeout=2.0):
    """Fetch one session log item from the test server's asyncio.Queue."""
    log_queue = core.get_sessionManager().log_queue
    loop = handle._loop if isinstance(handle, AsyncioTaskHandle) else handle[0]

    async def _get():
        return await asyncio.wait_for(log_queue.get(), timeout=timeout)

    return asyncio.run_coroutine_threadsafe(_get(), loop).result(timeout=timeout + 2.0)


def drain_log_queue(handle):
    """Drain all currently queued session log items (test-thread safe)."""
    log_queue = core.get_sessionManager().log_queue
    loop = handle._loop if isinstance(handle, AsyncioTaskHandle) else handle[0]

    async def _drain():
        items = []
        while not log_queue.empty():
            items.append(log_queue.get_nowait())
        return items

    return asyncio.run_coroutine_threadsafe(_drain(), loop).result(timeout=5.0)


def teardown_test_server(server, loop_task):
    if isinstance(loop_task, AsyncioTaskHandle):
        loop, task = loop_task._loop, loop_task._task
        loop_thread = loop_task._loop_thread
    else:
        loop, task = loop_task
        loop_thread = None
    server.stop()

    async def _stop():
        if not task.done():
            task.cancel()
        try:
            await task
        except BaseException:
            pass

    try:
        asyncio.run_coroutine_threadsafe(_stop(), loop).result(timeout=30.0)
    except Exception:
        pass
    finally:

        def _stop_loop():
            loop.stop()

        loop.call_soon_threadsafe(_stop_loop)
        if loop_thread is not None:
            loop_thread.join(timeout=15.0)
        try:
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for t in pending:
                t.cancel()
        except Exception:
            pass
        try:
            loop.close()
        except Exception:
            pass


def init_test_server_by_name(name, port=0):
    server_class = protocols.name_mapping[name]

    template = {
        "guardian_ast": "guardian_ast",
        "IEC104": "IEC104",
        "kamstrup_management": "kamstrup_382",
        "kamstrup_meter": "kamstrup_382",
        "dnp3": "dnp3",
    }.get(name, "default")

    class Args(SimpleNamespace):
        mibcache = None

    if name in ("ftp", "tftp"):
        core.initialize_vfs()

    server, handle = spawn_test_server(
        server_class, template, name, args=Args(), port=port
    )

    if name == "http":
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0.5), handle._loop).result(
            timeout=5.0
        )

    return server, handle
