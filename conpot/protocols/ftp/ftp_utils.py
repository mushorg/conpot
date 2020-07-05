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


class FTPException(Exception):
    """General FTP related exceptions. """

    pass


class FTPMaxLoginAttemptsExceeded(FTPException):
    pass


class FTPPrivilegeException(FTPException):
    pass


# all commands:
ftp_commands = {
    "ABOR": dict(
        auth=True, perm=None, arg=False, help="Syntax: ABOR (abort transfer)."
    ),
    "ALLO": dict(
        perm=None,
        auth=True,
        arg=True,
        help="Syntax: ALLO <SP> bytes (noop; allocate storage).",
    ),
    "APPE": dict(
        perm="a",
        auth=True,
        arg=True,
        help="Syntax: APPE <SP> file-name (append data to file).",
    ),
    "CDUP": dict(
        perm="e", auth=True, arg=False, help="Syntax: CDUP (go to parent directory)."
    ),
    "CWD": dict(
        perm="e",
        auth=True,
        arg=None,
        help="Syntax: CWD [<SP> dir-name] (change working directory).",
    ),
    "DELE": dict(
        perm="d", auth=True, arg=True, help="Syntax: DELE <SP> file-name (delete file)."
    ),
    "HELP": dict(
        perm=None, auth=False, arg=None, help="Syntax: HELP [<SP> cmd] (show help)."
    ),
    "LIST": dict(
        perm="l", auth=True, arg=None, help="Syntax: LIST [<SP> path] (list files)."
    ),
    "MDTM": dict(
        perm="l",
        auth=True,
        arg=True,
        help="Syntax: MDTM [<SP> path] (file last modification time).",
    ),
    "MODE": dict(
        perm=None,
        auth=True,
        arg=True,
        help="Syntax: MODE <SP> mode (noop; set data transfer mode).",
    ),
    "MKD": dict(
        perm="m", auth=True, arg=True, help="Syntax: MKD <SP> path (create directory)."
    ),
    "NLST": dict(
        perm="l",
        auth=True,
        arg=None,
        help="Syntax: NLST [<SP> path] (list path in a compact form).",
    ),
    "NOOP": dict(
        perm=None, auth=False, arg=False, help="Syntax: NOOP (just do nothing)."
    ),
    "PASS": dict(
        perm=None,
        auth=False,
        arg=None,
        help="Syntax: PASS [<SP> password] (set user password).",
    ),
    "PASV": dict(
        perm=None,
        auth=True,
        arg=False,
        help="Syntax: PASV (open passive data connection).",
    ),
    "PORT": dict(
        perm=None,
        auth=True,
        arg=True,
        help="Syntax: PORT <sp> h,h,h,h,p,p (open active data connection).",
    ),
    "PWD": dict(
        perm=None,
        auth=True,
        arg=False,
        help="Syntax: PWD (get current working directory).",
    ),
    "QUIT": dict(
        perm=None, auth=False, arg=False, help="Syntax: QUIT (quit current session)."
    ),
    "REIN": dict(perm=None, auth=True, arg=False, help="Syntax: REIN (flush account)."),
    "RETR": dict(
        perm="r",
        auth=True,
        arg=True,
        help="Syntax: RETR <SP> file-name (retrieve a file).",
    ),
    "RMD": dict(
        perm="d",
        auth=True,
        arg=True,
        help="Syntax: RMD <SP> dir-name (remove directory).",
    ),
    "RNFR": dict(
        perm="f",
        auth=True,
        arg=True,
        help="Syntax: RNFR <SP> file-name (rename (source name)).",
    ),
    "REST": dict(
        perm=None,
        auth=True,
        arg=True,
        help="Syntax: REST <SP> offset (set file offset).",
    ),
    "RNTO": dict(
        perm="f",
        auth=True,
        arg=True,
        help="Syntax: RNTO <SP> file-name (rename (destination name)).",
    ),
    "SITE": dict(
        perm=None,
        auth=False,
        arg=True,
        help="Syntax: SITE <SP> site-command (execute SITE command).",
    ),
    "SITE HELP": dict(
        perm=None,
        auth=False,
        arg=None,
        help="Syntax: SITE HELP [<SP> cmd] (show SITE command help).",
    ),
    "SITE CHMOD": dict(
        perm="M",
        auth=True,
        arg=True,
        help="Syntax: SITE CHMOD <SP> mode path (change file mode).",
    ),
    "SIZE": dict(
        perm="l",
        auth=True,
        arg=True,
        help="Syntax: SIZE <SP> file-name (get file size).",
    ),
    "STAT": dict(
        perm="l",
        auth=False,
        arg=None,
        help="Syntax: STAT [<SP> path name] (server stats [list files]).",
    ),
    "STOR": dict(
        perm="w",
        auth=True,
        arg=True,
        help="Syntax: STOR <SP> file-name (store a file).",
    ),
    "STOU": dict(
        perm="w",
        auth=True,
        arg=None,
        help="Syntax: STOU [<SP> name] (store a file with a unique name).",
    ),
    "STRU": dict(
        perm=None,
        auth=True,
        arg=True,
        help="Syntax: STRU <SP> type (noop; set file structure).",
    ),
    "SYST": dict(
        perm=None,
        auth=False,
        arg=False,
        help="Syntax: SYST (get operating system type).",
    ),
    "TYPE": dict(
        perm=None,
        auth=True,
        arg=True,
        help="Syntax: TYPE <SP> [A | I] (set transfer type).",
    ),
    "USER": dict(
        perm=None,
        auth=False,
        arg=True,
        help="Syntax: USER <SP> user-name (set username).",
    ),
    "XCUP": dict(
        perm="e",
        auth=True,
        arg=False,
        help="Syntax: XCUP (obsolete; go to parent directory).",
    ),
    "XCWD": dict(
        perm="e",
        auth=True,
        arg=None,
        help="Syntax: XCWD [<SP> dir-name] (obsolete; change directory).",
    ),
    "XMKD": dict(
        perm="m",
        auth=True,
        arg=True,
        help="Syntax: XMKD <SP> dir-name (obsolete; create directory).",
    ),
    "XPWD": dict(
        perm=None,
        auth=True,
        arg=False,
        help="Syntax: XPWD (obsolete; get current dir).",
    ),
    "XRMD": dict(
        perm="d",
        auth=True,
        arg=True,
        help="Syntax: XRMD <SP> dir-name (obsolete; remove directory).",
    ),
}


def get_data_from_iter(iterator):
    """This utility function generates data from iterators and returns them as string"""
    buffer = ""
    try:
        while True:
            buffer += str(next(iterator))
    except StopIteration:
        return buffer
