# Copyright (C) 2020  srenfo
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
from types import SimpleNamespace

from gevent import Greenlet, sleep
from gevent.event import Event

import conpot
from conpot import core, protocols


class ServiceGreenlet(Greenlet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scheduled_once = Event()

    def run(self):
        self.scheduled_once.set()
        super().run()


def spawn_startable_greenlet(instance, *args, **kwargs):
    greenlet = ServiceGreenlet.spawn(instance.start, *args, **kwargs)
    greenlet.name = instance.__class__.__name__

    return greenlet


def spawn_test_server(server_class, template, protocol, args=None, port=0):
    conpot_dir = os.path.dirname(conpot.__file__)

    template_dir = f"{conpot_dir}/templates/{template}"
    template_xml = f"{template_dir}/template.xml"
    protocol_xml = f"{template_dir}/{protocol}/{protocol}.xml"

    core.get_databus().initialize(template_xml)

    server = server_class(
        template=protocol_xml, template_directory=template_dir, args=args
    )

    greenlet = spawn_startable_greenlet(server, "127.0.0.1", port)
    greenlet.scheduled_once.wait()

    return server, greenlet


def teardown_test_server(server, greenlet):
    server.stop()
    greenlet.get()


# this is really a test helper but start_protocol.py wants to use it too
def init_test_server_by_name(name, port=0):
    server_class = protocols.name_mapping[name]

    template = {
        "guardian_ast": "guardian_ast",
        "IEC104": "IEC104",
        "kamstrup_management": "kamstrup_382",
        "kamstrup_meter": "kamstrup_382",
    }.get(name, "default")

    # Required by SNMP
    class Args(SimpleNamespace):
        mibcache = None

    if name in ("ftp", "tftp"):
        core.initialize_vfs()

    server, greenlet = spawn_test_server(
        server_class, template, name, args=Args(), port=port
    )

    # special case protocol with more complex start() logic
    # TODO: add serve_forever-Event() to servers to fix this properly
    if name == "http":
        sleep(0.5)

    return server, greenlet
