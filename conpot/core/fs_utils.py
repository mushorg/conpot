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

"""
Utils related to ConpotVFS
"""
import fs
from typing import Optional, Union
from fs.permissions import Permissions
import typing
from fs.subfs import SubFS
from fs.error_tools import unwrap_errors
import logging

_F = typing.TypeVar("_F", bound="FS", covariant=True)

logger = logging.getLogger(__name__)


class FilesystemError(fs.errors.FSError):
    """Custom class for filesystem-related exceptions."""


class FSOperationNotPermitted(fs.errors.FSError):
    """Custom class for filesystem-related exceptions."""


def copy_files(source, dest, buffer_size=1024 * 1024):
    """
    Copy a file from source to dest. source and dest must be file-like objects.
    """
    while True:
        copy_buffer = source.read(buffer_size)
        if not copy_buffer:
            break
        dest.write(copy_buffer)


class _custom_conpot_file(object):
    def __init__(
        self,
        file_system,
        parent_fs,
        path,
        mode,
        buffering=-1,
        encoding=None,
        newline="",
        line_buffering=False,
    ):
        self.file_system = file_system
        self._path = path
        self._file = parent_fs.open(
            path=self._path,
            mode=mode,
            buffering=buffering,
            encoding=encoding,
            newline=newline,
            line_buffering=line_buffering,
        )
        self.mode = self._file.mode

    def __getattr__(self, item):
        return getattr(self._file, item)

    def __repr__(self):
        return "<conpot_fs cached file: {}>".format(self._file.__repr__())

    __str__ = __repr__

    @property
    def get_file(self):
        return self._file

    def close(self):
        self._file.close()
        if (
            ("w" in self.mode)
            or ("a" in self.mode)
            or (self.file_system.built_cache is False)
            or ("x" in self.mode)
        ):
            self.file_system._cache.update(
                {
                    self._path: self.file_system.getinfo(
                        self._path,
                        get_actual=True,
                        namespaces=["basic", "access", "details", "stat"],
                    )
                }
            )
            self.file_system.chown(
                self._path, self.file_system.default_uid, self.file_system.default_gid
            )
            self.file_system.chmod(self._path, self.file_system.default_perms)
        logger.debug("Updating modified/access time")
        self.file_system.setinfo(self._path, {})

    def __enter__(self):
        return self._file

    def __exit__(self, exc_type, exc_value, traceback):
        logger.debug("Exiting file at : {}".format(self._path))
        self.close()


class SubAbstractFS(SubFS[_F], typing.Generic[_F]):
    """
    Creates a chroot jail sub file system. Each protocol can have an instance of this class. Use AbstractFS's
    create_jail method to access this. You won't be able to cd into an `up` directory.
    """

    def __init__(self, parent_fs, path):
        self.parent_fs = parent_fs
        self._default_uid, self._default_gid = (
            parent_fs.default_uid,
            parent_fs.default_gid,
        )
        self._default_perms = parent_fs.default_perms
        self.utime = self.settimes
        super(SubAbstractFS, self).__init__(parent_fs, path)

    def getinfo(self, path: str, get_actual: bool = False, namespaces=None):
        _fs, _path = self.delegate_path(path)
        with unwrap_errors(path):
            return _fs.getinfo(_path, get_actual=get_actual, namespaces=namespaces)

    # ------- Setters and getters for default users/grps/perms

    @property
    def default_perms(self):
        return self._default_perms

    @default_perms.setter
    def default_perms(self, perms):
        try:
            assert isinstance(perms, Permissions)
            self._default_perms = perms
        except AssertionError:
            raise FilesystemError(
                "Permissions provided must be of valid type (fs.permissions.Permission)"
            )

    @property
    def default_uid(self):
        return self._default_uid

    @default_uid.setter
    def default_uid(self, _uid):
        if _uid in self.parent_fs._users.keys():
            self._default_uid = _uid
        else:
            raise FilesystemError("User with id {} not registered with fs".format(_uid))

    @property
    def default_gid(self):
        return self._default_gid

    @default_gid.setter
    def default_gid(self, _gid):
        if _gid in self.parent_fs._grps.keys():
            self._default_gid = _gid
        else:
            raise FilesystemError(
                "Group with id {} not registered with fs".format(_gid)
            )

    # ---- Other utilites

    @property
    def default_user(self):
        return self.parent_fs._users[self.default_uid]["user"]

    @property
    def default_group(self):
        return self.parent_fs._grps[self.default_gid]["group"]

    def getcwd(self):
        return self._sub_dir

    @property
    def root(self):
        return self.parent_fs.root + self.getcwd()

    def getmtime(self, path):
        _fs, _path = self.delegate_path(path)
        with unwrap_errors(path):
            return _fs.getmtime(_path)

    def format_list(self, basedir, listing):
        _fs, _path = self.delegate_path(basedir)
        with unwrap_errors(basedir):
            return _fs.format_list(_path, listing)

    def check_access(self, path=None, user=None, perms=None):
        _fs, _path = self.delegate_path(path)
        with unwrap_errors(path):
            return _fs.check_access(_path, user, perms)

    def chown(
        self, fs_path: str, uid: int, gid: int, recursive: Optional[bool] = False
    ):
        _fs, _path = self.delegate_path(fs_path)
        with unwrap_errors(fs_path):
            return _fs.chown(_path, uid, gid, recursive)

    def chmod(self, path: str, mode: oct, recursive: bool = False) -> None:
        _fs, _path = self.delegate_path(path)
        with unwrap_errors(path):
            return _fs.chmod(_path, mode, recursive)

    def access(
        self, path: str, name_or_id: Union[int, str] = None, required_perms: str = None
    ):
        _fs, _path = self.delegate_path(path)
        with unwrap_errors(path):
            return _fs.access(_path, name_or_id, required_perms)

    def stat(self, path):
        _fs, _path = self.delegate_path(path)
        with unwrap_errors(path):
            return _fs.stat(_path)

    def readlink(self, path):
        _fs, _path = self.delegate_path(path)
        with unwrap_errors(path):
            return _fs.readlink(_path)

    def get_permissions(self, path):
        _fs, _path = self.delegate_path(path)
        with unwrap_errors(path):
            return _fs.get_permissions(_path)

    def removedir(self, path, rf=False):
        _fs, _path = self.delegate_path(path)
        with unwrap_errors(path):
            return _fs.removedir(_path)

    def remove(self, path):
        _fs, _path = self.delegate_path(path)
        with unwrap_errors(path):
            return _fs.remove(_path)

    def move(self, src_path, dst_path, overwrite=True):
        _fs, _src_path = self.delegate_path(src_path)
        _, _dst_path = self.delegate_path(dst_path)
        with unwrap_errors({_src_path: src_path, _dst_path: dst_path}):
            return _fs.move(_src_path, _dst_path, overwrite=overwrite)

    def __getattr__(self, item):
        if hasattr(self.parent_fs, item) and item in {
            "_cache",
            "create_group",
            "register_user",
            "take_snapshot",
            "norm_path",
            "users",
            "groups",
            "add_users_to_group",
            "check_access",
        }:
            return getattr(self.parent_fs, item)
        else:
            raise NotImplementedError(
                "Conpot's File System does not currently support method: {}".format(
                    item
                )
            )
