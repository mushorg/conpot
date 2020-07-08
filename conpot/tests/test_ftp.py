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

import gevent
from gevent import monkey

gevent.monkey.patch_all()
import unittest
import os
from datetime import datetime
import conpot
from freezegun import freeze_time
from conpot.protocols.ftp.ftp_utils import ftp_commands
import conpot.core as conpot_core
from conpot.helpers import sanitize_file_name
from conpot.protocols.ftp.ftp_server import FTPServer
import ftplib  # Use ftplib's client for more authentic testing


class TestFTPServer(unittest.TestCase):

    """
        All tests are executed in a similar way. We run a valid/invalid FTP request/command and check for valid
        response. Testing is done by sending/receiving files in data channel related commands.
        Implementation Note: There are no explicit tests for active/passive mode. These are covered in list and nlst
        tests
    """

    def setUp(self):
        # Initialize the file system
        conpot_core.initialize_vfs()
        # get the current directory
        self.dir_name = os.path.dirname(conpot.__file__)
        self.ftp_server = FTPServer(
            self.dir_name + "/templates/default/ftp/ftp.xml", None, None
        )
        self.server_greenlet = gevent.spawn(self.ftp_server.start, "127.0.0.1", 0)
        self.client = ftplib.FTP()
        gevent.sleep(1)

    def tearDown(self):
        if self.client:
            try:
                self.client.close()
            except ftplib.all_errors:
                pass
        self.ftp_server.stop()
        self.server_greenlet.kill()

    def refresh_client(self):
        """
        Disconnect and reconnect a client
        """
        if self.client:
            self.client.quit()
            del self.client
        self.client = ftplib.FTP()
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)

    def test_auth(self):
        """Test for user, pass and quit commands."""
        # test with anonymous
        self.assertEqual(
            self.client.connect(
                host="127.0.0.1", port=self.ftp_server.server.server_port
            ),
            "200 FTP server ready.",
        )
        self.assertIn("Technodrome - Mouser Factory.", self.client.login())
        self.refresh_client()
        # test with registered user nobody:nobody
        self.assertIn(
            "Technodrome - Mouser Factory.",
            self.client.login(user="nobody", passwd="nobody"),
        )
        # testing with incorrect password
        # testing with incorrect username
        # try to access a command that requires auth with being authenticated.
        self.assertEqual(self.client.quit(), "221 Bye.")

    def test_help(self):
        # TODO: test help before login and after login.
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        cmds = self.ftp_server.handler.config.enabled_commands
        [cmds.remove(i) for i in ("SITE HELP", "SITE CHMOD") if i in cmds]
        help_text = self.client.sendcmd("help")
        self.assertTrue(all([True if i in help_text else False for i in cmds]))
        # test command specific help
        cmds_help = {ftp_commands[k]["help"] for k in cmds}
        self.assertTrue(
            all(
                [
                    True
                    for i in cmds
                    if self.client.sendcmd("help {}".format(i))
                    and i != "HELP" in cmds_help
                ]
            )
        )
        # test unrecognized command
        self.assertRaisesRegex(
            ftplib.error_perm,
            "501 Unrecognized command.",
            self.client.sendcmd,
            "help ABCD",
        )

    def test_noop(self):
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        self.assertEqual(
            self.client.sendcmd("noop"), "200 I successfully done nothin'."
        )

    def test_stru(self):
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        self.assertEqual(
            self.client.sendcmd("stru F"), "200 File transfer structure set to: F."
        )
        self.assertRaisesRegex(
            ftplib.error_perm,
            "504 Unimplemented STRU type.",
            self.client.sendcmd,
            "stru P",
        )
        self.assertRaisesRegex(
            ftplib.error_perm,
            "504 Unimplemented STRU type.",
            self.client.sendcmd,
            "stru R",
        )
        self.assertRaisesRegex(
            ftplib.error_perm,
            "501 Unrecognized STRU type.",
            self.client.sendcmd,
            "stru invalid_stru_cmd",
        )

    def test_allo(self):
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        self.assertEqual(
            self.client.sendcmd("allo 250"), "202 No storage allocation necessary."
        )

    def test_syst(self):
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        self.assertEqual(self.client.sendcmd("syst"), "215 UNIX Type: L8")

    def test_mode(self):
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        self.assertRaisesRegex(
            ftplib.error_perm,
            "501 Syntax error: command needs an argument",
            self.client.sendcmd,
            "mode",
        )
        self.assertEqual(self.client.sendcmd("mode S"), "200 Transfer mode set to: S")
        self.assertRaisesRegex(
            ftplib.error_perm,
            "504 Unimplemented MODE type.",
            self.client.sendcmd,
            "mode B",
        )

    def test_site(self):
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        self.assertRaisesRegex(
            ftplib.error_perm,
            "501 Syntax error: command needs an argument",
            self.client.sendcmd,
            "site",
        )

    def test_site_help(self):
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        self.assertIn("Help SITE command successful.", self.client.sendcmd("site help"))
        self.assertIn("HELP", self.client.sendcmd("site help"))
        self.assertIn("CHMOD", self.client.sendcmd("site help"))

    def test_type(self):
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        self.assertEqual(self.client.sendcmd("type I"), "200 Type set to: Binary.")
        self.assertEqual(self.client.sendcmd("type L8"), "200 Type set to: Binary.")
        self.assertEqual(self.client.sendcmd("type A"), "200 Type set to: ASCII.")
        self.assertEqual(self.client.sendcmd("type L7"), "200 Type set to: ASCII.")
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, "type 234")

    def test_size(self):
        # TODO: test for a user who does not has permissions for size
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        self.assertRaisesRegex(
            ftplib.error_perm,
            "550 SIZE not allowed in ASCII mode.",
            self.client.sendcmd,
            "size ftp_data.txt",
        )
        # change to mode to binary
        _ = self.client.sendcmd("type I")
        self.assertEqual(self.client.sendcmd("size ftp_data.txt"), "213 49")
        self.assertRaisesRegex(
            ftplib.error_perm,
            "550 is not retrievable.",
            self.client.sendcmd,
            "size file_does_not_exist",
        )

    def test_pwd(self):
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        self.assertEqual(
            self.client.sendcmd("pwd"), '257 "/" is the current directory.'
        )

    def test_mkd(self):
        # TODO: test for a user who does not has permissions to make directory
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        self.assertEqual(
            self.client.sendcmd("mkd testing"), '257 "/testing" directory created.'
        )
        self.assertRaisesRegex(
            ftplib.error_perm,
            "550 'mkd /../../testing/testing' points to a path which is "
            "outside the user's root directory.",
            self.client.sendcmd,
            "mkd /../../testing/testing",
        )
        _ = self.client.sendcmd("mkd testing/testing")
        self.assertEqual(
            self.client.sendcmd("mkd testing/testing/../demo"),
            '257 "/testing/demo" directory created.',
        )
        _vfs, _ = conpot_core.get_vfs("ftp")
        _vfs.removedir("testing/testing")
        _vfs.removedir("testing/demo")
        _vfs.removedir("testing")

    def test_cwd(self):
        #  TODO: test for a user who does not has permissions to change directory
        _vfs, _ = conpot_core.get_vfs("ftp")
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        # create a directory to cwd to.
        _vfs.makedir("testing")
        self.assertEqual(
            self.client.sendcmd("cwd testing"),
            '250 "/testing" is the current directory.',
        )
        # check consistency with pwd
        self.assertEqual(
            self.client.sendcmd("pwd"), '257 "/testing" is the current directory.'
        )
        # test for cdup.
        self.assertEqual(
            self.client.sendcmd("cdup"), '250 "/" is the current directory.'
        )
        # make sure that user does not go - out of the root path.
        self.assertRaisesRegex(
            ftplib.error_perm,
            "550 'cwd ../' points to a path which is outside the user's "
            "root directory.",
            self.client.sendcmd,
            "cwd ../",
        )
        _vfs.removedir("testing")

    def test_rmd(self):
        _vfs, _ = conpot_core.get_vfs("ftp")
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        # let us create a temp dir for deleting
        _vfs.makedir("tmp")
        self.assertEqual(self.client.sendcmd("rmd tmp"), "250 Directory removed.")
        self.assertRaisesRegex(
            ftplib.error_perm,
            "550 Remove directory operation failed.",
            self.client.sendcmd,
            "rmd tmp",
        )
        # TODO: Test with user that has no or little permissions.
        # test for a user trying to delete '/'
        self.assertRaisesRegex(
            ftplib.error_perm,
            "550 Can't remove root directory.",
            self.client.sendcmd,
            "rmd /",
        )
        self.assertRaisesRegex(
            ftplib.error_perm,
            "550 'rmd ../../' points to a path which is outside the user's root directory.",
            self.client.sendcmd,
            "rmd ../../",
        )

    @freeze_time("2018-07-15 17:51:17")
    def test_mdtm(self):
        # TODO : test for user that does not have permissions for mdtm
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        _vfs, _ = conpot_core.get_vfs("ftp")
        _vfs.settimes("ftp_data.txt", accessed=datetime.now(), modified=datetime.now())
        # test for a file that already exists
        self.assertEqual(self.client.sendcmd("mdtm ftp_data.txt"), "213 20180715175117")
        self.assertRaisesRegex(
            ftplib.error_perm,
            "550 /this_file_does_not_exist.txt is not retrievable",
            self.client.sendcmd,
            "mdtm this_file_does_not_exist.txt",
        )

    def test_dele(self):
        # TODO: check for a user who does not have permissions to delete a file!
        _vfs, _ = conpot_core.get_vfs("ftp")
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        # let us create a temp file just for deleting.
        with _vfs.open("/temp_file", mode="w") as _tmp:
            _tmp.write("This is just a temp file for testing rm")
        # delete that file
        self.assertEqual(self.client.sendcmd("dele temp_file"), "250 File removed.")
        # check for errors
        self.assertRaisesRegex(
            ftplib.error_perm,
            "550 Failed to delete file.",
            self.client.sendcmd,
            "dele temp_file",
        )

    def test_file_rename(self):
        # TODO: check for a user who does not have permissions to rename a file!
        _vfs, _ = conpot_core.get_vfs("ftp")
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        # First we would do everything for a valid file and all valid params
        # check with invalid rnfr params
        self.assertRaisesRegex(
            ftplib.error_perm,
            "550 Can't rename home directory.",
            self.client.sendcmd,
            "rnfr /",
        )
        self.assertRaisesRegex(
            ftplib.error_perm,
            "550 No such file or directory.",
            self.client.sendcmd,
            "rnfr file_DNE",
        )
        self.assertRaisesRegex(
            ftplib.error_perm,
            "503 Bad sequence of commands: use RNFR first.",
            self.client.sendcmd,
            "rnto /random_path",
        )
        # create a custom file to play with.
        try:
            # do a rnfr to rename file ftp_data.txt
            with _vfs.open("/test_rename_file.txt", mode="w") as _test:
                _test.write("This is just a test file for rename testing of FTP server")
            self.assertEqual(
                self.client.sendcmd("rnfr test_rename_file.txt"),
                "350 Ready for destination name.",
            )
            self.assertEqual(
                self.client.sendcmd("rnto new_data.txt"), "250 Renaming ok."
            )
            # try for a case that would fail --
            # fixme: tests fail after trying to rename files once they have been renamed.
            # self.assertEqual(self.client.sendcmd('rnfr new_data.txt'), '350 Ready for destination name.')
            # self.assertRaisesRegex(ftplib.error_perm, '501 can\'t decode command.', self.client.sendcmd,
            #                        'rnto Very / Unsafe / file\nname hähä \n\r .txt')
        finally:
            _vfs.remove("new_data.txt")

    def test_site_chmod(self):
        # TODO: check for a user who does not have permissions to do chmod!
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        # change permissions
        self.client.sendcmd("site chmod 644 ftp_data.txt")
        _vfs, _ = conpot_core.get_vfs("ftp")
        self.assertEqual(_vfs.get_permissions("ftp_data.txt"), "rw-r--r--")

    def test_stat(self):
        # TODO: check for a user who does not have permissions to do stat!
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        # do stat without args
        self.assertIn(
            "Logged in as: nobody\n TYPE: ASCII; STRUcture: File; MODE: Stream\n",
            self.client.sendcmd("stat"),
        )
        self.assertIn("ftp_data.txt", self.client.sendcmd("stat /"))

    # ------ Data channel related. -----

    @freeze_time("2018-07-15 17:51:17")
    def test_list(self):
        # TODO: check for a user who does not have permissions to do list!
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        _vfs, _ = conpot_core.get_vfs("ftp")
        _vfs.settimes("ftp_data.txt", accessed=datetime.now(), modified=datetime.now())
        # Do a list of directory for passive mode
        _pasv_list = list()
        self.client.retrlines("LIST", _pasv_list.append)
        # note that this time is set in ftp_server settimes method. Picked up from the default template.
        self.assertEqual(
            ["-rwxrwxrwx   1 nobody   ftp            49 Jul 15 17:51 ftp_data.txt"],
            _pasv_list,
        )
        # check list for active mode
        _actv_list = list()
        self.client.set_pasv(False)
        self.client.retrlines("LIST", _actv_list.append)
        # note that this time is set in ftp_server settimes method. Picked up from the default template.
        self.assertEqual(
            ["-rwxrwxrwx   1 nobody   ftp            49 Jul 15 17:51 ftp_data.txt"],
            _actv_list,
        )
        # response from active and pasv mode should be same.

    def test_nlist(self):
        # TODO: check for a user who does not have permissions to do nlst!
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        # Do a list of directory
        _pasv_list = list()
        self.client.retrlines("NLST", _pasv_list.append)
        self.assertEqual(["ftp_data.txt"], _pasv_list)
        # check list for active mode
        _actv_list = list()
        self.client.set_pasv(False)
        self.client.retrlines("NLST", _actv_list.append)
        self.assertEqual(["ftp_data.txt"], _actv_list)

    def test_retr(self):
        """Test retr or downloading a file from the server."""
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        _path = os.path.join(
            "".join(conpot.__path__), "tests", "data", "data_temp_fs", "ftp"
        )
        with open(_path + "/ftp_testing_retr.txt", mode="wb") as _file:
            self.client.retrbinary("retr ftp_data.txt", _file.write)
        buffer = ""
        with open(_path + "/ftp_testing_retr.txt", mode="r") as _file:
            buffer += _file.readline()
        self.assertEqual(buffer, "This is just a test file for Conpot's FTP server\n")
        os.remove(_path + "/ftp_testing_retr.txt")

    def test_rein(self):
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        self.assertEqual(self.client.sendcmd("rein"), "230 Ready for new user.")
        self.assertRaisesRegex(
            ftplib.error_perm,
            "503 Login with USER first.",
            self.client.sendcmd,
            "pass testing",
        )
        # TODO: Add test with existing transfer in progress.

    @freeze_time("2018-07-15 17:51:17")
    def test_stor(self):
        # let us test by uploading a file called ftp_testing.txt
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        _path = os.path.join(
            "".join(conpot.__path__), "tests", "data", "test_data_fs", "ftp"
        )
        with open(_path + "/ftp_testing.txt", mode="rb") as _file:
            self.client.storbinary("stor ftp_testing_stor.txt", _file)
        self.assertIn(
            "ftp_testing_stor.txt", self.ftp_server.handler.config.vfs.listdir("/")
        )
        _vfs, _data_fs = conpot_core.get_vfs("ftp")
        _vfs.remove("ftp_testing_stor.txt")
        _data_fs_file = sanitize_file_name(
            "ftp_testing_stor.txt",
            self.client.sock.getsockname()[0],
            self.client.sock.getsockname()[1],
        )
        _data_fs.remove(_data_fs_file)

    def test_appe(self):
        _data_1 = "This is just a test!\n"
        _data_2 = "This is another test\n"
        _vfs, _ = conpot_core.get_vfs("ftp")
        with _vfs.open("ftp_appe_test.txt", mode="w") as _file:
            _file.write(_data_1)
        try:
            self.client.connect(
                host="127.0.0.1", port=self.ftp_server.server.server_port
            )
            self.client.login(user="nobody", passwd="nobody")
            _path = os.path.join(
                "".join(conpot.__path__), "tests", "data", "data_temp_fs", "ftp"
            )
            with open(_path + "/ftp_appe.txt", mode="w+") as _file:
                _file.write(_data_2)
            with open(_path + "/ftp_appe.txt", mode="rb+") as _file:
                self.client.storbinary("appe ftp_appe_test.txt", _file)
            _buffer = ""
            with _vfs.open("ftp_appe_test.txt", mode="r") as _file:
                _buffer += _file.read()
            self.assertEqual(_buffer, _data_1 + _data_2)
        finally:
            _vfs.remove("ftp_appe_test.txt")

    def test_abor(self):
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        self.assertEqual(self.client.sendcmd("abor"), "225 No transfer to abort.")

    def test_rest(self):
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        # Let us test error conditions first.
        self.client.sendcmd("type i")
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, "rest")
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, "rest str")
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, "rest -1")
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, "rest 10.1")
        # REST is not supposed to be allowed in ASCII mode
        self.client.sendcmd("type a")
        self.assertRaisesRegex(
            ftplib.error_perm,
            "501 Resuming transfers not allowed in ASCII mode.",
            self.client.sendcmd,
            "rest 10",
        )
        # Fixme: test rest while an actual transfer is going on.

    def test_stou(self):
        # fixme: incomplete test.
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.client.login(user="nobody", passwd="nobody")
        self.client.sendcmd("type i")
        self.client.sendcmd("rest 10")
        self.assertRaisesRegex(
            ftplib.error_temp, "Can't STOU while REST", self.client.sendcmd, "stou"
        )

    def test_max_retries(self):
        """client should raise an error when max retries are reached."""
        self.client.connect(host="127.0.0.1", port=self.ftp_server.server.server_port)
        self.assertRaises(
            ftplib.error_perm, self.client.login, user="nobody", passwd="incorrect_pass"
        )
        self.assertRaises(
            ftplib.error_perm, self.client.login, user="nobody", passwd="incorrect_pass"
        )
        self.assertRaises(
            ftplib.error_perm, self.client.login, user="nobody", passwd="incorrect_pass"
        )
        self.assertRaisesRegex(
            ftplib.error_temp,
            "421 Too many connections. Service temporarily unavailable.",
            self.client.login,
            user="nobody",
            passwd="incorrect_pass",
        )


if __name__ == "__main__":
    unittest.main()
