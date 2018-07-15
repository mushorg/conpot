import fs
import time
import logging
import sys
import stat
import typing
import tempfile
import shutil
from datetime import datetime
from os import F_OK, R_OK, W_OK
from typing import Optional, Union, Text, Any
from fs import open_fs, mirror, errors, subfs, permissions
from fs.time import datetime_to_epoch
from fs.subfs import SubFS
from fs.wrapfs import WrapFS
from fs.permissions import Permissions
from fs.osfs import Info
from conpot.protocols.ftp.ftp_utils import months_map
from types import FunctionType
_F = typing.TypeVar('_F', bound='FS', covariant=True)

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

class FilesystemError(fs.errors.FSError):
    """Custom class for filesystem-related exceptions."""


class SubAbstractFS(SubFS[_F], typing.Generic[_F]):
    """
    Creates a chroot jail sub file system. Each protocol can have an instance of this class. Use AbstractFS's
    create_jail method to access this. You won't be able to cd into an `up` directory.
    """
    def __init__(self, parent_fs, path):
        self.parent_fs = parent_fs
        super(SubAbstractFS, self).__init__(parent_fs, path)

    def getcwd(self):
        return self._sub_dir

    @property
    def root(self):
        return self.parent_fs.root + self.getcwd()

    def __getattr__(self, item):
        if hasattr(self.parent_fs, item):
            return getattr(self.parent_fs, item)
        else:
            raise NotImplementedError('Conpot\'s File System does not currently support method: {}'.format(item))


