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
import json
import logging
import socket
import subprocess
import sys
from asyncio import events

import aiohttp

logger = logging.getLogger(__name__)


def _verify_address(addr):
    try:
        socket.inet_aton(addr)
        return True
    except socket.error, UnicodeEncodeError, TypeError:
        return False


def _gevent_socket_patched():
    try:
        from gevent import monkey

        return monkey.is_module_patched("socket")
    except ImportError:
        return False


async def _fetch_data_async(urls):
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    timeout = aiohttp.ClientTimeout(total=5)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for url in urls:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = (await resp.text()).strip()
                        if data is None or not _verify_address(data):
                            continue
                        return data
                    logger.warning("Could not fetch public ip from %s", url)
            except asyncio.TimeoutError, aiohttp.ClientError:
                logger.warning("Could not fetch public ip from %s", url)
    return None


def _fetch_data_subprocess(urls):
    """Run aiohttp fetch in a clean interpreter (avoids gevent+asyncio DNS hangs)."""
    script = (
        "import asyncio, json, sys\n"
        "from conpot.utils.ext_ip import _fetch_data_async\n"
        "urls = json.loads(sys.argv[1])\n"
        "print(asyncio.run(_fetch_data_async(urls)) or '')\n"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", script, json.dumps(list(urls))],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Could not fetch public ip via subprocess: %s", exc)
        return None
    if completed.returncode != 0:
        logger.warning(
            "Could not fetch public ip via subprocess: %s",
            completed.stderr.strip() or completed.returncode,
        )
        return None
    data = completed.stdout.strip()
    if data and _verify_address(data):
        return data
    return None


def _fetch_data(urls):
    """Fetch via aiohttp.

    Under gevent monkey-patching, greenlets share an OS thread and asyncio DNS
    over patched sockets hangs. Prefer an existing loop when present; otherwise
    use a clean subprocess when gevent has patched ``socket``.
    """
    existing = events._get_running_loop()
    if existing is not None:
        future = asyncio.run_coroutine_threadsafe(_fetch_data_async(urls), existing)
        return future.result(timeout=60)

    if _gevent_socket_patched():
        return _fetch_data_subprocess(urls)

    return asyncio.run(_fetch_data_async(urls))


def get_ext_ip(config=None, urls=None):
    if config:
        urls = json.loads(config.get("fetch_public_ip", "urls"))
    public_ip = _fetch_data(urls)
    if public_ip:
        logger.info("Fetched %s as external ip.", public_ip)
    else:
        logger.warning("Could not fetch public ip: %s", public_ip)
    return public_ip


if __name__ == "__main__":
    print((get_ext_ip(urls=["https://api.ipify.org", "http://127.0.0.1:8000"])))
