import os
import unittest
import conpot
import gevent
import tftpy
import filecmp
import conpot.core as conpot_core
from conpot.protocols.tftp.tftp_server import TftpServer


class TestTFTPServer(unittest.TestCase):
    def setUp(self):
        # initialize the file system.
        conpot_core.initialize_vfs()
        self._test_file = './data/test_data_fs/tftp/test.txt'
        # get the current directory
        self.dir_name = os.path.dirname(conpot.__file__)
        self.tftp_server = TftpServer(self.dir_name + '/templates/default/tftp/tftp.xml',
                                      self.dir_name + '/templates/default', args=None)
        self.server_greenlet = gevent.spawn(self.tftp_server.start, '127.0.0.1', 0)
        gevent.sleep(1)

    def tearDown(self):
        self.tftp_server.stop()
        # close all file systems
        # conpot_core.get_vfs().close(force=True)

    def test_tftp_upload(self):
        client = tftpy.TftpClient('127.0.0.1', self.tftp_server.server.server_port)
        client.upload('test.txt', self._test_file)
        gevent.sleep(3)
        self.assertTrue(True)

    def test_mkdir_upload(self):
        pass

    def test_tftp_download(self):
        client = tftpy.TftpClient('127.0.0.1', self.tftp_server.server.server_port)
        client.download('tftp_data.txt', './data/test_data_fs/test.txt')
        gevent.sleep(3)
        self.assertTrue(filecmp.cmp('./data/test_data_fs/test.txt', self._test_file))


if __name__ == '__main__':
    unittest.main()