# Copyright (C) 2014 Johnny Vestergaard <jkv@unixcluster.dk>
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

from .session_manager import SessionManager
from .virtual_fs import VirtualFS
from .internal_interface import Interface

sessionManager = SessionManager()
virtualFS = VirtualFS()
core_interface = Interface()

# databus related  --


def get_sessionManager():
    return sessionManager


def get_databus():
    return sessionManager._databus


def get_session(*args, **kwargs):
    return sessionManager.get_session(*args, **kwargs)

# file-system related  --


def initialize_vfs(*args, **kwargs):
    return virtualFS.initialize_vfs(*args, **kwargs)


def add_protocol(*args, **kwargs):
    return virtualFS.add_protocol(*args, **kwargs)


def get_vfs():
    return virtualFS.protocol_fs


# internal-interface related   --


def get_interface():
    return globals()['core_interface']
