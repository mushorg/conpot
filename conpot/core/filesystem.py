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

import time
import stat
import tempfile
import logging
import contextlib
import shutil
import fs
from stat import filemode
from datetime import datetime
from os import F_OK, R_OK, W_OK
from typing import Optional, Union, Text, Any, List
from fs import open_fs, mirror, errors, subfs, base
from fs.mode import Mode
from fs.wrapfs import WrapFS
from fs.permissions import Permissions
from fs.osfs import Info
from conpot.helpers import months_map
from types import FunctionType
from conpot.core.fs_utils import (
    _custom_conpot_file,
    SubAbstractFS,
    copy_files,
    FilesystemError,
)
from conpot.core.fs_utils import FSOperationNotPermitted

logger = logging.getLogger(__name__)


# ---------------------------------------------------
# Regarding Permissions:
# ---------------------------------------------------
# For directories:
#   - Read bit = You can read the names on the list.
#   - Write bit = You can {add,rename,delete} names on the list IF the execute bit is set too.
#   - Execute bit = You can make this directory your working directory.
# ---------------------------------------------------
# For files:
#   - Read bit = Grants the capability to read, i.e., view the contents of the file.
#   - Write bit = Grants the capability to modify, or remove the content of the file.
#   - Execute bit = User with execute permissions can run a file as a program.
# ---------------------------------------------------


