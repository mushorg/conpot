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

from conpot.core import SessionManager
from conpot.protocols.ftp.ftp_exceptions import FTPMaxLoginAttemptsExceeded

proto_cmds_params = {
    'ABOR': dict(
        perm=None, auth=True, arg=False,
        help='Syntax: ABOR (abort transfer).'),
    'ALLO': dict(
        perm=None, auth=True, arg=True,
        help='Syntax: ALLO <SP> bytes (noop; allocate storage).'),
    'APPE': dict(
        perm='a', auth=True, arg=True,
        help='Syntax: APPE <SP> file-name (append data to file).'),
    'CDUP': dict(
        perm='e', auth=True, arg=False,
        help='Syntax: CDUP (go to parent directory).'),
    'CWD': dict(
        perm='e', auth=True, arg=None,
        help='Syntax: CWD [<SP> dir-name] (change working directory).'),
    'DELE': dict(
        perm='d', auth=True, arg=True,
        help='Syntax: DELE <SP> file-name (delete file).'),
    'EPRT': dict(
        perm=None, auth=True, arg=True,
        help='Syntax: EPRT <SP> |proto|ip|port| (extended active mode).'),
    'EPSV': dict(
        perm=None, auth=True, arg=None,
        help='Syntax: EPSV [<SP> proto/"ALL"] (extended passive mode).'),
    'FEAT': dict(
        perm=None, auth=False, arg=False,
        help='Syntax: FEAT (list all new features supported).'),
    'HELP': dict(
        perm=None, auth=False, arg=None,
        help='Syntax: HELP [<SP> cmd] (show help).'),
    'LIST': dict(
        perm='l', auth=True, arg=None,
        help='Syntax: LIST [<SP> path] (list files).'),
    'MDTM': dict(
        perm='l', auth=True, arg=True,
        help='Syntax: MDTM [<SP> path] (file last modification time).'),
    'MFMT': dict(
        perm='T', auth=True, arg=True,
        help='Syntax: MFMT <SP> timeval <SP> path (file update last '
             'modification time).'),
    'MLSD': dict(
        perm='l', auth=True, arg=None,
        help='Syntax: MLSD [<SP> path] (list directory).'),
    'MLST': dict(
        perm='l', auth=True, arg=None,
        help='Syntax: MLST [<SP> path] (show information about path).'),
    'MODE': dict(
        perm=None, auth=True, arg=True,
        help='Syntax: MODE <SP> mode (noop; set data transfer mode).'),
    'MKD': dict(
        perm='m', auth=True, arg=True,
        help='Syntax: MKD <SP> path (create directory).'),
    'NLST': dict(
        perm='l', auth=True, arg=None,
        help='Syntax: NLST [<SP> path] (list path in a compact form).'),
    'NOOP': dict(
        perm=None, auth=False, arg=False,
        help='Syntax: NOOP (just do nothing).'),
    'OPTS': dict(
        perm=None, auth=True, arg=True,
        help='Syntax: OPTS <SP> cmd [<SP> option] (set option for command).'),
    'PASS': dict(
        perm=None, auth=False, arg=None,
        help='Syntax: PASS [<SP> password] (set user password).'),
    'PASV': dict(
        perm=None, auth=True, arg=False,
        help='Syntax: PASV (open passive data connection).'),
    'PORT': dict(
        perm=None, auth=True, arg=True,
        help='Syntax: PORT <sp> h,h,h,h,p,p (open active data connection).'),
    'PWD': dict(
        perm=None, auth=True, arg=False,
        help='Syntax: PWD (get current working directory).'),
    'QUIT': dict(
        perm=None, auth=False, arg=False,
        help='Syntax: QUIT (quit current session).'),
    'REIN': dict(
        perm=None, auth=True, arg=False,
        help='Syntax: REIN (flush account).'),
    'REST': dict(
        perm=None, auth=True, arg=True,
        help='Syntax: REST <SP> offset (set file offset).'),
    'RETR': dict(
        perm='r', auth=True, arg=True,
        help='Syntax: RETR <SP> file-name (retrieve a file).'),
    'RMD': dict(
        perm='d', auth=True, arg=True,
        help='Syntax: RMD <SP> dir-name (remove directory).'),
    'RNFR': dict(
        perm='f', auth=True, arg=True,
        help='Syntax: RNFR <SP> file-name (rename (source name)).'),
    'RNTO': dict(
        perm='f', auth=True, arg=True,
        help='Syntax: RNTO <SP> file-name (rename (destination name)).'),
    'SITE': dict(
        perm=None, auth=False, arg=True,
        help='Syntax: SITE <SP> site-command (execute SITE command).'),
    'SITE HELP': dict(
        perm=None, auth=False, arg=None,
        help='Syntax: SITE HELP [<SP> cmd] (show SITE command help).'),
    'SITE CHMOD': dict(
        perm='M', auth=True, arg=True,
        help='Syntax: SITE CHMOD <SP> mode path (change file mode).'),
    'SIZE': dict(
        perm='l', auth=True, arg=True,
        help='Syntax: SIZE <SP> file-name (get file size).'),
    'STAT': dict(
        perm='l', auth=False, arg=None,
        help='Syntax: STAT [<SP> path name] (server stats [list files]).'),
    'STOR': dict(
        perm='w', auth=True, arg=True,
        help='Syntax: STOR <SP> file-name (store a file).'),
    'STOU': dict(
        perm='w', auth=True, arg=None,
        help='Syntax: STOU [<SP> name] (store a file with a unique name).'),
    'STRU': dict(
        perm=None, auth=True, arg=True,
        help='Syntax: STRU <SP> type (noop; set file structure).'),
    'SYST': dict(
        perm=None, auth=False, arg=False,
        help='Syntax: SYST (get operating system type).'),
    'TYPE': dict(
        perm=None, auth=True, arg=True,
        help='Syntax: TYPE <SP> [A | I] (set transfer type).'),
    'USER': dict(
        perm=None, auth=False, arg=True,
        help='Syntax: USER <SP> user-name (set username).'),
    'XCUP': dict(
        perm='e', auth=True, arg=False,
        help='Syntax: XCUP (obsolete; go to parent directory).'),
    'XCWD': dict(
        perm='e', auth=True, arg=None,
        help='Syntax: XCWD [<SP> dir-name] (obsolete; change directory).'),
    'XMKD': dict(
        perm='m', auth=True, arg=True,
        help='Syntax: XMKD <SP> dir-name (obsolete; create directory).'),
    'XPWD': dict(
        perm=None, auth=True, arg=False,
        help='Syntax: XPWD (obsolete; get current dir).'),
    'XRMD': dict(
        perm='d', auth=True, arg=True,
        help='Syntax: XRMD <SP> dir-name (obsolete; remove directory).'),
}


