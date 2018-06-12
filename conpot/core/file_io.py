from datetime import datetime
from slugify import slugify
from fs import open_fs, tempfs, mirror

import logging
logger = logging.getLogger(__name__)


def sanitize_file_name(name):
    """
    Ensure that file_name is legal. Slug the filename and store it onto the server.
    This would ensure that there are no duplicates as far as writing a file is concerned.
    :param name: Name of the file
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' - ' + slugify(name)


class FilesystemError(Exception):
    """Custom class for filesystem-related exceptions."""


class FileWriter(object):
    """
        Write a file chunk_size bytes at a time. Can be only accessed by the Protocol SubFS.
        ** A copy would be created in the data_fs **

        :param file_name: Name of the file to be written
    """
    def __init__(self, file_name):
        self.name = file_name
        self._f = self._open_file()

    def _open_file(self):
        logger.debug('Opening File {}'.format(self.name))
        return open(self.name, 'xb')

    def _flush(self):
        if self._f:
            self._f.flush()

    def write_chunk(self, data):
        bytes_written = self._f.write(data)
        logger.debug('Writing bytes of data to file {} - Contents {}'.format(self.name, data))

        return bytes_written

    def __del__(self):
        if self._f and not self._f.closed:
            self._f.close()


class AbstractFS(object):
    """
    AbstractFS distinguishes between "real" filesystem paths and "virtual" ftp paths emulating a UNIX chroot jail
    where the user can not escape its home directory (example: real "/home/user" path will be seen as "/" by the client)

        - Use AbstractFS.home_fs object to access the chroot jail FS
        - Use AbstractFS.root_fs object to access the global '/' FS

    This class exposes common fs wrappers around all os.* calls involving operations against the filesystem like
    creating files or removing directories (such as listdir etc.)
    Finally it would also store the uploads in a respective data_fs sub-directory. For later storage and analysis.

    NOTE: Every protocol must have an instance of this class. If protocol_src_dir is 'common' b/w protocols, they can
    share resources. All changes are reflected; Resetting of FS is done automatically with restart of Conpot.
    :param: (tempfs.TempFS) - Protocol fs root
    :param: (str) - Name of the protocol for which we are creating the vfs
    :param: (str) - Path to which the fs has to be initialized. This would be the real "user" home directory or root.
    :param: (osfs.OSFS) - for persistent storage of data.
    """
    def __init__(self, fs_root, protocol_name, protocol_src_dir, data_fs):
        assert isinstance(fs_root, tempfs.TempFS)
        self._root = '/'
        self._home = self._root + protocol_name
        self._cwd = self._home
        self.root_fs = fs_root  # Use the root_fs object to access the entire filesystem
        self.home_fs = None  # Use the home_fs object to access protocol only chroot jail filesystem
        self.data_fs = data_fs
        self._add_protocol(protocol_src_dir)

    def _add_protocol(self, src_root):
        # load the files from the path provided
        temp_fs = open_fs('osfs://' + src_root)
        # next, create a sub folder for the protocol
        # TODO: Enter the permissions of the folder here!?
        self.home_fs = self.root_fs.makedir(self._cwd)
        # copy the contents of the fs into a temp_fs
        mirror.mirror(src_fs=temp_fs, dst_fs=self.home_fs)
        # delete the osfs instance since no longer required
        del temp_fs

    @property
    def root(self):
        """The user root directory."""
        return self._root

    @property
    def home(self):
        """The user home directory."""
        return self._home

    @property
    def cwd(self):
        """The user current working directory."""
        return self._cwd

    @root.setter
    def root(self, path):
        assert isinstance(path, str), path
        self._root = path

    def chdir(self, path):
        """Change the current directory."""
        raise NotImplementedError

    def listdirinfo(self, path):
        """List the content of a directory."""
        raise NotImplementedError

    def chmod(self, path, mode):
        """Change file/directory mode."""
        raise NotImplementedError

    def stat(self, path):
        """Perform a stat() system call on the given path."""
        raise NotImplementedError

    def utime(self, path, timeval):
        """Perform a utime() call on the given path"""
        raise NotImplementedError

    def getmtime(self, path):
        """Return the last modified time as a number of seconds since the epoch."""
        raise NotImplementedError

    def format_list(self, path):
        """
        Return an iterator object that yields the entries of given directory emulating the "/bin/ls -lA" UNIX command
        output.
        This is how output should appear:
        -rw-rw-rw-   1 owner   group    7045120 Sep 02  3:47 music.mp3
        drwxrwxrwx   1 owner   group          0 Aug 31 18:50 e-books
        -rw-rw-rw-   1 owner   group        380 Sep 02  3:40 module.py
        """
        raise NotImplementedError