import gevent
from gevent import monkey; gevent.monkey.patch_all()

import unittest
from gevent import socket
import os
import conpot
import conpot.core as conpot_core
from conpot.protocols.ftp.ftp_server import FTPServer
import ftplib
# Use ftplib's client for more authentic testing


def client_send_receive(command, ftp_server):
    """
    Send a command to the ftp server and collect the response.
    :param command: FTP command
    :param ftp_server: conpot.protocols.ftp.ftp_server.FTPServer instance
    :return: response from the server
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', ftp_server.server.server_port))
    _ = s.recv(1024)  # receive the banner
    s.sendall(command)  # send the command
    cmd_rsp = s.recv(1024)
    s.close()
    return cmd_rsp


class TestFTPServer(unittest.TestCase):

    """
        All tests are executed in a similar way. We run a valid/invalid FTP request/command and check for valid
        response.
    """

    def setUp(self):
        # clean up before we start...
        conpot_core.get_sessionManager().purge_sessions()

        # get the current directory
        self.dir_name = os.path.dirname(conpot.__file__)
        self.ftp_server = FTPServer(self.dir_name + '/templates/default/ftp/ftp.xml')
        self.server_greenlet = gevent.spawn(self.ftp_server.start, '127.0.0.1', 0)
        gevent.sleep(1)
        # initialize the databus
        self.databus = conpot_core.get_databus()
        self.databus.initialize(self.dir_name + '/templates/default/template.xml')

    def tearDown(self):
        self.ftp_server.stop()
        gevent.joinall([self.server_greenlet])
        # tidy up (again)...
        conpot_core.get_sessionManager().purge_sessions()

    @unittest.skip
    def test_arg_cmds(self):
        # Test commands requiring an argument.
        expected = b'501 Syntax error: command needs an argument.'
        arg_cmds = ['allo', 'appe', 'dele', 'eprt', 'mdtm', 'mfmt', 'mode', 'mkd', 'opts',
                    'port', 'rest', 'retr', 'rmd', 'rnfr', 'rnto', 'site', 'size', 'stor',
                    'stru', 'type', 'user', 'xmkd', 'xrmd', 'site chmod']
        for cmd in arg_cmds:
            resp = client_send_receive(cmd, ftp_server=self.ftp_server)
            self.assertEqual(resp, expected)

    @unittest.skip
    def test_no_arg_cmds(self):
        # Test commands accepting no arguments.
        expected = b'501 Syntax error: command does not accept arguments.'
        arg_cmds = ['abor', 'cdup', 'feat', 'noop', 'pasv', 'pwd', 'quit',
                    'rein', 'syst', 'xcup', 'xpwd']
        for cmd in arg_cmds:
            resp = client_send_receive(cmd + ' arg', ftp_server=self.ftp_server)
            self.assertEqual(resp, expected)

    @unittest.skip
    def test_auth_cmds(self):
        # Test those commands requiring client to be authenticated.
        pass

    @unittest.skip
    def test_no_auth_cmds(self):
        # Test those commands that do not require client to be authenticated.
        pass


if __name__ == '__main__':
    unittest.main()
