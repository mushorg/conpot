import unittest
import filecmp
from freezegun import freeze_time
from tftpy import TftpClient

import conpot
import conpot.core as conpot_core
from conpot.protocols.tftp.tftp_server import TftpServer
from conpot.utils.greenlet import spawn_test_server, teardown_test_server


class TestTFTPServer(unittest.TestCase):
    def setUp(self):
        conpot_core.initialize_vfs()

        self.tftp_server, self.greenlet = spawn_test_server(
            TftpServer, template="default", protocol="tftp"
        )

        self.client = TftpClient(
            self.tftp_server.server.server_host, self.tftp_server.server.server_port
        )
        self._test_file = "/".join(
            conpot.__path__ + ["tests/data/test_data_fs/tftp/test.txt"]
        )

    def tearDown(self):
        teardown_test_server(self.tftp_server, self.greenlet)

    @freeze_time("2018-07-15 17:51:17")
    def test_tftp_upload(self):
        """Testing TFTP upload files. """
        self.client.upload("test.txt", self._test_file)
        _, _data_fs = conpot_core.get_vfs("tftp")
        [_file] = [
            i for i in _data_fs.listdir("./") if "2018-07-15 17:51:17-test-txt" in i
        ]
        self.assertEqual(
            _data_fs.readtext(_file),
            "This is just a test file for Conpot's TFTP server\n",
        )
        _data_fs.remove(_file)

    @freeze_time("2018-07-15 17:51:17")
    def test_mkdir_upload(self):
        """Testing TFTP upload files - while recursively making directories as per the TFTP path."""
        self.client.upload("/dir/dir/test.txt", self._test_file)
        _, _data_fs = conpot_core.get_vfs("tftp")
        [_file] = [
            i for i in _data_fs.listdir("./") if "2018-07-15 17:51:17-test-txt" in i
        ]
        self.assertEqual(
            _data_fs.readtext(_file),
            "This is just a test file for Conpot's TFTP server\n",
        )
        _data_fs.remove(_file)

    def test_tftp_download(self):
        _dst_path = "/".join(
            conpot.__path__ + ["tests/data/data_temp_fs/tftp/download"]
        )
        try:
            self.client.download("tftp_data.txt", _dst_path)
            self.assertTrue(filecmp.cmp(_dst_path, self._test_file))
        finally:
            _, _data_fs = conpot_core.get_vfs("tftp")
            _data_fs.remove("download")
