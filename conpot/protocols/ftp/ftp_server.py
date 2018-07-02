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

from lxml import etree
import conpot.core as conpot_core
from gevent.server import StreamServer
from conpot.protocols.ftp.ftp_handler import FTPCommandChannel, ftp_commands
from conpot.core.protocol_wrapper import conpot_protocol

logger = logging.getLogger(__name__)


class FTPParseTemplate(object):
    def __init__(self, template):
        dom = etree.parse(template)
        self.device_type = dom.xpath('//ftp/device_info/DeviceType/text()')[0]
        self.working_dir = dom.xpath('//ftp/device_info/Path/text()')[0]
        # The directory would be copied into the Temp VFS.
        self.banner = dom.xpath('//ftp/device_info/Banner/text()')[0]
        self.max_login_attempts = int(dom.xpath('//ftp/device_info/MaxLoginAttempts/text()')[0])
        self.anon_auth = bool(dom.xpath('//ftp/device_info/AnonymousLogin/text()')[0])
        # FTP directory path
        self.ftp_path = dom.xpath('//ftp/path/text()')[0]
        self.enabled_commands = ['USER', 'PASS', 'MKD', 'CWD', 'HELP', 'NOOP', 'PWD', 'QUIT', 'RMD', 'SITE', 'SYST',
                                 'MODE']
        # File System
        self.ftp_fs = conpot_core.create_vfs(protocol_name='ftp', protocol_src_dir='./ftp_data/dir',
                                             data_fs_subdir='ftp')   # Protocol temporary filesystem
        self.data_fs = self.ftp_fs.data_fs  # where the data would be kept for later analysis.
        self.commands = {i: ftp_commands[i] for i in self.enabled_commands}  # Restrict FTP to only enabled FTP commands

        # TODO: Remove this after central auth and vfs are implemented..
        # User/Permissions Model.
        self.user_db = dict()  # |-> user_db[user_name] = (user_pass, user_group)
        self.grp_db = dict()   # |-> grp_db[grp_name] = (grp_permissions, grp_vfs)
        # FIXME: Granting *all* privileges to all user currently
        self.authorizer_has_perm = lambda x, y, z: True
        self.ftp2fs = self.ftp_fs.chdir
        self.fs2ftp = self.ftp_fs.chdir
        # TODO: Delete after integration/testing with central VFS


@conpot_protocol
class FTPServer(object):
    def __init__(self, template, timeout=5):
        self.timeout = timeout
        self.template = template
        self.server = None  # Initialize later
        # Initialize vfs here..
        self.handler = FTPCommandChannel
        self.handler.config = FTPParseTemplate(self.template)
        self._initialize_user_db()

    # TODO: Remove this after integration/testing with central Auth module
    def _initialize_user_db(self):
        self.handler.config.grp_db['ftp'] = ('0777', self.handler.config.ftp_fs)
        self.handler.config.user_db['nobody'] = ('pass', 'ftp')

    def start(self, host, port):
        connection = (host, port)
        # TODO:  pool = Pool(10000) # do not accept more than 10000 connections
        # TODO: StreamServer(('127.0.0.1', 1234), handle, spawn=pool)
        self.server = StreamServer(connection, self.handler.stream_server_handle)
        logger.info('FTP server started on: {}'.format(connection))
        self.server.serve_forever()

    def stop(self):
        logger.debug('Stopping Telnet server')
        self.server.stop()


# ---- For debugging ----
if __name__ == '__main__':
    # Set vars for connection information
    TCP_IP = '127.0.0.1'
    TCP_PORT = 10001
    import os
    conpot_core.init_data_fs('./ftp_data/data')       # Place where all ftp related uploads would be stored
    test_template = os.getcwd() + '/../../templates/default/ftp/ftp.xml'
    server = FTPServer(test_template)
    try:
        server.start(TCP_IP, TCP_PORT)
    except KeyboardInterrupt:
        server.stop()