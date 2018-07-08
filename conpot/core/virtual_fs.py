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
import os
import sys
import fs
from fs import open_fs, mountfs, tempfs, errors
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
    :param: (open_fs) Path for storing data_fs. A dictionary with attribute name _protocol_vfs stores all the fs folders
    made by all the individual protocols.
    """
    def __init__(self, fs_path=None):
        self._protocol_vfs = {}   # dictionary to keep all the protocol vfs instances.
        if fs_path is None:
            try:
                self.data_fs = open_fs('tar:/' + os.getcwd() + '/data.tar', writeable=True, create=True)
                # TODO: Make sure data_fs closes gracfully even when Conpot crashes.
            except fs.errors.FSError:
                logger.exception('Unable to create persistent storage for Conpot. Exiting')
                sys.exit(3)
        else:
            try:
                assert fs_path, isinstance(fs_path, str)
                self.data_fs = open_fs(fs_path)  # Specify the place where you would place the uploads
            except AssertionError:
                logger.exception('Incorrect FS url specified. Please check documentation for more details.')
                sys.exit(3)
            except fs.errors.CreateFailed:
                logger.exception('Unexpected error occurred while creating Conpot FS.')
                sys.exit(3)
        self.protocol_fs = tempfs.TempFS(identifier='__conpot__')
        self._conpot_vfs = mountfs.MountFS()  # Just for convenience sake
        self._conpot_vfs.mount('data', self.data_fs)
        self._conpot_vfs.mount('protocols', self.protocol_fs)

    def init_data_fs(self, path):
        return self.__init__(fs_path=path)

    def create_protocol_fs(self, protocol_name, protocol_src_dir, data_fs_subdir):
        """
        Method that would be used by protocols to initialize vfs. Called by each protocol individually.
        :param: (str) name of the protocol for which VFS is being created.
        :param: (str) path to which the fs has to be initialized
        :param: (str) sub-folder name within data_fs that would be storing the uploads for later analysis
        :return: fs object
        """
        assert isinstance(protocol_name, str) and protocol_name
        assert isinstance(protocol_src_dir, str) and protocol_src_dir
        assert isinstance(data_fs_subdir, str) and data_fs_subdir
        if not os.path.isdir(protocol_src_dir):
            logger.exception('Protocol directory is not a valid directory.')
            sys.exit(3)
        logger.info('Creating persistent data store for protocol: {}'.format(protocol_name))
        # create a sub directory for persistent storage.
        if self.data_fs.isdir(data_fs_subdir):
            sub_data_fs = self.data_fs.opendir(path=data_fs_subdir)
        else:
            sub_data_fs = self.data_fs.makedir(path=data_fs_subdir)
        if protocol_name not in self._protocol_vfs.keys():
            sub_protocol_fs = AbstractFS(self.protocol_fs, protocol_name, protocol_src_dir, sub_data_fs)
            self._protocol_vfs[protocol_name] = sub_protocol_fs
            return sub_protocol_fs
        else:
            return self._protocol_vfs[protocol_name]
