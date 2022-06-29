# Copyright (C) 2018 Abhinav Saxena <xandfury@gmail.com>
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

from conpot.core import get_interface
from datetime import datetime

core_interface = get_interface()


def conpot_protocol(cls):
    class Wrapper(object):
        def __init__(self, *args, **kwargs):
            self.wrapped = cls(*args, **kwargs)
            self.cls = cls
            if self.cls.__name__ not in "Proxy":
                if self.cls not in core_interface.protocols:
                    core_interface.protocols[self.cls] = []

                core_interface.protocols[self.cls].append(self.wrapped)

            self.__class__.__name__ = self.cls.__name__

        def __getattr__(self, name):
            if name == "handle":
                # assuming that handle function from a class is only called when a client tries to connect with an
                # enabled protocol, update the last_active (last_attacked attribute)
                # FIXME: No handle function in HTTPServer
                core_interface.last_active = datetime.now().strftime(
                    "%b %d %Y - %H:%M:%S"
                )
            return self.wrapped.__getattribute__(name)

        def __repr__(self):
            return self.wrapped.__repr__()

        __doc__ = cls.__doc__
        __module__ = cls.__module__

    return Wrapper