class FTPHandler(object):
    """
    Respond to various FTP commands.
    """
    def __init__(self, device_type=None, ftp_home=None, max_login_attempts=3, anon_auth=True, terminator=b'\r\n',
                 session=None):
        # sanity checks
        assert isinstance(device_type, str), device_type
        assert isinstance(ftp_home, str), ftp_home
        assert isinstance(max_login_attempts, int), max_login_attempts
        assert isinstance(anon_auth, bool), anon_auth
        assert isinstance(terminator, bytes), terminator
        assert isinstance(session, SessionManager), session
        self.authenticated = False
        self.device_type = device_type
        self.ftp_home = ftp_home
        self.session = session
        self.working_dir = None
        self.max_login_attempts = max_login_attempts
        self.terminator = terminator
        self.user = None
        self.user_pass = dict()
        # Allow anonymous user/pass
        if anon_auth:
            self.user_pass['anonymous'] = ''
        self.state = None
        self.invalid_login_attempt = 0

    def handle_request(self, request):
        """
        Parse an incoming packet and send it to appropriate ftp method
        :param: (bytes) request - incoming request
        :return: (bytes) response - reply in respect to the request
        """
        try:
            cmd, params = request.split(' ', 1)
        except ValueError:
            cmd = request
            params = None
        else:
            params = params.strip('\r\n')
        cmd = (cmd.strip('\r\n')).upper()
        method = getattr(self, 'ftp_' + params, None)
        if not method:
            # method is invalid.
            return b'500 Unknown Command.' + self.terminator
        if self.invalid_login_attempt < self.max_login_attempts:
            self.state = cmd
            return method(params)
        else:
            raise FTPMaxLoginAttemptsExceeded

    def ftp_USER(self, params):
        """
        USER FTP command. If the user is already logged in, return 530 else 331 for the PASS command
        :param params: username specified by the client/attacker
        """
        # first we need to check if the user is authenticated?
        if self.authenticated:
            return b'530 Cannot switch to another user.' + self.terminator
        else:
            self.user = params
            return b'331 Now specify the Password.' + self.terminator

    def ftp_PASS(self, params):
        if self.state != 'USER':
            return b'503 Log in with USER and PASS first.' + self.terminator
        passwd = params
        if self.user_pass[self.user] == passwd:
            self.authenticated = True
            self.working_dir = '/'
            return b'230 Log in Successful.' + self.terminator
        else:
            self.authenticated = False
            self.invalid_login_attempt += 1
            return b'530 Authentication Failed.' + self.terminator

    def ftp_PORT(self):
        pass

    def ftp_LIST(self):
        pass

    def ftp_CWD(self):
        pass

    def ftp_PWD(self):
        return b'257 "%s"' % self.working_dir + self.terminator

    def ftp_PASV(self):
        pass

    def ftp_RETR(self):
        pass

    def ftp_TYPE(self):
        pass

    def ftp_SYST(self):
        return b'215 %s' % self.device_type + self.terminator

    def ftp_QUIT(self):
        # TODO: disconnect the client
        return b'221 Bye.' + self.terminator