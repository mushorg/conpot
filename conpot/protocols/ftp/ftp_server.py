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

import asyncio
import logging

from os import R_OK, W_OK
from datetime import datetime

from conpot.protocols.ftp.ftp_utils import ftp_commands, FTPException
from conpot.protocols.ftp.ftp_handler import FTPCommandChannel
from conpot.core.protocol_wrapper import conpot_protocol
from conpot.utils.asyncio_serve import serve_tcp_sync_handler
import conpot.core as conpot_core

logger = logging.getLogger(__name__)


class FTPConfig(object):
    def __init__(self, template):
        self.user_db = dict()  # user_db[uid] = (user_pass, user_group)
        self.grp_db = (
            dict()
        )  # grp_db[gid] = {group: 'group_name'. users: set(users_uid))
        device_info = template["device_info"]
        # First let us get FTP related data
        self.all_commands = [
            "USER",
            "PASS",
            "HELP",
            "NOOP",
            "QUIT",
            "SITE HELP",
            "SITE",
            "SYST",
            "TYPE",
            "PASV",
            "PORT",
            "ALLO",
            "MODE",
            "SIZE",
            "PWD",
            "MKD",
            "RMD",
            "CWD",
            "CDUP",
            "MDTM",
            "DELE",
            "SITE CHMOD",
            "RNFR",
            "RNTO",
            "STAT",
            "LIST",
            "NLST",
            "RETR",
            "REIN",
            "ABOR",
            "STOR",
            "APPE",
            "REST",
            "STRU",
            "STOU",
        ]
        # Implementation Note: removing a command from here would make it unrecognizable in FTP server.
        raw_commands = device_info["enabled_commands"]
        if isinstance(raw_commands, list):
            self.enabled_commands = [
                str(i).replace("'", "").strip() for i in raw_commands
            ]
        else:
            self.enabled_commands = ("".join(str(raw_commands).strip().split())).split(
                ","
            )
            self.enabled_commands = [
                i.replace("'", "").strip() for i in self.enabled_commands if i
            ]
        if "SITEHELP" in self.enabled_commands:
            self.enabled_commands.remove("SITEHELP")
            self.enabled_commands.append("SITE HELP")
        if "SITECHMOD" in self.enabled_commands:
            self.enabled_commands.remove("SITECHMOD")
            self.enabled_commands.append("SITE CHMOD")
        for i in self.enabled_commands:
            assert i in self.all_commands, "Unknown FTP command: %r" % i
        self.device_type = device_info["device_type"]
        self.banner = device_info["banner"]
        self.max_login_attempts = int(device_info["max_login_attempts"])
        # set the connection timeout to 300 secs.
        self.timeout = int(device_info["sever_timeout"])
        self.motd = device_info.get("motd")
        self.stou_prefix = device_info.get("stou_prefix") or ""
        self.stou_suffix = device_info.get("stou_suffix") or ""
        # Restrict FTP to only enabled FTP commands
        self.COMMANDS = {i: ftp_commands[i] for i in self.enabled_commands}

        # -- Now that we fetched FTP meta, let us populate users.
        ftp_users = template["ftp_users"]
        grp = ftp_users["group"]
        for i in ftp_users.get("users", []):
            self.user_db[int(i["uid"])] = {
                "uname": i["uname"],
                "grp": grp,
                "password": i["password"],
            }
        self.anon_auth = bool(ftp_users.get("anon_enabled", False))
        if self.anon_auth:
            self.anon_uid = int(ftp_users["anon_uid"])
            self.user_db[self.anon_uid] = {
                "uname": ftp_users["anon_uname"],
                "grp": grp,
                "password": "",
            }

        # As a last step, get VFS related data.
        vfs = template["ftp_vfs"]
        self.root_path = vfs["path"]
        self.data_fs_subdir = vfs["data_fs_subdir"]
        if not vfs.get("add_src"):
            self.add_src = None
        else:
            self.add_src = str(vfs["add_src"]).lower()
        # default ftp owners and groups
        self.default_owner = int(vfs["default_owner"])
        self.default_group = int(grp.split(":")[0])

        self.default_perms = oct(int(str(vfs["default_perms"]), 8))
        self.file_default_perms = oct(int(str(vfs["upload_file_perms"]), 8))
        self.dir_default_perms = oct(int(str(vfs["upload_file_perms"]), 8))
        self._custom_files = vfs.get("files", [])
        self._custom_dirs = vfs.get("dirs", [])
        self._init_user_db()  # Initialize User DB
        self._init_fs()  # Initialize FTP file system.

    def _init_fs(self):
        # Create/register all necessary users and groups in the file system
        _ = {
            conpot_core.get_vfs().register_user(uid=k, name=v["uname"])
            for k, v in self.user_db.items()
        }
        _ = {
            conpot_core.get_vfs().create_group(gid=k, name=v["group"])
            for k, v in self.grp_db.items()
        }
        _ = {
            conpot_core.get_vfs().add_users_to_group(gid=k, uids=list(v["users"]))
            for k, v in self.grp_db.items()
        }
        # Initialize file system
        self.vfs, self.data_fs = conpot_core.add_protocol(
            protocol_name="ftp",
            data_fs_subdir=self.data_fs_subdir,
            vfs_dst_path=self.root_path,
            src_path=self.add_src,
            owner_uid=self.default_owner,
            group_gid=self.default_group,
            perms=self.default_perms,
        )
        if self.add_src:
            logger.info(
                "FTP Serving File System from {} at {} in vfs. FTP data_fs sub directory: {}".format(
                    self.add_src, self.root_path, self.data_fs._sub_dir
                )
            )
        else:
            logger.info(
                "FTP Serving File System at {} in vfs. FTP data_fs sub directory: {}".format(
                    self.root_path, self.data_fs._sub_dir
                )
            )
        logger.debug(
            "FTP serving list of files : {}".format(", ".join(self.vfs.listdir(".")))
        )
        self.root = "/"  # Setup root dir.
        # check for permissions etc.
        logger.debug("FTP root {} is a directory".format(self.vfs.getcwd() + self.root))
        if self.vfs.access(self.root, 0, R_OK):
            logger.debug(
                "FTP root {} is readable".format(self.vfs.getcwd() + self.root)
            )
        else:
            raise FTPException("FTP root must be readable")
        if self.vfs.access(self.root, 0, W_OK):
            logger.debug(
                "FTP root {} is writable".format(self.vfs.getcwd() + self.root)
            )
        else:
            logger.warning(
                "FTP root {} is not writable".format(self.vfs.getcwd() + self.root)
            )
        # Finally apply permissions to specific files.
        for _file in self._custom_files:
            _path = _file["path"]
            _path = _path.replace(self.root_path, self.root)
            _owner = int(_file["owner_uid"])
            _perms = oct(int(str(_file["perms"]), 8))
            _accessed = datetime.fromtimestamp(float(_file["last_accessed"]))
            _modified = datetime.fromtimestamp(float(_file["last_modified"]))
            self.vfs.chown(_path, _owner, self.default_group)
            self.vfs.chmod(_path, _perms)
            _fs = self.vfs.delegate_fs().delegate_fs()
            _fs.settimes(self.vfs.delegate_path(_path)[1], _accessed, _modified)

        for _dir in self._custom_dirs:
            _path = _dir["path"]
            _recursive = bool(_dir.get("recursive", False))
            _path = _path.replace(self.root_path, self.root)
            _owner = int(_dir["owner_uid"])
            _perms = oct(int(str(_dir["perms"]), 8))
            _accessed = datetime.fromtimestamp(float(_dir["last_accessed"]))
            _modified = datetime.fromtimestamp(float(_dir["last_modified"]))
            self.vfs.chown(_path, _owner, self.default_group, _recursive)
            self.vfs.chmod(_path, _perms)
            _fs = self.vfs.delegate_fs().delegate_fs()
            _fs.settimes(self.vfs.delegate_path(_path)[1], _accessed, _modified)
        # self.default_owner = 13
        # self.default_group = 45
        # self.vfs.chmod('/', self.default_perms, recursive=True)
        # self.vfs.chown('/', uid=self.default_owner, gid=self.default_group, recursive=True)

    # --------------------------------------------
    # TODO: move this method to auth module.
    def _init_user_db(self):
        """
        We expect the following dict format to build for every user
                self.user_db[10] = {
                    'uname': 'test_user',
                    'grp': '45:ftp',
                    'password': 'test'
                }
        :return:
        """
        # TODO: Get users from the template.
        self.user_db[13] = {"uname": "nobody", "grp": "45:ftp", "password": "nobody"}
        # Toggle enable/disable anonymous user.
        self.user_db[22] = {"uname": "anonymous", "grp": "45:ftp", "password": ""}
        # Let us create groups from the populated users.
        for i in self.user_db.keys():
            grp = self.user_db[i].pop("grp")
            _gid, _gname = grp.split(":")
            _gid = int(_gid)
            if _gid not in self.grp_db.keys():
                # It is a new group. Let us create/register this.
                self.grp_db[_gid] = {"group": _gname, "users": set()}
            self.grp_db[_gid]["users"].add(i)
        # create a simple set of user and pass combinations for easy auth
        self.user_pass = set(
            zip(
                [v["uname"] for v in self.user_db.values()],
                [v["password"] for v in self.user_db.values()],
            )
        )

    # TODO: move this method to auth module.
    def get_uid(self, user_name):
        """Get uid from a username"""
        [_uid] = [k for k, v in self.user_db.items() if user_name in v.values()]
        return _uid

    # TODO: move this method to auth module.
    def get_gid(self, uid):
        """Get group id of a user from it's uid"""
        [_gid] = [k for k, v in self.grp_db.items() if uid in v["users"]]
        return _gid


@conpot_protocol
class FTPServer(object):
    def __init__(self, template, template_directory, args):
        self.template = template
        self.server = None  # Initialize later
        # Initialize vfs here..
        self.handler = FTPCommandChannel
        self.handler.config = FTPConfig(self.template)

    def handle(self, sock, address):
        self.handler.stream_server_handle(sock, address)

    async def start(self, host, port):
        self.host = host
        self.port = port
        self.handler.host, self.handler.port = host, port
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        connection = (self.handler.host, self.handler.port)
        logger.info("FTP server started on: {}".format(connection))
        await serve_tcp_sync_handler(
            host,
            port,
            self,
            stop_event=self._stop,
            ready_event=self._ready,
            name="FTPServer",
        )

    def stop(self):
        logger.debug("Stopping FTP server")
        if hasattr(self, "_stop"):
            self._stop.set()
