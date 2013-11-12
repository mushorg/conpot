# Copyright (C) 2013  Lukas Rist <glaslos@gmail.com>
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


import unittest
import socket

from gevent.queue import Queue
from conpot.s7comm.s7_server import S7Server

from gevent import monkey

monkey.patch_all()


class TestBase(unittest.TestCase):

    def setUp(self):
        self.log_queue = Queue()
        S7_instance = S7Server('conpot/tests/data/basic_s7_template.xml', self.log_queue)
        self.S7_server = S7_instance.get_server('localhost', 1025)
        print self.S7_server
        self.S7_server.start()
        print 'started'

    def tearDown(self):
        self.S7_server.stop()

    def test_s7(self):
        data = '0300001902f08032010000000000080000f0000001000101e0'.decode('hex')
        print data
        HOST = 'localhost'
        PORT = 1025
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((HOST, PORT))
        s.sendall(data)
        print "done sending"
        data = s.recv(1024)
        s.close()
        print 'Received', repr(data)


if __name__ == '__main__':
    log_queue = Queue()
    S7_instance = S7Server('conpot/tests/data/basic_s7_template.xml', log_queue)
    S7_server = S7_instance.get_server('0.0.0.0', 102)
    S7_server.start()