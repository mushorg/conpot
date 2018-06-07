# Copyright (C) 2018  Abhinav Saxena <xandfury@gmail.com>
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

import conpot
import os
import sys
from fs import mountfs, tempfs, osfs


class ConpotFS(object):
    """
    Conpot's virtual file system. Based on Pyfilesystem2, it would allow us to have
    arbitrary file uploads while sandboxing them - for later analysis. This is how it should look like:

                          [vfs]
                            |
                            |-- data (persistent)
                            |    |-- ftp/uploads
                            |    `-- misc.
                            |
                            `-- protocols(temporary, refreshed at startup)
                                 |-- common
                                 |-- telnet
                                 |-- http
                                 |-- snmp
                                 `-- ftp etc.
    """
    def __init__(self):
        self.data_fs = osfs.OSFS(root_path='')
        self.protocol_fs = tempfs.TempFS()
        self.home_fs = mountfs.MountFS()  # Just for convenience sake
        self.upload_file = self.write_file
        self._conpot_vfs = dict()

    def read_file(self, file_name=None, chunk_size=0):
        pass

    def write_file(self):
        pass

    def create_protocol_fs(self):
        """
        Simple method that would be used by protocols to initialize vfs. This would create a sub-folder inside protocol
        fs with the vfs_name specified in the protocol directory
        :return: fs object
        """
        pass