class AbstractFS(WrapFS):
    """
    AbstractFS distinguishes between "real" filesystem paths and "virtual" ftp paths emulating a UNIX chroot jail
    where the user can not escape its home directory (example: real "/home/user" path will be seen as "/" by the client)

    This class exposes common fs wrappers around all os.* calls involving operations against the filesystem like
    creating files or removing directories (such as listdir etc.)
    """

    def __init__(self,
                 src_path: str,
                 create_mode: int = 0o777,      # Default file system permissions.
                 temp_dir: Union[str, None]=None,
                 identifier: Optional[str]='__conpot__',
                 auto_clean: Optional[bool]=True,
                 ignore_clean_errors: Optional[bool]=True
                 ) -> None:
        self._cwd = self.getcwd()  # keep track of the current working directory
        self._cache = {}   # Storing all cache of the file system
        self.identifier = identifier.replace('/', '-')
        self._auto_clean = auto_clean
        self._ignore_clean_errors = ignore_clean_errors
        self.temp_dir = temp_dir
        self._cleaned = False
        self._built_cache = False
        # Create our file system
        self._temp_dir = tempfile.mkdtemp(
            prefix=(self.identifier or "ConpotTempFS"),
            dir=self.temp_dir
        )
        # open various filesystems that would be used by Conpot
        try:
            self.vfs = open_fs(self._temp_dir)
            super(AbstractFS, self).__init__(self.vfs)
        except fs.errors.FSError as fs_err:
            logger.exception('File System exception occurred! {}'.format(fs_err))
        # Copy all files from src_path into our file system
        logger.info('Initializing Virtual File System at {}. Source specified : {}\n Please wait while the '
                    'system copies all specified files'.format(self._temp_dir, src_path))
        # There are some fs native file system methods that are very useful and are safe for use in our FS - as is.
        # We would set them here,
        # self.validatepath = super(AbstractFS, self).validatepath
        # self.exists = super(AbstractFS, self).exists
        # self.close = super(AbstractFS, self).close
        # keep records related to users and groups
        self.default_uid = 0
        self.default_gid = 0
        self.default_perms = create_mode
        self._users = {
            0: {'user': 'root'}
        }
        self._grps = {
            0: {'group': 'root'},    # TODO: Mechanism to have users belonging to groups.
        }
        self._initialize_fs(src_path=src_path)

    def norm_path(self, path):
        path = '/' if path == '.' else path
        _path = self.validatepath(self._cwd + path) if self._cwd not in path else self.validatepath(path)
        try:
            if _path is not '/':
                assert self._cache[_path]
            return _path
        except (KeyError, AssertionError):
            raise FilesystemError('Invalid Path: {}'.format(_path))

    def check_exists(self, path):
        path = '/' if path == '.' else path
        try:
            if path is not '/':
                assert self._cache[path]
                return path
        except (KeyError, AssertionError):
            raise FilesystemError('Invalid Path: {}'.format(path))

    def _initialize_fs(self, src_path: str) -> None:
            """
            Copies all data into Conpot's created fs folder and builds up the cache.
            :param src_path: FS URLS
            """
            # copy all contents from the source path the filesystem.
            src_fs = open_fs(src_path)
            logger.debug('Building up file system: copying contents from the source path {}'.format(src_path))
            with src_fs.lock():
                mirror.mirror(src_fs=src_fs, dst_fs=self.vfs)
                self._cache.update({path: info for path, info in self.walk.info(namespaces=['basic', 'access',
                                                                                            'details', 'stat'])})
                self._cache['/'] = self._wrap_fs.getinfo('/', namespaces=['basic', 'access', 'details', 'stat', 'link'])
                self.chown('/', self.default_uid, self.default_gid, recursive=True)
                self.chmod('/', self.default_perms, recursive=True)
                self._built_cache = True   # FS has been built. Now all info must be accessed from cache.
            del src_fs

    def __str__(self):
        return "<Conpot AbstractFS '{}'>".format(self._temp_dir)

    __repr__ = __str__

    # -----------------------------------------------------------
    # Custom "setter" methods overwriting behaviour FS library methods
    # We need to update our cache in such cases.
    # -----------------------------------------------------------
    def setinfo(self, path, info):
        """
        Higher level function to directly change values in the file system.
        :param path: path of the file that is to be changed
        :param info: Raw Info object. Please check pyfilesystem2's docs for more info.
        """
        assert path and isinstance(path, str)
        path = self.norm_path(path)
        if 'lstat' not in info:
            try:
                if 'details' in info:
                    details = info['details']
                    if 'accessed' in details or 'modified' in details:
                        return self._wrap_fs.setinfo(path, info)
            finally:
                try:
                    assert self._cache[path]
                except AssertionError:
                    # This is the first time we have seen this file. Let us create this entry.
                    logger.debug('Creating cache for file/directory : {}'.format(path))
                    self._cache[path] = self._wrap_fs.getinfo(path, namespaces=['basic', 'access', 'details', 'stat',
                                                                                'link'])
                # update the 'accessed' and 'modified' time.
                self._cache[path].raw['details']['accessed'] = fs.time.datetime_to_epoch(
                    self._wrap_fs.getinfo(path, namespaces=['details']).accessed
                )
                self._cache[path].raw['details']['modified'] = fs.time.datetime_to_epoch(
                    self._wrap_fs.getinfo(path, namespaces=['details']).modified
                )
                if 'access' in info:
                    access = info['access']
                    if 'permissions' in access:
                        self._cache[path].raw['access']['permissions'] = access['permissions']
                        self._cache[path].raw['details']['metadata_changed'] = fs.time.datetime_to_epoch(datetime.now())
                    if 'user' in access or 'uid' in access:
                        try:
                            if 'user' in access or ('user' in access and 'uid' in access):
                                self._cache[path].raw['access']['user'] = access['user']
                                [_uid] = [key for key, value in self._users.items()
                                          if value == {'user': access['user']}]
                                self._cache[path].raw['access']['uid'] = _uid
                                self._cache[path].raw['details']['metadata_changed'] = fs.time.datetime_to_epoch(
                                    datetime.now()
                                )
                            else:
                                # Must be 'uid' that is available.
                                self._cache[path].raw['access']['uid'] = access['uid']
                                self._cache[path].raw['access']['user'] = self._users[int(access['uid'])]['user']
                                self._cache[path].raw['details']['metadata_changed'] = fs.time.datetime_to_epoch(
                                    datetime.now()
                                )
                        except (TypeError, AssertionError, KeyError):
                            raise
                    if 'group' in access or 'gid' in access:
                        try:
                            if 'group' in access or ('group' in access and 'gid' in access):
                                self._cache[path].raw['access']['group'] = access['group']
                                [_gid] = [key for key, value in self._grps.items()
                                          if value == {'group': access['group']}]
                                self._cache[path].raw['access']['gid'] = _gid
                                self._cache[path].raw['details']['metadata_changed'] = fs.time.datetime_to_epoch(
                                    datetime.now()
                                )
                            else:
                                # Must be 'gid' that is available.
                                self._cache[path].raw['access']['gid'] = access['gid']
                                self._cache[path].raw['access']['group'] = self._users[int(access['gid'])]['group']
                                self._cache[path].raw['details']['metadata_changed'] = fs.time.datetime_to_epoch(
                                    datetime.now()
                                )
                        except (TypeError, AssertionError, KeyError):
                            raise
        else:
            raise FilesystemError('lstat is not currently supported!')

    def makedir(self,
                path,               # type: Text
                perms=None,         # type: Optional[int]
                recreate=False      # type: bool
                ):
        # make a directory in the file system. Also, update the cache about the directory.
        _path = self.norm_path(path)
        self._wrap_fs.makedir(_path)
        dir_perms = perms if perms else self.default_perms
        dir_cache = {
            'access': {
                'permissions': Permissions.create(dir_perms),
                'uid': self.default_uid,
                'gid': self.default_gid
            }
        }
        self.setinfo(_path, info=dir_cache)

    def rmdir(self, path):
        # removing a directory and finally block would clear the local cache.
        try:
            return self._wrap_fs.removedir(path)
        except fs.errors.FSError:
            raise
        finally:
            rm_dir = self._cache.pop(path)
            logger.debug('Removed directory {}'.format(rm_dir))

    def remove(self, path):
        """Remove a file from the file system."""
        try:
            return self._wrap_fs.remove(path)
        except fs.errors.FSError:
            raise
        finally:
            rm_file = self._cache.pop(self._cwd + path)
            logger.debug('Remove file {}'.format(rm_file))

    def open(self,
             path,                      # type: Text
             mode='r',                  # type: Text
             encoding=None,             # type: Optional[Text]
             newline='',                # type: Text
             line_buffering=False,      # type: bool
             **options                  # type: Any
             ):
        try:
            if not ('w' in mode or 'a' in mode):
                logging.debug('Opening file {} with mode {}'.format(self.norm_path(path), mode))
                return super(AbstractFS, self).open(self.norm_path(path), mode)
            else:
                logging.debug('Opening file {} with mode {}'.format(path, mode))
                return super(AbstractFS, self).open(path, mode)
        except fs.errors.FSError:
            raise
        finally:
            if (not any(sys.exc_info())) and ('w' in mode or 'a' in mode):
                self._cache.update({path: self.getinfo(path, get_actual = True,
                                                       namespaces=['basic', 'access', 'details', 'stat'])})
                self.chown(path, self.default_uid, self.default_gid)
                self.chmod(path, self.default_perms)
                logger.debug('Updating modified/access time')

    # -----------------------------------------------------------
    # Custom "getter" methods overwriting behaviour FS library methods
    # Data is retrieved from the cached file-system.
    # -----------------------------------------------------------

    def opendir(self, path, factory=SubAbstractFS):
        return super(AbstractFS, self).opendir(path, factory=factory)

    def getinfo(self, path: str, get_actual: bool = False, namespaces=None):
        if get_actual or (not self._built_cache):
            return self._wrap_fs.getinfo(path, namespaces)
        else:
            info = {'basic': self._cache[path].raw['basic']}
            if namespaces is not None:
                if 'details' in namespaces:
                    info['details'] = self._cache[path].raw['details']
                if 'stat' in namespaces:
                    stat_cache = {
                        'st_uid': self._cache[path].raw['access']['uid'],
                        'st_gid': self._cache[path].raw['access']['gid'],
                        'st_mode':  self._cache[path].raw['access']['permissions'].mode,
                        'st_atime': self._cache[path].raw['details']['accessed'],
                        'st_mtime': self._cache[path].raw['details']['modified'],
                        # TODO: Fix these to appropriate values
                        'st_mtime_ns': None,
                        'st_ctime_ns': None,
                        'st_ctime': None,
                    }
                    self._cache[path].raw['stat'].update(stat_cache)
                    info['stat'] = self._cache[path].raw['stat']
                    # Note that we won't be keeping tabs on 'lstat'
                if 'lstat' in namespaces:
                    info['lstat'] = self._cache[path].raw['lstat']
                    info['lstat'] = self._cache[path].raw['lstat']
                if 'link' in namespaces:
                    info['link'] = self._cache[path].raw['link']
                if 'access' in namespaces:
                    info['access'] = self._cache[path].raw['access']
            return Info(info)

    def listdir(self, path):
        logger.debug('Listing contents from directory'.format(self.norm_path(path)))
        try:
            return super(AbstractFS, self).listdir(self.norm_path(path))
        finally:
            self.setinfo(self.norm_path(path), {})

    def getfile(self, path, file, chunk_size=None, **options):
        # check where there exists a copy in the cache
        if self.exists(self.norm_path(path)) and self.norm_path(path) in self._cache.keys():
            return self._wrap_fs.getfile(self.norm_path(path), file, chunk_size, **options)
        else:
            raise FilesystemError('Can\'t get. File does not exist!')

    def __del__(self):
        self._wrap_fs.close()
        if self._auto_clean:
            self.clean()

    # -----------------------------------------------------------
    # Methods defined for our needs.
    # -----------------------------------------------------------

    def create_jail(self, path):
        """Returns chroot jail sub system for a path"""
        logger.debug('Creating jail for path: {}'.format(path))
        return self.opendir(path)

    def getcwd(self):
        return '/'

    def take_snapshot(self):
        """Take snapshot of entire filesystem.
        :rtype: dict
        """
        return {'date-time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'snapshot-data': self._cache}

    def register_user(self, name: str, uid: int) -> None:
        """Store all user related data for the file system."""
        assert name and isinstance(name, str)
        self._users[uid] = {'user': name}

    def create_group(self,  name: str, gid: int) -> None:
        """Store all group related data for the file system."""
        assert name and isinstance(name, str)
        self._grps[gid] = {'group': name}

    def chown(self, fs_path: str, uid: int, gid: int, recursive: Optional[bool]=False) -> None:
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
            logger.exception('Integers expected got {} - {}'.format(uid, gid))
        if self.exists(path):
            assert self._grps[gid] and self._users[uid]
            chown_cache = {
                'access': {
                    'user': self._users[uid]['user'],
                    'uid': self._users[uid],
                    'group': self._grps[gid]['group'],
                    'gid': self._grps[gid]
                }
            }
            if self.isdir(path) and recursive:
                if self.norm_path(path) is not '/':
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
            raise FilesystemError('File not found for chown')

    def clean(self):
        """Clean (delete) temporary files created by this filesystem."""
        logger.info('Shutting down File System. Cleaning directories at {}'.format(self._temp_dir))
        if self._cleaned:
            return

        try:
            shutil.rmtree(self._temp_dir)
        except Exception as error:
            if not self._ignore_clean_errors:
                raise errors.OperationFailed(
                    msg="failed to remove temporary directory",
                    exc=error
                )
        self._cleaned = True

    @property
    def root(self):
        """The root directory - where the filesystem is stored"""
        return self._temp_dir

    def chdir(self, path):
        """Change the current directory."""
        # TODO: check permissions
        try:
            assert path, isinstance(path, str)
            if self.isdir(path=self.getcwd() + path):
                self._cwd += path
            else:
                raise fs.errors.FSError('Directory {} does not exist.'.format(path))
        except AssertionError:
            raise
        except fs.errors.IllegalBackReference:
            raise

    def stat(self, path):
        """Perform a stat() system call on the given path.
        :param path: (str) must be protocol relative path
        """
        assert path, isinstance(path, str)
        return self.getinfo(path, namespaces=['stat']).raw['stat']

    def readlink(self, path):
        """Perform a readlink() system call. Return a string representing the path to which a symbolic link points.
        :param path: (str) must be protocol relative path
        """
        assert path, isinstance(path, str)
        return self.getinfo(path, namespaces=['link']).raw['link']['target']

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
        basedir += '/' if basedir[-1:] != '/' else basedir
        now = time.time()
        for basename in listing:
            file = basedir + basename  # for e.g. basedir = '/' and basename = test.png. So file is '/test.png'
            try:
                st = self.stat(file)
            except (fs.errors.FSError, FilesystemError):
                raise
            permission = Permissions.create(st['st_mode']).as_str()
            nlinks = st['st_nlink']
            size = st['st_size']  # file-size
            uname = self._users[st['st_uid']]['user']
            # |-> pwd.getpwuid(st['st_uid']).pw_name would fetch the user_name of the actual owner of these files.
            gname = self._grps[st['st_gid']]['group']
            # |-> grp.getgrgid(st['st_gid']).gr_name would fetch the user_name of the actual of these files.
            mtime = time.gmtime(st['st_mtime'])
            if (now - st['st_mtime']) > (180 * 24 * 60 * 60):
                fmtstr = "%d  %Y"
            else:
                fmtstr = "%d %H:%M"
            mtimestr = "%s %s" % (months_map[mtime.tm_mon], time.strftime(fmtstr, mtime))
            if (st['st_mode'] & 61440) == stat.S_IFLNK:
                # if the file is a symlink, resolve it, e.g.  "symlink -> realfile"
                basename = basename + " -> " + self.readlink(file)
                # formatting is matched with proftpd ls output
            line = "%s %3s %-8s %-8s %8s %s %s\r\n" % (permission, nlinks, uname, gname, size, mtimestr, basename)
            yield line

    def getmtime(self, path):
        """Return the last modified time as a number of seconds since the epoch."""
        return self.getinfo(path, namespaces=['details']).modified

    # FIXME: refactor to os.access. Mode is missing from the params
    def access(self, path: str, name_or_id: Union[int, str]=None, required_perms: str=None):
        """
            Returns bool w.r.t  the a user/group has permissions to read/write/execute a file.
            This is a wrapper around os.access. But it would accept name or id instead of of just ids.
            Also it can accept required permissions in the form of strings rather than os.F_OK, os.R_OK, os.W_OK etc.
        """
        # TODO: Currently users can't belong to groups. Manage through the group permissions.
        _path = self.norm_path(path)
        _perms = self.getinfo(_path, namespaces=['access']).permissions
        _uid = self.getinfo(_path, namespaces=['access']).uid
        _gid = self.getinfo(_path, namespaces=['access']).gid
        if isinstance(required_perms, int):
            if required_perms == F_OK:
                return True
            elif required_perms == R_OK:
                required_perms = 'r'
            elif required_perms == W_OK:
                required_perms = 'w'
        if isinstance(name_or_id, str):
            # must be username or group name
            # fetch the uid/gid of that uname/gname
            [_id] = [k for k, v in self._users.items() if v == {'user': name_or_id}]
            if _id is not None:
                if _id == _uid:
                    # provided id is the owner
                    return all([_perms.check('u_' + i) for i in list(required_perms)])
            else:
                [_id] = [k for k, v in self._grps.items() if v == {'group': name_or_id}]
                if _id == _gid:
                    # provided id is the group
                    return all([_perms.check('g_' + i) for i in list(required_perms)])
        else:
            # check other permissions
            return all([_perms.check('o_' + i) for i in list(required_perms)])

    def get_permissions(self, path):
        """Get permissions for a particular user on a particular file/directory in 'rwxrx---' format"""
        _path = self.norm_path(path)
        _perms = self.getinfo(_path, namespaces=['access']).permissions
        return _perms.as_str()

    def chmod(self, path: str, mode, recursive: bool = False) -> None:
        """Change file/directory mode.
        :param path: Path to be modified.
        :param mode: Operating-system mode bitfield.
        :param recursive: If the path is directory, setting recursive to true would change permissions to subfolders
        and contained files.
        :type recursive: bool
        """
        assert isinstance(mode, int)
        chmod_cache_info = {
                    'access': {
                        'permissions': permissions.Permissions.create(mode)
                    }
                }
        if self.isdir(path) and recursive:
            # self.setinfo(path, chmod_cache_info)
            # create a walker
            sub_dir = self.opendir(path)
            for _path, _ in sub_dir.walk.info():
                self.setinfo(path + _path, chmod_cache_info)
            sub_dir.close()
        else:
            self.setinfo(path, chmod_cache_info)

    def mount_fs(self,
                 dst_path: str,
                 fs_url: str = None,
                 owner_uid: Optional[int] = 0,
                 group_gid: Optional[int] = 0,
                 perms: Optional[Permissions] = 0o755
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
                return self.create_jail(path)
            else:
                temp_fs = open_fs(fs_url=fs_url)
                with temp_fs.lock():
                        new_dir = self.opendir(self.norm_path(dst_path), factory=SubAbstractFS)
                        mirror.mirror(src_fs=temp_fs, dst_fs=new_dir)
                        self.chown(new_dir.getcwd(), uid=owner_uid, gid=group_gid, recursive=True)
                        self.chmod(new_dir.getcwd(), mode=perms, recursive=True)
                        del temp_fs  # delete the instance since no longer required
                        return new_dir
        else:
            raise fs.errors.DirectoryExpected('{} path does not exists'.format(path))

    def __getattribute__(self, attr):
        # Restrict access to methods that are implemented in AbstractFS class - Calling methods from base class but may
        # not be safe to use.
        # FIXME: Need to fix these for only allow methods that are defined here.
        method_list = [x for x, y in WrapFS.__dict__.items() if type(y) == FunctionType]
        if attr in method_list:
            if attr in super(AbstractFS, self).__getattribute__('__dict__').keys() or \
                    attr not in ['match']:
                # These methods have been overwritten and are safe to use.
                return super(AbstractFS, self).__getattribute__(attr)
            else:
                raise NotImplementedError('The method requested is not supported by Conpot\'s VFS')
        else:
            return super(AbstractFS, self).__getattribute__(attr)


if __name__ == '__main__':
    import os
    test_dir = os.getcwd() + '/../../../../conpot23/ftp'
    os.chdir(test_dir)
    test = AbstractFS('.')
    print(test.norm_path('abhinav'))
    jail = test.create_jail('/abhinav')
    print('Jail :: ', jail.getcwd(), jail.root)
    print(test.root)
    print(test.listdir('.'))
    print(test._cache)
    print(test._cache['/test.py'].raw)
    print('Permissions for file \'/abhinav\': {}'.format(test.get_permissions('/abhinav')))
    print('---------------------')
    print('Check for owners/group change ')
    print('---------------------')
    [print(path, ' : ', test.getinfo(path, namespaces=['access']).user) for path in test.walk.files()]
    [print(path, ' : ', test.getinfo(path, namespaces=['access']).user) for path in test.walk.dirs()]
    # change them using chmod
    test.register_user('daniel', 2000)
    test.create_group('daniel', 3000)
    test.chown('/abhinav', uid=2000, gid=3000, recursive=True)
    print('Permissions: {} '.format(test.access('/abhinav', 2000, 'rwx')))
    test._cache['/test.py'].raw['access']['user'] = 'test_user'
    # view them to get a good idea of results.
    print('after owner change')
    [print(path, ' : ', test.getinfo(path, namespaces=['access']).user) for path in test.walk.files()]
    [print(path, ' : ', test.getinfo(path, namespaces=['access']).user) for path in test.walk.dirs()]
    # do chmod
    print('Permissions: {} '.format(test.access('/abhinav', 0, 'rwx')))
    # create a file - with user 'daniel'
    # create a directory with user 'daniel'
    # check the current permissions.
    print('---------------------')
    print('Formatted List of files : {}'.format(test.format_list('/abhinav', test.listdir('/abhinav'))))
    [print(i) for i in test.format_list('/abhinav', test.listdir('/abhinav'))]
    print(test.getmtime('/abhinav'))
    del test