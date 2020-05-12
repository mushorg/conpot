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

from os import R_OK, W_OK
from lxml import etree
import conpot.core as conpot_core
from gevent.server import StreamServer
from conpot.protocols.ftp.ftp_utils import ftp_commands, FTPException
from conpot.protocols.ftp.ftp_handler import FTPCommandChannel
from conpot.core.protocol_wrapper import conpot_protocol
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FTPConfig(object):
    def __init__(self, template):
        self.user_db = dict()  # user_db[uid] = (user_pass, user_group)
        self.grp_db = (
            dict()
        )  # grp_db[gid] = {group: 'group_name'. users: set(users_uid))
        dom = etree.parse(template)
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
        self.enabled_commands = (
            "".join(
                dom.xpath("//ftp/device_info/enabled_commands/text()")[0]
                .strip()
                .split()
            )
        ).split(",")
        self.enabled_commands = [i.replace("'", "") for i in self.enabled_commands]
        if "SITEHELP" in self.enabled_commands:
            self.enabled_commands.remove("SITEHELP")
            self.enabled_commands.append("SITE HELP")
        if "SITECHMOD" in self.enabled_commands:
            self.enabled_commands.remove("SITECHMOD")
            self.enabled_commands.append("SITE CHMOD")
        for i in self.enabled_commands:
            assert i in self.all_commands
        self.device_type = dom.xpath("//ftp/device_info/device_type/text()")[0]
        self.banner = dom.xpath("//ftp/device_info/banner/text()")[0]
        self.max_login_attempts = int(
            dom.xpath("//ftp/device_info/max_login_attempts/text()")[0]
        )
        # set the connection timeout to 300 secs.
        self.timeout = int(dom.xpath("//ftp/device_info/sever_timeout/text()")[0])
        if dom.xpath("//ftp/device_info/motd/text()"):
            self.motd = dom.xpath("//ftp/device_info/motd/text()")[0]
        else:
            self.motd = None
        self.stou_prefix = dom.xpath("//ftp/device_info/stou_prefix/text()")
        self.stou_suffix = dom.xpath("//ftp/device_info/stou_suffix/text()")
        # Restrict FTP to only enabled FTP commands
        self.COMMANDS = {i: ftp_commands[i] for i in self.enabled_commands}

        # -- Now that we fetched FTP meta, let us populate users.
        grp = dom.xpath("//ftp/ftp_users/users")[0].attrib["group"]
        for i in dom.xpath("//ftp/ftp_users/users/*"):
            self.user_db[int(i.attrib["uid"])] = {
                "uname": i.xpath("./uname/text()")[0],
                "grp": grp,
                "password": i.xpath("./password/text()")[0],
            }
        self.anon_auth = bool(
            dom.xpath("//ftp/ftp_users/anon_login")[0].attrib["enabled"]
        )
        if self.anon_auth:
            self.anon_uid = int(
                dom.xpath("//ftp/ftp_users/anon_login")[0].attrib["uid"]
            )
            self.user_db[self.anon_uid] = {
                "uname": dom.xpath("//ftp/ftp_users/anon_login/uname/text()")[0],
                "grp": grp,
                "password": "",
            }

        # As a last step, get VFS related data.
        self.root_path = dom.xpath("//ftp/ftp_vfs/path/text()")[0]
        self.data_fs_subdir = dom.xpath("//ftp/ftp_vfs/data_fs_subdir/text()")[0]
        if len(dom.xpath("//ftp/ftp_vfs/add_src/text()")) == 0:
            self.add_src = None
        else:
            self.add_src = dom.xpath("//ftp/ftp_vfs/add_src/text()")[0].lower()
        # default ftp owners and groups
        self.default_owner = int(dom.xpath("//ftp/ftp_vfs/default_owner/text()")[0])
        self.default_group = int(grp.split(":")[0])

        self.default_perms = oct(
            int(dom.xpath("//ftp/ftp_vfs/default_perms/text()")[0], 8)
        )
        self.file_default_perms = oct(
            int(dom.xpath("//ftp/ftp_vfs/upload_file_perms/text()")[0], 8)
        )
        self.dir_default_perms = oct(
            int(dom.xpath("//ftp/ftp_vfs/upload_file_perms/text()")[0], 8)
        )
        self._custom_files = dom.xpath("//ftp/ftp_vfs/file")
        self._custom_dirs = dom.xpath("//ftp/ftp_vfs/dir")
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
            _path = _file.attrib["path"]
            _path = _path.replace(self.root_path, self.root)
            _owner = int(_file.xpath("./owner_uid/text()")[0])
            _perms = oct(int(_file.xpath("./perms/text()")[0], 8))
            _accessed = datetime.fromtimestamp(
                float(_file.xpath("./last_accessed/text()")[0])
            )
            _modified = datetime.fromtimestamp(
                float(_file.xpath("./last_modified/text()")[0])
            )
            self.vfs.chown(_path, _owner, self.default_group)
            self.vfs.chmod(_path, _perms)
            _fs = self.vfs.delegate_fs().delegate_fs()
            _fs.settimes(self.vfs.delegate_path(_path)[1], _accessed, _modified)

        for _dir in self._custom_dirs:
            _path = _dir.attrib["path"]
            _recursive = bool(_dir.attrib["recursive"])
            _path = _path.replace(self.root_path, self.root)
            _owner = int(_dir.xpath("./owner_uid/text()")[0])
            _perms = oct(int(_dir.xpath("./perms/text()")[0], 8))
            _accessed = datetime.fromtimestamp(
                float(_dir.xpath("./last_accessed/text()")[0])
            )
            _modified = datetime.fromtimestamp(
                float(_dir.xpath("./last_modified/text()")[0])
            )
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

    def start(self, host, port):
        self.handler.host, self.handler.port = host, port
        connection = (self.handler.host, self.handler.port)
        self.server = StreamServer(connection, self.handler.stream_server_handle)
        logger.info("FTP server started on: {}".format(connection))
        self.server.serve_forever()

    def stop(self):
        logger.debug("Stopping FTP server")
        self.server.stop()
        del self.handler
