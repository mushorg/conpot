"""
This module is based on the original work done by pyftpdlib authors. This is customized version that supports
Conpot's virtual file system os.* wrappers and gevent support.
"""
from conpot.protocols.ftp.base_handler import FTPHandlerBase
import logging
import fs
import os
import gevent
from gevent import socket
from fs import errors
from conpot.core.file_io import FilesystemError
from conpot.protocols.ftp.ftp_utils import FTPPrivilegeException, get_data_from_iter
logger = logging.getLogger(__name__)


# Regarding Permissions:
# To change a directory as current directory we need permissions : rwx (CWD)| Also it has to be a directory. |
# To read a file we need : r permissions - It has to be a file | list files (LIST, NLST, STAT, MLSD, MLST, SIZE, MDTM
# RETR commands)
# To store a file to the server we need 'w' permissions - (STOR, STOU commands)
# To rename file or directory we need 'w' permissions (RNFR, RNTO)
# To delete file or directory we need 'w' permissions (DELE, RMD commands)
# To append data to an existing file (APPE command) we need 'w' permissions

class FTPCommandChannel(FTPHandlerBase):
    """
    FTP Command Responder. Implementation of RFC 959.
    """

    # -----------------------------------------------------------------------
    # There are some commands that do not require any kind of auth and permissions to run.
    # These also do not require us to have an established data channel. So let us get rid of those first.
    # Btw: These are - USER, PASS, HELP, NOOP, SYST, QUIT, SITE HELP

    # The USER command is used to verify users as they try to login.
    def do_USER(self, arg):
        """
        USER FTP command. If the user is already logged in, return 530 else 331 for the PASS command
        :param arg: username specified by the client/attacker
        """
        # first we need to check if the user is authenticated?
        if self.authenticated:
            self.respond(b'530 Cannot switch to another user.')
        else:
            self.username = arg
            self.respond(b'331 Now specify the Password.')

    def do_PASS(self, arg):
        if self.authenticated:
            self.respond(b"503 User already authenticated.")
        if not self.username:
            self.respond(b"503 Login with USER first.")
        if self.authentication_ok(user_pass=arg):
            self.respond(b'230 Log in Successful.')
        else:
            self.invalid_login_attempt += 1
            self.respond(b'530 Authentication Failed.')

    def do_HELP(self, arg):
        """Return help text to the client."""
        if arg:
            line = arg.upper()
            if line in self.config.COMMANDS:
                self.respond(b'214 %a' % self.config.COMMANDS[line]['help'])
            else:
                self.respond(b'501 Unrecognized command.')
        else:
            # provide a compact list of recognized commands
            def formatted_help():
                cmds = []
                keys = sorted([x for x in self.config.COMMANDS.keys()
                               if not x.startswith('SITE ')])
                while keys:
                    elems = tuple((keys[0:8]))
                    cmds.append(b' %-6a' * len(elems) % elems + b'\r\n')
                    del keys[0:8]
                return b''.join(cmds)

            _buffer = b'214-The following commands are recognized:\r\n'
            _buffer += formatted_help()
            self.respond(_buffer + b'214 Help command successful.')

    def do_NOOP(self, arg):
        """Do nothing. No params required. No auth required and no permissions required."""
        self.respond(b'200 I successfully done nothin\'.')

    def do_SYST(self, arg):
        """Return system type (always returns UNIX type: L8)."""
        # This command is used to find out the type of operating system
        # at the server.  The reply shall have as its first word one of
        # the system names listed in RFC-943.
        # Since that we always return a "/bin/ls -lA"-like output on
        # LIST we  prefer to respond as if we would on Unix in any case.
        self.respond(b'215 UNIX Type: L8')

    def do_QUIT(self, arg):
        self.respond(b'221 Bye.')
        self.disconnect_client = True

    def do_SITE_HELP(self, line):
        """Return help text to the client for a given SITE command."""
        if line:
            line = line.upper()
            if line in self.config.COMMANDS:
                self.respond(b'214 %a' % self.config.COMMANDS[line]['help'])
            else:
                self.respond(b'501 Unrecognized SITE command.')
        else:
            _buffer = b'214-The following SITE commands are recognized:\r\n'
            site_cmds = []
            for cmd in sorted(self.config.COMMANDS.keys()):
                if cmd.startswith('SITE '):
                    site_cmds.append(b' %a\r\n' % cmd[5:])
            _buffer_cmds = b''.join(site_cmds)
            self.respond(_buffer + _buffer_cmds + b'214 Help SITE command successful.')

    def do_PASV(self, arg):
        """
            Starts a Passive Data Channel using IPv4. We don't actually need to start the full duplex connection here.
            Just need to figure the host ip and the port. The DTP connection would start in each command.
        """
        if self._data_channel:
            self.stop_data_channel()
        self.active_passive_mode = 'PASV'
        # We are in passive mode. Here we would create a simple socket listener.
        self._data_listener_sock = gevent.socket.socket()
        self._data_sock = gevent.socket.socket()
        self._data_listener_sock.bind((self._local_ip, 0))
        ip, port = self._data_listener_sock.getsockname()
        self.respond('227 Entering Passive Mode (%s,%u,%u).' % (','.join(ip.split('.')), port >> 8 & 0xFF,
                                                                port & 0xFF))
        try:
            self._data_listener_sock.listen(1)
            self._data_listener_sock.settimeout(5)  # Timeout for ftp client to send info
            logger.info('Client {} entering FTP passive mode'.format(self.client_address))
            self._data_sock, (self.cli_ip, self.cli_port) = self._data_listener_sock.accept()
            logger.info('Client {} provided IP {} and Port {} for PASV connection.'.format(
                self.client_address, self.cli_ip, self.cli_port)
            )
            logger.info('FTP: starting data channel for client {}'.format(self.client_address))
            self._data_listener_sock.close()
        except (socket.error, socket.timeout) as se:
            logger.info('Can\'t switch to PASV mode.  Error occurred: {}'.format(str(se)))
            if self._data_channel:
                self.stop_data_channel()

    def do_PORT(self, arg):
        """
            Starts an active data channel by using IPv4. We don't actually need to start the full duplex connection here.
            Just need to figure the host ip and the port. The DTP connection would start in each command.
        """
        if self._data_channel:
            self.stop_data_channel()
        self.active_passive_mode = 'PORT'
        try:
            addr = list(map(int, arg.split(',')))
            if len(addr) != 6:
                raise ValueError
            for x in addr[:4]:
                if not 0 <= x <= 255:
                    raise ValueError
            ip = '%d.%d.%d.%d' % tuple(addr[:4])
            port = (addr[4] * 256) + addr[5]
            if not 0 <= port <= 65535:
                raise ValueError
        except (ValueError, OverflowError):
            self.respond("501 Invalid PORT format.")
            return
        self.cli_ip, self.cli_port = ip, port
        self._data_sock = gevent.socket.socket()
        try:
            self._data_sock.connect((self.cli_ip, self.cli_port))
            logger.info('Client {} entered FTP active mode'.format(self.client_address))
            logger.info('Client {} provided IP {} and Port for PORT connection.'.format(
                self.client_address, self.cli_ip, self.cli_port)
            )
            self.respond(b'200 PORT Command Successful.')
            logger.info('FTP: starting data channel for client {}'.format(self.client_address))
        except socket.error:
            logger.info('Can\'t switch to Active(PORT) mode. Error occurred: {}'.format(str(se)))
            if self._data_channel:
                self.stop_data_channel()

    def do_MODE(self, line):
        """Set data transfer mode ("S" is the only one supported (noop))."""
        mode = line.upper()
        if mode == 'S':
            self.respond(b'200 Transfer mode set to: S')
        elif mode in ('B', 'C'):
            self.respond(b'504 Unimplemented MODE type.')
        else:
            self.respond(b'501 Unrecognized MODE type.')

    def do_PWD(self, arg):
        """Return the name of the current working directory to the client."""
        pwd = self.config.vfs.norm_path(self.root + self.working_dir)
        try:
            assert isinstance(pwd, str), pwd
            _pwd = '257 "{}" is the current directory.'.format(pwd)
            self.respond(_pwd.encode())
        except AssertionError:
            logger.info('FTP CWD specified is not unicode. {}'.format(pwd))
            self.respond(b'FTP CWD not unicode.')

    def do_TYPE(self, line):
        """Set current type data type to binary/ascii"""
        data_type = line.upper().replace(' ', '')
        if data_type in ("A", "L7"):
            self.respond(b'200 Type set to: ASCII.')
            self._current_type = 'a'
        elif data_type in ("I", "L8"):
            self.respond(b'200 Type set to: Binary.')
            self._current_type = 'i'
        else:
            self.respond(b'504 Unsupported type "%a".' % line)

    def do_SITE_CHMOD(self, path, mode):
        """Change file mode. On success return a (file_path, mode) tuple."""
        try:
            # Note: although most UNIX servers implement it, SITE CHMOD is not
            # defined in any official RFC.
            # TODO: check whether a user has permissions to do a chmod?!
            assert len(mode) in (3, 4)
            for x in mode:
                assert 0 <= int(x) <= 7
            mode = int(mode, 8)
            # To do a chmod user needs to be the owner of the file.
            self.config.vfs.chmod(path, mode)
            self.respond(b'200 SITE CHMOD successful.')
        except (AssertionError, ValueError):
            self.respond(b"501 Invalid SITE CHMOD format.")
        except (fs.errors.FSError, FilesystemError, FTPPrivilegeException):
            self.respond(b'550 SITE CHMOD command failed.')

    def do_MDTM(self, path):
        """Return last modification time of file to the client as an ISO
        3307 style timestamp (YYYYMMDDHHMMSS) as defined in RFC-3659.
        On success return the file path, else None.
        """
        try:
            # FIXME: check whether the current user has the permissions for MDTM
            if not self.config.vfs.isfile(path):
                _msg = '550 {} is not retrievable'.format(path)
                self.respond(_msg.encode())
                return
            m_time = '213 {}'.format(self.config.vfs.getmtime(path).strftime("%Y%m%d%H%M%S"))
            self.respond(m_time.encode())
        except (ValueError, fs.errors.FSError, FilesystemError, FTPPrivilegeException):
            # It could happen if file's last modification time
            # happens to be too old (prior to year 1900)
            self.respond('550 Can\'t determine file\'s last modification time.')

    def do_SIZE(self, path):
        """Return size of file in a format suitable for using with RESTart as defined in RFC-3659."""
        try:
            # FIXME: check whether the current user has the permissions for SIZE
            path = self.config.vfs.norm_path(path)
            if self._current_type == 'a':
                self.respond(b'550 SIZE not allowed in ASCII mode.')
                return
            # If the file is a sym-link i.e. not readable, send not retrievable
            if not self.config.vfs.isfile(path):
                self.respond(b'550 is not retrievable.')
                return
            else:
                size = self.config.vfs.getsize(path)
                self.respond(b'213 %a' % size)
        except (OSError, fs.errors.FSError) as err:
            self.respond(b'550 %a.' % self._log_err(err))

    def do_MKD(self, path):
        """
        Create the specified directory. On success return the directory path, else None.
        """
        try:
            # In order to create a directory the current user must have 'w' permissions for the parent directory
            # of current path.
            self.check_perms(perms='w', path=self.working_dir)
            self.config.vfs.makedir(path)
            _mkd = '257 "{}" directory created.'.format(self.root + path)
            self.respond(_mkd)
        except (FilesystemError, fs.errors.FSError, FTPPrivilegeException):
            self.respond(b'550 Create directory operation failed.')

    def do_RMD(self, path):
        """Remove the specified directory. On success return the directory path, else None.
        """
        if path == self.working_dir or path == '/':
            self.respond(b'550 Can\'t remove root directory.')
            return
        try:
            _path = self.working_dir + path
            # In order to create a directory the current user must have 'w' permissions for the current directory
            self.check_perms(perms='w', path=_path)
            self.config.vfs.removedir(_path)
            self.respond(b'250 Directory removed.')
        except (fs.errors.FSError, FilesystemError, FTPPrivilegeException):
            self.respond(b'550 Remove directory operation failed.')

    def do_CWD(self, path):
        """Change the current working directory."""
        # Temporarily join the specified directory to see if we have permissions to do so, then get back to original
        # process's current working directory.
        try:
            init_cwd = self.working_dir
            # make sure the current user has permissions to the new dir. To change the directory, user needs to have
            # executable permissions for the directory
            self.check_perms(perms='x', path=path)
            self.working_dir = self.config.vfs.norm_path(path)
            logger.info('Changing current directory {} to {}'.format(init_cwd, self.working_dir))
            _cwd = '250 "{}" is the current directory.'.format(self.config.vfs.norm_path(self.root +
                                                                                         self.working_dir))
            self.respond(_cwd.encode())
        except (fs.errors.FSError, FilesystemError, FTPPrivilegeException):
            self.respond(b'550 Failed to change directory.')

    def do_CDUP(self, arg):
        """Change into the parent directory.
        On success return the new directory, else None.
        """
        # Note: RFC-959 says that code 200 is required but it also says
        # that CDUP uses the same codes as CWD.
        return self.do_CWD(path='/'.join([self.config.vfs.norm_path(self.working_dir), '../']))

    def do_DELE(self, path):
        """Delete the specified file."""
        try:
            # FIXME: check whether the current user has the permissions for DELE
            self.config.vfs.remove(path)
            self.respond(b'250 File removed.')
        except (fs.errors.FSError, FilesystemError, FTPPrivilegeException):
            self.respond(b'550 Failed to delete file.')

    def do_ALLO(self, arg):
        """Allocate bytes for storage (noop)."""
        # not necessary (always respond with 202)
        self.respond(b'202 No storage allocation necessary.')

    def do_RNFR(self, path):
        """Rename the specified (only the source name is specified
        here, see RNTO command)"""
        try:
            assert isinstance(path, str)
            assert self.config.vfs.exists(path)
            if self.config.vfs.norm_path(path) == '/':
                self.respond(b"550 Can't rename home directory.")
            else:
                self._rnfr = path
                self.respond(b"350 Ready for destination name.")
        except (AssertionError, fs.errors.FSError, FilesystemError, FTPPrivilegeException):
            self.respond(b'550 No such file or directory.')

    def do_RNTO(self, dst_path):
        """Rename file (destination name only, source is specified with RNFR)."""
        try:
            # TODO: check for rename permissions
            assert isinstance(dst_path, str)
            if not self._rnfr:
                self.respond(b"503 Bad sequence of commands: use RNFR first.")
                return
            src = self._rnfr
            self._rnfr = None
            # currently ony support rename of files - not folders.
            if self.config.vfs.isdir(src):
                raise FilesystemError
            assert self.working_dir in src
            assert self.working_dir in dst_path
            # FIXME: use os.path.split : _basedir, _file = os.path.split()
            _path, _file = self.working_dir, src.replace(self.working_dir, '/')
            _dst_file = dst_path.replace(self.working_dir, '/')
            if _file != _dst_file:
                logger.info('Renaming file from {} to {}'.format(self.root + _path + _file,
                                                                 self.root + _path + _dst_file))
                self.config.vfs.rename_file(self.config.vfs.norm_path(_path), _file, _dst_file)
            self.respond(b"250 Renaming ok.")
        except (ValueError, AssertionError, fs.errors.FSError, FilesystemError, FTPPrivilegeException):
            self.respond(b'550 File rename operation failed.')

    def do_STAT(self, path):
        """If invoked without parameters, returns general status information about the FTP server process.
        If a parameter is given, acts like the LIST command, except that data is sent over the command
        channel (no PORT or PASV command is required).
        """
        # return STATus information about ftp data connection
        if not path:
            s = list()
            s.append('Connected to: %s:%s' % self.request.getsockname()[:2])
            if self.authenticated:
                s.append('Logged in as: %s' % self.username)
            else:
                if not self.username:
                    s.append("Waiting for username.")
                else:
                    s.append("Waiting for password.")
            if self._current_type == 'a':
                _type = 'ASCII'
            else:
                _type = 'Binary'
            s.append("TYPE: %s; STRUcture: File; MODE: Stream" % _type)
            # FIXME: add this when data channel is running.
            # if self._data_sock is not None:
            #     s.append('Passive data channel waiting for connection.')
            # elif self._data_channel is not None:
            #     bytes_sent = self.data_channel.tot_bytes_sent
            #     bytes_recv = self.data_channel.tot_bytes_received
            #     elapsed_time = self.data_channel.get_elapsed_time()
            #     s.append('Data connection open:')
            #     s.append('Total bytes sent: %s' % bytes_sent)
            #     s.append('Total bytes received: %s' % bytes_recv)
            #     s.append('Transfer elapsed time: %s secs' % elapsed_time)
            # else:
            #     s.append('Data connection closed.')

            self.respond('211-FTP server status:\r\n')
            self.respond(''.join([' %s\r\n' % item for item in s]))
            self.respond('211 End of status.')
        # return directory LISTing over the command channel
        else:
            line = self.config.vfs.norm_path(path)
            try:
                if self.config.vfs.isdir(path):
                    listing = self.config.vfs.listdir(path)
                    # RFC 959 recommends the listing to be sorted.
                    listing.sort()
                    iterator = self.config.vfs.format_list(path, listing)
                else:
                    basedir, filename = os.path.split(path)
                    self.config.stat(path)
                    iterator = self.config.vfs.format_list(basedir, [filename])
                _status = '213-Status of "{}":\r\n'.format(line)
                _status += get_data_from_iter(iterator)
                _status += '213 End of status.'
                self.respond(_status.encode())
            except (OSError, FilesystemError, AssertionError, fs.errors.FSError, FTPPrivilegeException):
                self.respond(b'550 STAT command failed.')

    # -- Data Channel related commands --

    def do_STRU(self, arg):
        pass

    def do_ABOR(self, arg):
        """
            Aborts a file transfer currently in progress.
        """
        # There are 3 cases here.
        # case 1: ABOR while no data channel is opened : return 225
        if (self.active_passive_mode is None and
                self._data_sock is None):
            self.respond(b'225 No transfer to abort.')
        else:
            # a PASV or PORT was received but connection wasn't made yet
            if self.active_passive_mode is not None or self._data_sock is not None:
                self.abort = True
                self.respond(b'225 ABOR command successful; data channel closed.')
            # If a data transfer is in progress the server must first
            # close the data connection, returning a 426 reply to
            # indicate that the transfer terminated abnormally, then it
            # must send a 226 reply, indicating that the abort command
            # was successfully processed.
            # If no data has been transmitted we just respond with 225
            # indicating that no transfer was in progress.
            if self._data_sock is not None:
                if not self.abort:
                    self.abort = True
                    self.respond(b'426 Transfer aborted via ABOR.')
                    self.respond(b'226 ABOR command successful.')
                else:
                    self.abort = True
                    self.respond(b'225 ABOR command successful; data channel closed.')

    def do_LIST(self, path):
        try:
            if self.config.vfs.isfile(self.working_dir + path):
                listing = self.config.vfs.listdir(self.working_dir + path)
                if isinstance(listing, list):
                    # RFC 959 recommends the listing to be sorted.
                    listing.sort()
                    iterator = self.config.vfs.format_list(path, listing)
                    _list_data = get_data_from_iter(iterator)
                    self.start_data_channel()
                    self.push_data(_list_data)
                    self.stop_data_channel()
        except (OSError, fs.errors.FSError, FilesystemError, FTPPrivilegeException) as err:
            self._log_err(err)
            self.respond(b'550 LIST command failed.')

    def do_NLST(self, path):
        """Return a list of files in the specified directory in a compact form to the client."""
        try:
            if self.config.vfs.isdir(path):
                listing = self.config.vfs.listdir(self.working_dir + path)
            else:
                # if path is a file we just list its name
                self.config.vfs.stat(path)  # raise exc in case of problems
                listing = [self.working_dir + path]
            data = ''
            if listing:
                listing.sort()
                data = '\r\n'.join(listing) + '\r\n'
            self.push_data(data=data)
        except (OSError, fs.errors.FSError, FilesystemError, FTPPrivilegeException) as err:
            self._log_err(err)
            self.respond(b'550 NLST command failed.')

    def do_RETR(self, arg):
        """
        Fetch and send a file.
        :param arg: Filename that is to be retrieved
        """
        filename = self.working_dir + arg
        if self.config.vfs.isfile(filename):
            self.start_data_channel()
            self.send_file(file_name=filename)
        else:
            self.respond(b'550 The system cannot find the file specified.')

    def do_APPE(self, arg):
        pass

    def do_REIN(self, arg):
        """Reinitialize user's current session."""
        # From RFC-959:
        # REIN command terminates a USER, flushing all I/O and account
        # information, except to allow any transfer in progress to be
        # completed.  All parameters are reset to the default settings
        # and the control connection is left open.  This is identical
        # to the state in which a user finds themselves immediately after
        # the control connection is opened.
        self.stop_data_channel()
        self.username = ''
        # Note: RFC-959 erroneously mention "220" as the correct response
        # code to be given in this case, but this is wrong...
        self.respond(b"230 Ready for new user.")

    def do_STOR(self, file, mode='w'):
        """Store a file (transfer from the client to the server).
        On success return the file path, else None.
        """
        # A resume could occur in case of APPE or REST commands.
        # In that case we have to open file object in different ways:
        # STOR: mode = 'w'
        # APPE: mode = 'a'
        # REST: mode = 'r+' (to permit seeking on file object)
        if 'a' in self._transfer_mode:
            cmd = 'APPE'
        else:
            cmd = 'STOR'
        rest_pos = self._restart_position
        self._restart_position = 0
        if rest_pos:
            mode = 'r+'
        try:
            fd = self.config.vfs.open(file, mode + 'b')
        except fs.errors.FSError as err:
            self.respond(b'550 %a.' % self._log_err(err))
            return

        try:
            if rest_pos:
                # Make sure that the requested offset is valid (within the
                # size of the file being resumed).
                # According to RFC-1123 a 554 reply may result in case
                # that the existing file cannot be repositioned as
                # specified in the REST.
                ok = 0
                try:
                    if rest_pos > self.config.vfs.getsize(file):
                        raise ValueError
                    fd.seek(rest_pos)
                    ok = 1
                except fs.errors.FSError as err:
                    if not ok:
                        fd.close()
                        self.respond(b'554 %a' % self._log_err(err))
                        return

            if self._data_sock is not None:
                self.respond(b'125 Data connection already open. Transfer starting.')
            else:
                self.respond(b'150 File status okay. About to open data connection.')
                self._in_dtp_queue = (fd, cmd)
            return file
        except fs.errors.FSError:
            fd.close()
            raise

    def do_STOU(self, arg):
        pass
    # -----------------------------------------------------------------
    # Depreciated/alias commands
    # RFC-1123 requires that the server treat XCUP, XCWD, XMKD, XPWD and XRMD commands as synonyms for CDUP, CWD, MKD,
    # LIST and RMD. Such commands are obsoleted but some ftp clients (e.g. Windows ftp.exe) still use them.

    # Change to the parent directory. Synonym for CDUP. Deprecated.
    do_XCUP = do_CDUP
    # Change the current working directory. Synonym for CWD. Deprecated.
    do_XCWD = do_CWD
    # Create the specified directory. Synonym for MKD. Deprecated.
    do_XMKD = do_MKD
    # Return the current working directory. Synonym for PWD. Deprecated.
    do_XPWD = do_PWD
    # Remove the specified directory. Synonym for RMD. Deprecated.
    do_XRMD = do_RMD
    # Quit and end the current ftp session. Synonym for QUIT
    do_BYE = do_QUIT