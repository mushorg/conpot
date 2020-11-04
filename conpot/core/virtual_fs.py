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
import conpot
from fs import open_fs, subfs
from conpot.core.filesystem import AbstractFS, SubAbstractFS

logger = logging.getLogger(__name__)


class VirtualFS(object):
    """
    Conpot's virtual file system. Based on Pyfilesystem2, it would allow us to have
    arbitrary file uploads while sand boxing them for later analysis. This is how it should look like:

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
    :param data_fs_path: Path for storing data_fs. A dictionary with attribute name _protocol_vfs stores all the
    fs folders made by all the individual protocols.
    :type data_fs_path: fs.open_fs
    """

    def __init__(self, data_fs_path=None):
        self._conpot_vfs = (
            dict()
        )  # dictionary to keep all the protocol vfs instances, maintain easy access for
        # individual mounted protocols with paths
        if data_fs_path is None:
            try:
                self.data_fs = open_fs(
                    os.path.join(
                        "/".join(conpot.__file__.split("/")[:-1]),
                        "tests",
                        "data",
                        "data_temp_fs",
                    )
                )
            except fs.errors.FSError:
                logger.exception(
                    "Unable to create persistent storage for Conpot. Exiting"
                )
                sys.exit(3)
        else:
            try:
                assert data_fs_path and isinstance(data_fs_path, str)
                self.data_fs = open_fs(
                    data_fs_path
                )  # Specify the place where you would place the uploads
            except AssertionError:
                logger.exception(
                    "Incorrect FS url specified. Please check documentation for more details."
                )
                sys.exit(3)
            except fs.errors.CreateFailed:
                logger.exception("Unexpected error occurred while creating Conpot FS.")
                sys.exit(3)
        self.protocol_fs = None

    def initialize_vfs(self, fs_path=None, data_fs_path=None, temp_dir=None):
        if data_fs_path is not None:
            logger.info(
                "Opening path {} for persistent storage of files.".format(data_fs_path)
            )
            self.__init__(data_fs_path=data_fs_path)
        if fs_path is None:
            fs_path = "tar://" + os.path.join(
                "/".join(conpot.__file__.split("/")[:-1]), "data.tar"
            )
            logger.warning("Using default FS path. {}".format(fs_path))
        self.protocol_fs = AbstractFS(src_path=fs_path, temp_dir=temp_dir)

    def add_protocol(
        self,
        protocol_name: str,
        data_fs_subdir: str,
        vfs_dst_path: str,
        src_path=None,
        owner_uid=0,
        group_gid=0,
        perms=0o755,
    ) -> (SubAbstractFS, subfs.SubFS):
        """
        Method that would be used by protocols to initialize vfs. May be called by each protocol individually. This
        creates a chroot jail sub file system env which makes easier handling. It also creates a data_fs sub file system
        for managing protocol specific uploads.
        :param protocol_name: name of the protocol for which VFS is being created.
        :param data_fs_subdir: sub-folder name within data_fs that would be storing the uploads for later analysis
        :param vfs_dst_path:  protocol specific sub-folder path in the fs.
        :param src_path: Source from where the files are to copied.
        :param owner_uid: UID of a registered user. This is the default owner in the sub file system
        :param group_gid: GID of a existing group.
        :param perms: Default permissions of the sub file system.
        :return: fs object

        **Note:** The owner_uid and group_gid must be already registered with the fs. Otherwise an exception
        would be raised.
        """
        assert isinstance(protocol_name, str) and protocol_name
        assert isinstance(data_fs_subdir, str) and data_fs_subdir
        assert isinstance(vfs_dst_path, str) and vfs_dst_path
        if src_path:
            assert isinstance(src_path, str)
            if not os.path.isdir(src_path):
                logger.error("Protocol directory is not a valid directory.")
                sys.exit(3)
        logger.info(
            "Creating persistent data store for protocol: {}".format(protocol_name)
        )
        # create a sub directory for persistent storage.
        if self.data_fs.isdir(data_fs_subdir):
            sub_data_fs = self.data_fs.opendir(path=data_fs_subdir)
        else:
            sub_data_fs = self.data_fs.makedir(path=data_fs_subdir)
        if protocol_name not in self._conpot_vfs.keys():
            sub_protocol_fs = self.protocol_fs.mount_fs(
                vfs_dst_path, src_path, owner_uid, group_gid, perms
            )
            self._conpot_vfs[protocol_name] = (sub_protocol_fs, sub_data_fs)
        return self._conpot_vfs[protocol_name]

    def close(self, force=False):
        """
        Close the filesystem properly. Better and more graceful than __del__
        :param force: Force close. This would close the AbstractFS instance - without close closing data_fs File Systems
        """
        if self._conpot_vfs and (not force):
            for _fs in self._conpot_vfs.keys():
                try:
                    # First let us close all the data_fs instances.
                    self._conpot_vfs[_fs][1].close()
                    # Let us close the protocol_fs sub dirs for that protocol
                    self._conpot_vfs[_fs][0].close()
                except fs.errors.FSError:
                    logger.exception("Error occurred while closing FS {}".format(_fs))
                    del self._conpot_vfs[_fs][0]
        self.protocol_fs.close()
        self.protocol_fs.clean()
