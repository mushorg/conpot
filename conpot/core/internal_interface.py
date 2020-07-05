# Copyright (C) 2015 Lukas Rist <glaslos@gmail.com>
#
# Rewritten by Abhinav Saxena <xandfury@gmail.com>
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

from datetime import datetime


class DotDict(dict):
    def __getattr__(self, name):
        return self[name]


class Network(object):
    def __init__(self):
        self.public_ip = None
        self.hw_address = None

    # create attributes to interface on the fly.
    def __setattr__(self, attr, value):
        object.__setattr__(self, attr, value)

    # return default value in case an attribute cannot be found in the interface
    def __getattr__(self, attr):
        raise AttributeError("Interface.Network attribute does exist")


class Interface(object):
    """ Conpot's internal interface """

    def __init__(self):
        self.network = Network()
        self.config = None
        self.protocols = DotDict()
        self.last_active = datetime.now().strftime("%b %d %Y - %H:%M:%S")

    @property
    def enabled(self):
        return [k for k in self.protocols.keys() if self.protocols[k] is not None]

    def __setattr__(self, attr, value):
        object.__setattr__(self, attr, value)

    def __getattr__(self, attr):
        raise AttributeError("Interface attribute does exist. Please check assignment")

    # FIXME: Do we really need this?
    def __repr__(self):
        s = """          Conpot: ICS/SCADA Honeypot        
                        (c) 2018, MushMush Foundation.   
               ---------------------------------------------
                (1) Using Config                       :  {}
                (2) Enabled Protocols                  :  {}
                (3) Last Active (Attacked) on          :  {}""".format(
            self.config, self.enabled, self.last_active
        )
        return s

    __str__ = __repr__
