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

from typing import Tuple, Union, Optional

from .databus import Databus
from .internal_interface import Interface
from .session_manager import SessionManager
from .virtual_fs import VirtualFS, AbstractFS

databus = Databus()
sessionManager = SessionManager()
virtualFS = VirtualFS()
core_interface = Interface()

# databus related  --


def get_sessionManager():
    return sessionManager


def get_databus():
    return databus


def get_session(*args, **kwargs):
    return sessionManager.get_session(*args, **kwargs)


# file-system related  --


def initialize_vfs(fs_path=None, data_fs_path=None, temp_dir=None):
    return virtualFS.initialize_vfs(
        fs_path=fs_path, data_fs_path=data_fs_path, temp_dir=temp_dir
    )


def add_protocol(
    protocol_name: str,
    data_fs_subdir: str,
    vfs_dst_path: str,
    src_path=None,
    owner_uid: Optional[int] = 0,
    group_gid: Optional[int] = 0,
    perms: Optional[oct] = 0o755,
) -> Tuple:
    return virtualFS.add_protocol(
        protocol_name,
        data_fs_subdir,
        vfs_dst_path,
        src_path,
        owner_uid,
        group_gid,
        perms,
    )


def get_vfs(protocol_name: Optional[str] = None) -> Union[AbstractFS, Tuple]:
    """
    Get the File System.
    :param protocol_name: Name of the protocol to be fetched
    """
    if protocol_name:
        return virtualFS._conpot_vfs[protocol_name]
    else:
        return virtualFS.protocol_fs


def close_fs():
    """Close the file system. Remove all the temp files."""
    virtualFS.close()


# internal-interface related   --


def get_interface():
    return globals()["core_interface"]
