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

import logging

from fs import mountfs, tempfs, osfs
from conpot.core.file_io import AbstractFS

logger = logging.getLogger(__name__)


# TODO: clean-up --
class VirtualFS(object):
    """
    Conpot's virtual file system. Based on Pyfilesystem2, it would allow us to have
    arbitrary file uploads while sandboxing them - for later analysis. This is how it should look like:

                      [_conpot_vfs]
                            |
                            |-- data_fs (persistent)
                            |    |-- ftp/uploads
                            |    `-- misc.
                            |
                            `-- protocol_fs (temporary, refreshed at startup)
                                 |-- common
                                 |-- telnet
                                 |-- http
                                 |-- snmp
                                 `-- ftp etc.
    """
    def __init__(self):
        self.data_fs = osfs.OSFS(root_path='')  # Specify the place where you would place the uploads
        self.protocol_fs = tempfs.TempFS()
        self._conpot_vfs = mountfs.MountFS()  # Just for convenience sake
        self._conpot_vfs.mount('data', self.data_fs)
        self._conpot_vfs.mount('protocols', self.protocol_fs)

    def create_protocol_fs(self, protocol_name, protocol_fs_dir, data_fs_subdir):
        """
        Method that would be used by protocols to initialize vfs. Called by each protocol individually.
        :param: (str) name of the protocol for which VFS is being created.
        :param: (str) path to which the fs has to be initialized
        :param: (str) sub-folder name within data_fs that would be storing the uploads for later analysis
        :return: fs object
        """
        assert isinstance(protocol_name, str), protocol_name
        assert isinstance(protocol_fs_dir, str), protocol_fs_dir
        assert isinstance(data_fs_subdir, str), data_fs_subdir
        # TODO: check if the string protocol_fs_dir is a valid path

        logger.info('Creating persistent data store for protocol: {}'.format(protocol_name))
        # create a sub directory for persistent storage.
        sub_data_fs = self.data_fs.opendir(path=data_fs_subdir)

        return AbstractFS(self.protocol_fs, protocol_name, protocol_fs_dir, sub_data_fs)