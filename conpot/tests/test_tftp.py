import unittest
import filecmp
import time
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

    def _wait_uploaded(self, data_fs, needle="test-txt", timeout=3.0):
        # Handle runs in a thread-pool executor; context.end() copies to
        # data_fs after the client has already seen the final ACK.
        deadline = time.time() + timeout
        while time.time() < deadline:
            matches = [i for i in data_fs.listdir("./") if needle in i]
            if matches:
                return matches[0]
            time.sleep(0.05)
        self.fail("uploaded TFTP file matching %r not found" % needle)

    def test_tftp_upload(self):
        """Testing TFTP upload files."""
        self.client.upload("test.txt", self._test_file)
        _, _data_fs = conpot_core.get_vfs("tftp")
        _file = self._wait_uploaded(_data_fs)
        self.assertEqual(
            _data_fs.readtext(_file),
            "This is just a test file for Conpot's TFTP server\n",
        )
        _data_fs.remove(_file)

    def test_mkdir_upload(self):
        """Testing TFTP upload files - while recursively making directories as per the TFTP path."""
        self.client.upload("/dir/dir/test.txt", self._test_file)
        _, _data_fs = conpot_core.get_vfs("tftp")
        _file = self._wait_uploaded(_data_fs)
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