class AbstractFS(WrapFS):
    """
    AbstractFS distinguishes between "real" filesystem paths and "virtual" ftp paths emulating a UNIX chroot jail
    where the user can not escape its home directory (example: real "/home/user" path will be seen as "/" by the client)

    This class exposes common fs wrappers around all os.* calls involving operations against the filesystem like
    creating files or removing directories (such as listdir etc.)

    *Implementation Note:* When doing I/O - Always with the check_access and set_access context managers for safe
    operations.
    """

    def __init__(
        self,
        src_path: str,
        create_mode: int = 0o777,  # Default file system permissions.
        temp_dir: Union[str, None] = None,
        identifier: Optional[str] = "__conpot__",
        auto_clean: Optional[bool] = True,
        ignore_clean_errors: Optional[bool] = True,
    ) -> None:
        self._cwd = self.getcwd()  # keep track of the current working directory
        self._cache = {}  # Storing all cache of the file system
        self.identifier = identifier.replace("/", "-")
        self._auto_clean = auto_clean
        self._ignore_clean_errors = ignore_clean_errors
        self.temp_dir = temp_dir
        self._cleaned = False
        self.built_cache = False
        # Create our file system
        self._temp_dir = tempfile.mkdtemp(
            prefix=(self.identifier or "ConpotTempFS"), dir=self.temp_dir
        )
        # open various filesystems that would be used by Conpot
        try:
            self.vfs = open_fs(self._temp_dir)
            super(AbstractFS, self).__init__(self.vfs)
        except fs.errors.FSError as fs_err:
            logger.exception("File System exception occurred! {}".format(fs_err))
        # Copy all files from src_path into our file system
        logger.info(
            "Initializing Virtual File System at {}. Source specified : {}\n Please wait while the "
            "system copies all specified files".format(self._temp_dir, src_path)
        )
        self.utime = self.settimes  # utime maps to settimes
        # keep records related to users and groups
        self.default_uid = 0
        self.default_gid = 0
        self.default_perms = create_mode
        self._users = {0: {"user": "root"}}
        self._grps = {0: {"group": "root"}}
        # simple dictionary linking users to groups ->
        self._user_grps = {0: {0}}  # --> gid: set(uids)
        self._initialize_fs(src_path=src_path)
        # fixme: kind of hack-ish. Find the correct way of doing this.
        self._wrap_fs._meta["supports_rename"] = False

    def norm_path(self, path):
        path = "/" if path == "." else path
        try:
            _path = (
                self.validatepath(self._cwd + path)
                if self._cwd not in path
                else self.validatepath(path)
            )
            return _path
        except fs.errors.FSError:
            logger.debug("Could not validate path: {}".format(path))
            raise FilesystemError("Could not validate path: {}".format(path))

    def _initialize_fs(self, src_path: str) -> None:
        """
        Copies all data into Conpot's created fs folder and builds up the cache.
        :param src_path: FS URLS
        """
        # copy all contents from the source path the filesystem.
        src_fs = open_fs(src_path)
        logger.debug(
            "Building up file system: copying contents from the source path {}".format(
                src_path
            )
        )
        with src_fs.lock():
            mirror.mirror(src_fs=src_fs, dst_fs=self.vfs)
            self._cache.update(
                {
                    path: info
                    for path, info in self.walk.info(
                        namespaces=["basic", "access", "details", "stat"]
                    )
                }
            )
            self._cache["/"] = self._wrap_fs.getinfo(
                "/", namespaces=["basic", "access", "details", "stat", "link"]
            )
            self.chown("/", self.default_uid, self.default_gid, recursive=True)
            self.chmod("/", self.default_perms, recursive=True)
            self.built_cache = (
                True  # FS has been built. Now all info must be accessed from cache.
            )
            src_fs.close()
        del src_fs

    def __str__(self):
        return "<Conpot AbstractFS '{}'>".format(self._temp_dir)

    __repr__ = __str__

    @property
    def users(self):
        return self._users

    @property
    def groups(self):
        return self._grps

    @property
    def user_groups(self):
        """gid: {set of uid of users.}"""
        return self._user_grps

    def getmeta(self, namespace="standard"):
        self.check()
        meta = self.delegate_fs().getmeta(namespace=namespace)
        meta["supports_rename"] = False
        return meta

    # ------- context managers for easier handling of fs

    @contextlib.contextmanager
    def check_access(self, path=None, user=None, perms=None):
        """
        Checks whether the current user has permissions to do a specific operation. Raises FSOperationNotPermitted
        exception in case permissions are not satisfied.
        Handy utility to check whether the user with uid provided has permissions specified. Examples:

        >>> import conpot.core as conpot_core
        >>> _vfs, _ = conpot_core.get_vfs('ftp')
        >>> with _vfs.check_access(path='/', user=13, perms='rwx'):
        >>>     _vfs.listdir('/')

        >>> with _vfs.check_access(path='/', user=45, perms='w'):
        >>>     with _vfs.open('/test', mode='wb') as _file:
        >>>         _file.write(b'Hello World!')
        """
        if not self.access(path=path, name_or_id=user, required_perms=perms):
            raise FSOperationNotPermitted(
                "User {} does not have required permission to file/path: {}".format(
                    user, path
                )
            )
        else:
            logger.debug(
                "File/Dir {} has the requested params : {}".format(path, (user, perms))
            )
            self.setinfo(path, {})
            yield
            if self.vfs.isfile(path):
                logger.debug("yield file: {} after requested access.".format(path))
            elif self.vfs.isdir(path):
                logger.debug("yield dir: {} after requested access.".format(path))
            else:
                logger.debug(
                    "yield unknown type: {} after requested access.".format(path)
                )

    # -----------------------------------------------------------
    # Custom "setter" methods overwriting behaviour FS library methods
    # We need to update our cache in such cases.
    # -----------------------------------------------------------
    def setinfo(self, path, info):
        """
        Higher level function to directly change values in the file system. Dictionary specified here changes cache
        values.
        :param path: path of the file that is to be changed
        :param info: Raw Info object. Please check pyfilesystem2's docs for more info.
        """
        assert path and isinstance(path, str)
        path = self.norm_path(path)
        if "lstat" not in info:
            try:
                if "details" in info:
                    details = info["details"]
                    if "accessed" in details or "modified" in details:
                        return self._wrap_fs.setinfo(path, info)
            finally:
                try:
                    assert self._cache[path]
                except (AssertionError, KeyError):
                    # This is the first time we have seen this file. Let us create this entry.
                    logger.debug("Creating cache for file/directory : {}".format(path))
                    self._cache[path] = self._wrap_fs.getinfo(
                        path, namespaces=["basic", "access", "details", "stat", "link"]
                    )
                # update the 'accessed' and 'modified' time.
                self.settimes(path)
                if "access" in info:
                    access = info["access"]
                    if "permissions" in access:
                        self._cache[path].raw["access"]["permissions"] = access[
                            "permissions"
                        ]
                        self._cache[path].raw["details"][
                            "metadata_changed"
                        ] = fs.time.datetime_to_epoch(datetime.now())
                    if "user" in access or "uid" in access:
                        try:
                            if "user" in access or (
                                "user" in access and "uid" in access
                            ):
                                self._cache[path].raw["access"]["user"] = access["user"]
                                [_uid] = [
                                    key
                                    for key, value in self._users.items()
                                    if value == {"user": access["user"]}
                                ]
                                self._cache[path].raw["access"]["uid"] = _uid
                                self._cache[path].raw["details"][
                                    "metadata_changed"
                                ] = fs.time.datetime_to_epoch(datetime.now())
                            else:
                                # Must be 'uid' that is available.
                                _uid = int(access["uid"])  # type: ignore
                                self._cache[path].raw["access"]["uid"] = _uid
                                self._cache[path].raw["access"]["user"] = self._users[
                                    _uid
                                ]["user"]
                                self._cache[path].raw["details"][
                                    "metadata_changed"
                                ] = fs.time.datetime_to_epoch(datetime.now())
                        except (TypeError, AssertionError, KeyError):
                            raise
                    if "group" in access or "gid" in access:
                        try:
                            if "group" in access or (
                                "group" in access and "gid" in access
                            ):
                                self._cache[path].raw["access"]["group"] = access[
                                    "group"
                                ]
                                [_gid] = [
                                    key
                                    for key, value in self._grps.items()
                                    if value == {"group": access["group"]}
                                ]
                                self._cache[path].raw["access"]["gid"] = _gid
                                self._cache[path].raw["details"][
                                    "metadata_changed"
                                ] = fs.time.datetime_to_epoch(datetime.now())
                            else:
                                # Must be 'gid' that is available.
                                _gid = int(access["gid"])  # type: ignore
                                self._cache[path].raw["access"]["gid"] = _gid
                                self._cache[path].raw["access"]["group"] = self._grps[
                                    _gid
                                ]["group"]
                                self._cache[path].raw["details"][
                                    "metadata_changed"
                                ] = fs.time.datetime_to_epoch(datetime.now())
                        except (TypeError, AssertionError, KeyError):
                            raise
        else:
            raise FilesystemError("lstat is not currently supported!")

    def makedir(
        self,
        path,  # type: Text
        permissions=None,  # type: Optional[int]
        recreate=True,  # type: bool
    ):
        # make a directory in the file system. Also, update the cache about the directory.
        _path = self.norm_path(path)
        # we always want to overwrite a directory if it already exists.
        recreate = True if recreate is False else recreate
        perms = permissions
        fs_err = None
        try:
            super(AbstractFS, self).makedir(_path, permissions=None, recreate=recreate)
        except fs.errors.FSError as err:
            fs_err = err
        finally:
            if not fs_err:
                dir_perms = perms if perms else self.default_perms
                dir_cache = {
                    "access": {
                        "permissions": Permissions.create(dir_perms),
                        "uid": self.default_uid,
                        "gid": self.default_gid,
                    }
                }
                logger.debug("Created directory {}".format(_path))
                self.setinfo(_path, info=dir_cache)
            else:
                raise fs_err

    def removedir(self, path, rf=True):
        """Remove a directory from the file system.
        :param path: directory path
        :param rf: remove directory recursively and forcefully. This removes directory even if there is any data
        in it. If set to False, an exception would be raised
        """
        # removing a directory and finally block would clear the local cache.
        _path = self.norm_path(path)
        fs_err = None
        try:
            super(AbstractFS, self).removedir(_path)
        except fs.errors.FSError as err:
            fs_err = err
        finally:
            if not fs_err:
                rm_dir = self._cache.pop(_path)
                logger.debug("Removed directory {}".format(rm_dir))
            else:
                if isinstance(fs_err, fs.errors.DirectoryNotEmpty) and rf is True:
                    # delete the contents for the directory recursively
                    self._wrap_fs.removetree(_path)
                    # delete the all the _cache files in the directory.
                    _files = [i for i in self._cache.keys() if _path in i]
                    for _f in _files:
                        file = self._cache.pop(_f)
                        logger.debug("Removing file : {}".format(repr(file)))
                else:
                    raise fs_err

    def remove(self, path):
        """Remove a file from the file system."""
        _path = self.norm_path(path)
        fs_err = None
        try:
            super(AbstractFS, self).remove(_path)
        except fs.errors.FSError as err:
            fs_err = err
        finally:
            if not fs_err:
                rm_file = self._cache.pop(_path)
                logger.debug("Removed file {}".format(rm_file))
            else:
                raise fs_err

    def openbin(self, path, mode="r", buffering=-1, **options):
        """
        Open a file in the ConpotFS in binary mode.
        """
        logger.debug("Opening file {} with mode {}".format(path, mode))
        _path = self.norm_path(path)
        _bin_mode = Mode(mode).to_platform_bin()
        _bin_mode = _bin_mode.replace("t", "") if "t" in _bin_mode else _bin_mode
        _parent_fs = self.delegate_fs()
        self.check()
        binary_file = _custom_conpot_file(
            file_system=self,
            parent_fs=_parent_fs,
            path=_path,
            mode=_bin_mode,
            encoding=None,
        )
        return binary_file

    def open(
        self,
        path,  # type: Text
        mode="r",  # type: Text
        buffering=-1,  # type: int
        encoding=None,  # type: Optional[Text]
        newline="",  # type: Text
        line_buffering=False,  # type: bool
        **options  # type: Any
    ):
        _open_mode = Mode(mode)
        base.validate_open_mode(mode)
        self.check()
        _path = self.norm_path(path)
        _parent_fs = self.delegate_fs()
        _encoding = encoding or "utf-8"
        file = _custom_conpot_file(
            file_system=self,
            parent_fs=_parent_fs,
            path=_path,
            mode=_open_mode.to_platform(),
            buffering=buffering,
            encoding=encoding,
            newline=newline,
            line_buffering=line_buffering,
        )
        return file

    def setbinfile(self, path, file):
        with self.openbin(path, "wb") as dst_file:
            copy_files(file, dst_file)
        self.setinfo(path, {})

    def move(self, src_path, dst_path, overwrite=False):
        if self.getinfo(src_path).is_dir:
            raise fs.errors.FileExpected(src_path)
        with self.openbin(src_path, "rb") as read_file:
            with self.openbin(dst_path, "wb") as dst_file:
                copy_files(read_file, dst_file)
        self.setinfo(src_path, {})
        self.setinfo(dst_path, {})
        self.remove(src_path)

    def copy(self, src_path, dst_path, overwrite=False):
        if self.getinfo(src_path).is_dir:
            raise fs.errors.FileExpected(src_path)
        with self.openbin(src_path, "rb") as read_file:
            with self.openbin(dst_path, "wb") as dst_file:
                copy_files(read_file, dst_file)
        self.setinfo(src_path, {})
        self.setinfo(dst_path, {})

    # -----------------------------------------------------------
    # Custom "getter" methods overwriting behaviour FS library methods
    # Data is retrieved from the cached file-system.
    # -----------------------------------------------------------

    def opendir(self, path, factory=SubAbstractFS):
        return super(AbstractFS, self).opendir(path, factory=factory)

    def settimes(self, path, accessed=None, modified=None):
        if accessed or modified:
            self.delegate_fs().settimes(path, accessed, modified)
        self._cache[path].raw["details"]["accessed"] = fs.time.datetime_to_epoch(
            super(AbstractFS, self).getinfo(path, namespaces=["details"]).accessed
        )
        self._cache[path].raw["details"]["modified"] = fs.time.datetime_to_epoch(
            super(AbstractFS, self).getinfo(path, namespaces=["details"]).modified
        )

    def getinfo(self, path: str, get_actual: bool = False, namespaces=None):
        if get_actual or (not self.built_cache):
            return self._wrap_fs.getinfo(path, namespaces)
        else:
            try:
                # ensure that the path starts with '/'
                if path[0] != "/":
                    path = "/" + path
                info = {"basic": self._cache[path].raw["basic"]}
                if namespaces is not None:
                    if "details" in namespaces:
                        info["details"] = self._cache[path].raw["details"]
                    if "stat" in namespaces:
                        stat_cache = {
                            "st_uid": self._cache[path].raw["access"]["uid"],
                            "st_gid": self._cache[path].raw["access"]["gid"],
                            "st_atime": self._cache[path].raw["details"]["accessed"],
                            "st_mtime": self._cache[path].raw["details"]["modified"],
                            # TODO: Fix these to appropriate values
                            "st_mtime_ns": None,
                            "st_ctime_ns": None,
                            "st_ctime": None,
                        }
                        if isinstance(
                            self._cache[path].raw["access"]["permissions"], list
                        ):
                            stat_cache["st_mode"] = Permissions(
                                self._cache[path].raw["access"]["permissions"]
                            ).mode
                        else:
                            stat_cache["st_mode"] = (
                                self._cache[path].raw["access"]["permissions"].mode
                            )
                        self._cache[path].raw["stat"].update(stat_cache)
                        info["stat"] = self._cache[path].raw["stat"]
                        # Note that we won't be keeping tabs on 'lstat'
                    if "lstat" in namespaces:
                        info["lstat"] = self._cache[path].raw["lstat"]
                        info["lstat"] = self._cache[path].raw["lstat"]
                    if "link" in namespaces:
                        info["link"] = self._cache[path].raw["link"]
                    if "access" in namespaces:
                        info["access"] = self._cache[path].raw["access"]
                return Info(info)
            except KeyError:
                raise FilesystemError

    def listdir(self, path):
        logger.debug("Listing contents from directory: {}".format(self.norm_path(path)))
        self.setinfo(self.norm_path(path), {})
        return super(AbstractFS, self).listdir(self.norm_path(path))

    def getfile(self, path, file, chunk_size=None, **options):
        # check where there exists a copy in the cache
        if (
            self.exists(self.norm_path(path))
            and self.norm_path(path) in self._cache.keys()
        ):
            self.setinfo(self.norm_path(path), {})
            return self._wrap_fs.getfile(
                self.norm_path(path), file, chunk_size, **options
            )
        else:
            raise FilesystemError("Can't get. File does not exist!")

    def __del__(self):
        self._wrap_fs.close()
        if self._auto_clean:
            self.clean()

    # -----------------------------------------------------------
    # Methods defined for our needs.
    # -----------------------------------------------------------

    def create_jail(self, path):
        """Returns chroot jail sub system for a path"""
        logger.debug("Creating jail for path: {}".format(path))
        return self.opendir(path)

    def getcwd(self):
        return "/"

    def take_snapshot(self):
        """Take snapshot of entire filesystem.
        :rtype: dict
        """
        return {
            "date-time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "snapshot-data": self._cache,
        }

    def register_user(self, name: str, uid: int) -> None:
        """Store all user related data for the file system."""
        assert name and isinstance(name, str)
        self._users[uid] = {"user": name}
        # let us check for duplicate usernames/group names
        if len(set([v["user"] for k, v in self._users.items()])) != len(
            self._users.keys()
        ):
            _uname = self._users.pop(uid)["user"]
            raise FilesystemError(
                "Can't add users with duplicate uname: {}.".format(_uname)
            )

    def create_group(self, name: str, gid: int) -> None:
        """
        Store all group related data for the file system.
        :param name: Name of the group
        :param gid: gid of the group
        """
        assert name and isinstance(name, str)
        self._grps[gid] = {"group": name}
        if len(set([v["group"] for k, v in self._grps.items()])) != len(
            self._grps.keys()
        ):
            _gname = self._grps.pop(gid)
            raise FilesystemError(
                "Can't create groups with duplicate names: {}.".format(_gname)
            )

    def add_users_to_group(self, gid: int, uids: List) -> None:
        """Add list of users to an existing group
        :param gid: Group id of the group.
        :param uids: List of registers users that belong to this group
        """
        try:
            assert gid in self._grps.keys()
            for i in uids:
                if i not in self._users.keys():
                    raise AssertionError
            _uids = set(uids)
            if gid in self._user_grps.keys():
                self._user_grps[gid] += _uids
            else:
                self._user_grps[gid] = _uids
        except AssertionError:
            raise FilesystemError(
                "uid/gid does not exist in the file system. Please register it via create_group/"
                "register_user method."
            )

    def chown(
        self, fs_path: str, uid: int, gid: int, recursive: Optional[bool] = False
    ) -> None:
        """Change the owner of a specified file. Wrapper for os.chown
        :param fs_path: path or directory in the VFS where chown would be executed.
        :param uid: The `uid` of the user. **User must be a registered user on the filesystem or an exception would be
        thrown.
        :param gid: The `gid` of the group **Group must be a registered group on the filesystem or an exception would be
        thrown.
        :param recursive: If the given path is directory, then setting the recursive option to true would walk down the
        tree and recursive change permissions in the cache.

        ** `fs_path` needs to be the absolute path w.r.t to the vfs. If you are in a sub file system, please use
        `subvfs.getcwd()` to get the current directory. **
        """
        path = self.norm_path(fs_path)
        try:
            assert isinstance(uid, int) and isinstance(gid, int)
        except AssertionError:
            logger.exception("Integers expected got {} - {}".format(uid, gid))
        if self.isdir(path) or self.isfile(path):
            assert self._grps[gid] and self._users[uid]
            chown_cache = {
                "access": {
                    "user": self._users[uid]["user"],
                    "uid": self._users[uid],
                    "group": self._grps[gid]["group"],
                    "gid": self._grps[gid],
                }
            }
            if self.isdir(path) and recursive:
                if self.norm_path(path) != "/":
                    self.setinfo(path, chown_cache)
                sub_dir = self.opendir(path)
                for _path, _ in sub_dir.walk.info():
                    assert self._cache[self.norm_path(path + _path)]
                    self.setinfo(path + _path, chown_cache)
                sub_dir.close()
            else:
                self.setinfo(path, chown_cache)

        else:
            # TODO: map this to the actual output of os.chown
            raise FilesystemError("File not found for chown")

    def clean(self):
        """Clean (delete) temporary files created by this filesystem."""
        if self._cleaned:
            return

        try:
            logger.info(
                "Shutting down File System. Cleaning directories at {}".format(
                    self._temp_dir
                )
            )
            shutil.rmtree(self._temp_dir)
        except Exception as error:
            if not self._ignore_clean_errors:
                raise errors.OperationFailed(
                    msg="failed to remove temporary directory", exc=error
                )
        self._cleaned = True

    @property
    def root(self):
        """The root directory - where the filesystem is stored"""
        return self._temp_dir

    def stat(self, path):
        """Perform a stat() system call on the given path.
        :param path: (str) must be protocol relative path
        """
        assert path, isinstance(path, str)
        self.setinfo(self.norm_path(path), {})
        return self.getinfo(path, namespaces=["stat"]).raw["stat"]

    def readlink(self, path):
        """Perform a readlink() system call. Return a string representing the path to which a symbolic link points.
        :param path: (str) must be protocol relative path
        """
        assert path, isinstance(path, str)
        self.setinfo(self.norm_path(path), {})
        return self.getinfo(path, get_actual=True, namespaces=["link"]).raw["link"][
            "target"
        ]

    def format_list(self, basedir, listing):
        """
        Return an iterator object that yields the entries of given directory emulating the "/bin/ls -lA" UNIX command
        output.
        This is how output should appear:
        -rw-rw-rw-   1 owner   group    7045120 Sep 02  3:47 music.mp3
        drwxrwxrwx   1 owner   group          0 Aug 31 18:50 e-books
        -rw-rw-rw-   1 owner   group        380 Sep 02  3:40 module.py

        :param basedir: (str) must be protocol relative path
        :param listing: (list) list of files to needed for output.
        """
        assert isinstance(basedir, str), basedir
        basedir += "/" if basedir[-1:] != "/" else basedir
        now = time.time()
        for basename in listing:
            file = self.norm_path(
                basedir + basename
            )  # for e.g. basedir = '/' and basename = test.png.
            # So file is '/test.png'
            try:
                st = self.stat(file)
            except (fs.errors.FSError, FilesystemError):
                raise
            permission = filemode(Permissions.create(st["st_mode"]).mode)
            if self.isdir(file):
                permission = permission.replace("?", "d")
            elif self.isfile(file):
                permission = permission.replace("?", "-")
            elif self.islink(file):
                permission = permission.replace("?", "l")
            nlinks = st["st_nlink"]
            size = st["st_size"]  # file-size
            uname = self.getinfo(path=file, namespaces=["access"]).user
            # |-> pwd.getpwuid(st['st_uid']).pw_name would fetch the user_name of the actual owner of these files.
            gname = self.getinfo(path=file, namespaces=["access"]).group
            # |-> grp.getgrgid(st['st_gid']).gr_name would fetch the user_name of the actual of these files.
            mtime = time.gmtime(
                fs.time.datetime_to_epoch(
                    self.getinfo(file, namespaces=["details"]).modified
                )
            )
            if (now - st["st_mtime"]) > (180 * 24 * 60 * 60):
                fmtstr = "%d  %Y"
            else:
                fmtstr = "%d %H:%M"
            mtimestr = "%s %s" % (
                months_map[mtime.tm_mon],
                time.strftime(fmtstr, mtime),
            )
            if (st["st_mode"] & 61440) == stat.S_IFLNK:
                # if the file is a symlink, resolve it, e.g.  "symlink -> realfile"
                basename = basename + " -> " + self.readlink(file)
                # formatting is matched with proftpd ls output
            line = "%s %3s %-8s %-8s %8s %s %s\r\n" % (
                permission,
                nlinks,
                uname,
                gname,
                size,
                mtimestr,
                basename,
            )
            yield line

    def getmtime(self, path):
        """Return the last modified time as a number of seconds since the epoch."""
        self.setinfo(self.norm_path(path), {})
        return self.getinfo(path, namespaces=["details"]).modified

    # FIXME: refactor to os.access. Mode is missing from the params
    def access(
        self, path: str, name_or_id: Union[int, str] = None, required_perms: str = None
    ):
        """
        Returns bool w.r.t  the a user/group has permissions to read/write/execute a file.
        This is a wrapper around os.access. But it would accept name or id instead of of just ids.
        Also it can accept required permissions in the form of strings rather than os.F_OK, os.R_OK, os.W_OK etc.

        *Implementation Note*: First we would check whether the current user has the required permissions. If not,
        then we check the group to which this user belongs to. Finally if the user's group also does not meet the
        perms we check for other permissions.
        """
        try:
            _path = self.norm_path(path)
            _perms = self.getinfo(_path, namespaces=["access"]).permissions
            _uid = self.getinfo(_path, namespaces=["access"]).uid
            _gid = self.getinfo(_path, namespaces=["access"]).gid
            if isinstance(required_perms, int):
                if required_perms == F_OK:
                    return True
                elif required_perms == R_OK:
                    required_perms = "r"
                elif required_perms == W_OK:
                    required_perms = "w"
            # first we need to find the uid - in case username is provided instead of uid.
            if isinstance(name_or_id, str):
                # must be username or group name
                # fetch the uid/gid of that uname/gname
                [_id] = [k for k, v in self._users.items() if v == {"user": name_or_id}]
            else:
                _id = name_or_id
            # find the gid of this user.
            _grp_id = None
            # FIXME: The above operation can cause incorrect results if one user belongs to more than one group.
            for key, values in self._user_grps.items():
                if _id in values:
                    _grp_id = key
            if _id is not None:
                if _id == _uid:
                    # provided id is the owner
                    return all([_perms.check("u_" + i) for i in list(required_perms)])
                elif _grp_id and (_grp_id == _gid):
                    # provided id is not the owner but belongs to that grp.
                    # That means we would check it's group permissions.
                    return all([_perms.check("g_" + i) for i in list(required_perms)])
                else:
                    # id not equal to either in uid/gid
                    # check other permissions
                    return all([_perms.check("o_" + i) for i in list(required_perms)])
        except (ValueError, AssertionError, KeyError, fs.errors.FSError) as err:
            logger.info("Exception has occurred while doing fs.access: {}".format(err))
            logger.info("Returning False to avoid conpot crash")
            return False

    def get_permissions(self, path):
        """Get permissions for a particular user on a particular file/directory in 'rwxrx---' format"""
        _path = self.norm_path(path)
        self.setinfo(self.norm_path(path), {})
        _perms = self.getinfo(_path, namespaces=["access"]).permissions
        return _perms.as_str()

    def chmod(self, path: str, mode: oct, recursive: bool = False) -> None:
        """Change file/directory mode.
        :param path: Path to be modified.
        :param mode: Operating-system mode bitfield. Must be in octal's form.
        Eg: chmod with (mode=0o755) = Permissions(user='rwx', group='rx', other='rx')
        :param recursive: If the path is directory, setting recursive to true would change permissions to sub folders
        and contained files.
        :type recursive: bool
        """
        assert isinstance(mode, str) or isinstance(mode, int)
        if isinstance(mode, str):
            # convert mode to octal
            mode = int(mode, 8)
        chmod_cache_info = {"access": {"permissions": Permissions.create(mode)}}
        if self.isdir(path) and recursive:
            if path != "/":
                self.setinfo(path, chmod_cache_info)
            # create a walker
            sub_dir = self.opendir(path)
            for _path, _ in sub_dir.walk.info():
                self.setinfo(path + _path, chmod_cache_info)
            sub_dir.close()
        else:
            self.setinfo(path, chmod_cache_info)

    def mount_fs(
        self,
        dst_path: str,
        fs_url: str = None,
        owner_uid: Optional[int] = 0,
        group_gid: Optional[int] = 0,
        perms: Optional[Union[Permissions, int]] = 0o755,
    ) -> subfs.SubFS:
        """
        To be called to mount individual filesystems.
        :param fs_url: Location/URL for the file system that is to be mounted.
        :param dst_path: Place in the Conpot's file system where the files would be placed. This should be relative to
        FS root.
        :param owner_uid: The owner `user` **UID** of the directory and the sub directory. Default is root/
        :param group_gid: The group 'group` to which the directory beings. Defaults to root.
        :param perms: Permission UMASK
        """
        path = self.norm_path(dst_path)
        if self.exists(path) and self.isdir(path):
            if not fs_url:
                new_dir = self.create_jail(path)
            else:
                temp_fs = open_fs(fs_url=fs_url)
                with temp_fs.lock():
                    new_dir = self.opendir(
                        self.norm_path(dst_path), factory=SubAbstractFS
                    )
                    mirror.mirror(src_fs=temp_fs, dst_fs=new_dir)
                    self._cache.update(
                        {
                            path: info
                            for path, info in self.walk.info(
                                namespaces=["basic", "access", "details", "stat"]
                            )
                        }
                    )
                del temp_fs  # delete the instance since no longer required
            new_dir.default_uid, new_dir.default_gid = owner_uid, group_gid
            new_dir.chown("/", uid=owner_uid, gid=group_gid, recursive=True)
            new_dir.chmod("/", mode=perms, recursive=True)
            return new_dir
        else:
            raise fs.errors.DirectoryExpected("{} path does not exist".format(path))

    def __getattribute__(self, attr):
        # Restrict access to methods that are implemented in AbstractFS class - Calling methods from base class may
        # not be safe to use.
        # FIXME: Need to fix these for only allow methods that are defined here.
        if not WrapFS:
            return
        method_list = [x for x, y in WrapFS.__dict__.items() if type(y) == FunctionType]
        if attr in method_list:
            if attr in super(AbstractFS, self).__getattribute__(
                "__dict__"
            ).keys() or attr not in ["match", "settext"]:
                # These methods have been overwritten and are safe to use.
                try:
                    return super(AbstractFS, self).__getattribute__(attr)
                except KeyError as ke:
                    raise FilesystemError("Invalid Path : {}".format(ke))
            else:
                raise NotImplementedError(
                    "The method requested is not supported by Conpot's VFS"
                )
        else:
            try:
                return super(AbstractFS, self).__getattribute__(attr)
            except KeyError as ke:
                raise FilesystemError("Invalid Path : {}".format(ke))
