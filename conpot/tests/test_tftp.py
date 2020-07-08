import os
import unittest
import conpot
import gevent
import tftpy
import filecmp
import conpot.core as conpot_core
from freezegun import freeze_time
from conpot.protocols.tftp.tftp_server import TftpServer


class TestTFTPServer(unittest.TestCase):
    def setUp(self):
        # initialize the file system.
        conpot_core.initialize_vfs()
        self._test_file = "/".join(
            conpot.__path__ + ["tests/data/test_data_fs/tftp/test.txt"]
        )
        # get the current directory
        self.dir_name = os.path.dirname(conpot.__file__)
        self.tftp_server = TftpServer(
            self.dir_name + "/templates/default/tftp/tftp.xml",
            self.dir_name + "/templates/default",
            args=None,
        )
        self.server_greenlet = gevent.spawn(self.tftp_server.start, "127.0.0.1", 0)
        gevent.sleep(1)

    def tearDown(self):
        self.tftp_server.stop()

    @freeze_time("2018-07-15 17:51:17")
    def test_tftp_upload(self):
        """Testing TFTP upload files. """
        client = tftpy.TftpClient("127.0.0.1", self.tftp_server.server.server_port)
        client.upload("test.txt", self._test_file)
        gevent.sleep(3)
        _, _data_fs = conpot_core.get_vfs("tftp")
        [_file] = [
            i for i in _data_fs.listdir("./") if "2018-07-15 17:51:17-test-txt" in i
        ]
        self.assertEqual(
            _data_fs.gettext(_file),
            "This is just a test file for Conpot's TFTP server\n",
        )
        _data_fs.remove(_file)

    @freeze_time("2018-07-15 17:51:17")
    def test_mkdir_upload(self):
        """Testing TFTP upload files - while recursively making directories as per the TFTP path."""
        client = tftpy.TftpClient("127.0.0.1", self.tftp_server.server.server_port)
        client.upload("/dir/dir/test.txt", self._test_file)
        gevent.sleep(3)
        _, _data_fs = conpot_core.get_vfs("tftp")
        [_file] = [
            i for i in _data_fs.listdir("./") if "2018-07-15 17:51:17-test-txt" in i
        ]
        self.assertEqual(
            _data_fs.gettext(_file),
            "This is just a test file for Conpot's TFTP server\n",
        )
        _data_fs.remove(_file)

    def test_tftp_download(self):
        _dst_path = "/".join(
            conpot.__path__ + ["tests/data/data_temp_fs/tftp/download"]
        )
        client = tftpy.TftpClient("127.0.0.1", self.tftp_server.server.server_port)
        try:
            client.download("tftp_data.txt", _dst_path)
            gevent.sleep(3)
            self.assertTrue(filecmp.cmp(_dst_path, self._test_file))
        finally:
            _, _data_fs = conpot_core.get_vfs("tftp")
            _data_fs.remove("download")


if __name__ == "__main__":
    unittest.main()
