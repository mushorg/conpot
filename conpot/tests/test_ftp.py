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
from gevent import monkey

monkey.patch_all()
import unittest
import os
from datetime import datetime
from tempfile import NamedTemporaryFile
from freezegun import freeze_time
import conpot
import conpot.core as conpot_core
from conpot.helpers import sanitize_file_name
from conpot.protocols.ftp.ftp_server import FTPServer
from conpot.protocols.ftp.ftp_utils import ftp_commands
from conpot.utils.greenlet import spawn_test_server, teardown_test_server
import ftplib  # Use ftplib's client for more authentic testing


class TestFTPServer(unittest.TestCase):

    """
    All tests are executed in a similar way. We run a valid/invalid FTP request/command and check for valid
    response. Testing is done by sending/receiving files in data channel related commands.
    Implementation Note: There are no explicit tests for active/passive mode. These are covered in list and nlst
    tests
    """

    def setUp(self):
        conpot_core.initialize_vfs()

        self.ftp_server, self.greenlet = spawn_test_server(FTPServer, "default", "ftp")
        self.client = ftplib.FTP()

        self.vfs, self.data_fs = conpot_core.get_vfs("ftp")

    def tearDown(self):
        if self.client:
            try:
                self.client.close()
            except ftplib.all_errors:
                pass

        teardown_test_server(self.ftp_server, self.greenlet)

    def client_connect(self):
        return self.client.connect(
            host=self.ftp_server.server.server_host,
            port=self.ftp_server.server.server_port,
        )

    def client_init(self):
        self.client_connect()
        self.client.login(user="nobody", passwd="nobody")

    def client_refresh(self):
        """
        Disconnect and reconnect a client
        """
        if self.client:
            self.client.quit()
            del self.client
        self.client = ftplib.FTP()
        self.client_connect()

    def test_auth(self):
        """Test for user, pass and quit commands."""
        # test with anonymous
        self.assertEqual(self.client_connect(), "200 FTP server ready.")
        self.assertIn("Technodrome - Mouser Factory.", self.client.login())
        self.client_refresh()
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
        self.client_init()
        cmds = self.ftp_server.handler.config.enabled_commands
        [cmds.remove(i) for i in ("SITE HELP", "SITE CHMOD") if i in cmds]
        help_text = self.client.sendcmd("help")
        self.assertTrue(all([i in help_text for i in cmds]))

        # test command specific help
        for i in cmds:
            response = self.client.sendcmd("help {}".format(i))
            self.assertIn(ftp_commands[i]["help"], response)

        # test unrecognized command
        self.assertRaisesRegex(
            ftplib.error_perm,
            "501 Unrecognized command.",
            self.client.sendcmd,
            "help ABCD",
        )

    def test_noop(self):
        self.client_init()
        self.assertEqual(
            self.client.sendcmd("noop"), "200 I successfully done nothin'."
        )

    def test_stru(self):
        self.client_init()
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
        self.client_init()
        self.assertEqual(
            self.client.sendcmd("allo 250"), "202 No storage allocation necessary."
        )

    def test_syst(self):
        self.client_init()
        self.assertEqual(self.client.sendcmd("syst"), "215 UNIX Type: L8")

    def test_mode(self):
        self.client_init()
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
        self.client_init()
        self.assertRaisesRegex(
            ftplib.error_perm,
            "501 Syntax error: command needs an argument",
            self.client.sendcmd,
            "site",
        )

    def test_site_help(self):
        self.client_init()
        self.assertIn("Help SITE command successful.", self.client.sendcmd("site help"))
        self.assertIn("HELP", self.client.sendcmd("site help"))
        self.assertIn("CHMOD", self.client.sendcmd("site help"))

    def test_type(self):
        self.client_init()
        self.assertEqual(self.client.sendcmd("type I"), "200 Type set to: Binary.")
        self.assertEqual(self.client.sendcmd("type L8"), "200 Type set to: Binary.")
        self.assertEqual(self.client.sendcmd("type A"), "200 Type set to: ASCII.")
        self.assertEqual(self.client.sendcmd("type L7"), "200 Type set to: ASCII.")
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, "type 234")

    def test_size(self):
        # TODO: test for a user who does not has permissions for size
        self.client_init()
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
        self.client_init()
        self.assertEqual(
            self.client.sendcmd("pwd"), '257 "/" is the current directory.'
        )

    def test_mkd(self):
        # TODO: test for a user who does not has permissions to make directory
        self.client_init()
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
        self.vfs.removedir("testing/testing")
        self.vfs.removedir("testing/demo")
        self.vfs.removedir("testing")

    def test_cwd(self):
        #  TODO: test for a user who does not has permissions to change directory
        self.client_init()
        # create a directory to cwd to.
        self.vfs.makedir("testing")
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
        self.vfs.removedir("testing")

    def test_rmd(self):
        self.client_init()
        # let us create a temp dir for deleting
        self.vfs.makedir("tmp")
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
        self.client_init()
        self.vfs.settimes(
            "ftp_data.txt", accessed=datetime.now(), modified=datetime.now()
        )
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
        self.client_init()
        # let us create a temp file just for deleting.
        with self.vfs.open("/temp_file", mode="w") as _tmp:
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
        self.client_init()
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
            with self.vfs.open("/test_rename_file.txt", mode="w") as _test:
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
            self.vfs.remove("new_data.txt")

    def test_site_chmod(self):
        # TODO: check for a user who does not have permissions to do chmod!
        self.client_init()
        # change permissions
        self.client.sendcmd("site chmod 644 ftp_data.txt")
        self.assertEqual(self.vfs.get_permissions("ftp_data.txt"), "rw-r--r--")

    def test_stat(self):
        # TODO: check for a user who does not have permissions to do stat!
        self.client_init()
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
        self.client_init()
        self.vfs.settimes(
            "ftp_data.txt", accessed=datetime.now(), modified=datetime.now()
        )
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
        self.client_init()
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
        self.client_init()
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
        self.client_init()
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
        self.client_init()
        _path = os.path.join(
            "".join(conpot.__path__), "tests", "data", "test_data_fs", "ftp"
        )
        with open(_path + "/ftp_testing.txt", mode="rb") as _file:
            self.client.storbinary("stor ftp_testing_stor.txt", _file)
        self.assertIn(
            "ftp_testing_stor.txt", self.ftp_server.handler.config.vfs.listdir("/")
        )
        self.vfs.remove("ftp_testing_stor.txt")
        _data_fs_file = sanitize_file_name(
            "ftp_testing_stor.txt",
            self.client.sock.getsockname()[0],
            self.client.sock.getsockname()[1],
        )
        self.data_fs.remove(_data_fs_file)

    def test_appe(self):
        self.client_init()
        _data_1 = "This is just a test!\n"
        _data_2 = "This is another test\n"
        _file_name = "ftp_appe_test.txt"

        with self.vfs.open(_file_name, mode="w") as _server_file:
            _server_file.write(_data_1)

        try:
            with NamedTemporaryFile(mode="w+") as _temp:
                _temp.write(_data_2)
                _temp.flush()

                with open(_temp.name, mode="rb+") as _source:
                    self.client.storbinary(f"appe {_file_name}", _source)

            with self.vfs.open(_file_name, mode="r") as _server_file:
                _file_contents = _server_file.read()

            self.assertEqual(_file_contents, _data_1 + _data_2)
        finally:
            self.vfs.remove(_file_name)
            _data_fs_file = sanitize_file_name(
                _file_name,
                self.client.sock.getsockname()[0],
                self.client.sock.getsockname()[1],
            )
            self.data_fs.remove(_data_fs_file)

    def test_abor(self):
        self.client_init()
        self.assertEqual(self.client.sendcmd("abor"), "225 No transfer to abort.")

    def test_rest(self):
        self.client_init()
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
        self.client_init()
        self.client.sendcmd("type i")
        self.client.sendcmd("rest 10")
        self.assertRaisesRegex(
            ftplib.error_temp, "Can't STOU while REST", self.client.sendcmd, "stou"
        )

    def test_max_retries(self):
        """client should raise an error when max retries are reached."""
        self.client_connect()
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
