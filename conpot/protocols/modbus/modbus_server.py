import struct
import socket
import time
import logging

from lxml import etree
from gevent.server import StreamServer

import modbus_tk.modbus_tcp as modbus_tcp
from modbus_tk import modbus
# Following imports are required for modbus template evaluation
import modbus_tk.defines as mdef
import random

from conpot.protocols.modbus import slave_db
import conpot.core as conpot_core

logger = logging.getLogger(__name__)


class ModbusServer(modbus.Server):

    def __init__(self, template, timeout=5):

        self.timeout = timeout
        databank = slave_db.SlaveBase(template)

        # Constructor: initializes the server settings
        modbus.Server.__init__(self, databank if databank else modbus.Databank())

        # not sure how this class remember slave configuration across instance creation, i guess there are some
        # well hidden away class variables somewhere.
        self.remove_all_slaves()
        self._configure_slaves(template)

    def _configure_slaves(self, template):
        dom = etree.parse(template)
        slaves = dom.xpath('//conpot_template/protocols/modbus/slaves/*')
        for s in slaves:
            slave_id = int(s.attrib['id'])
            slave = self.add_slave(slave_id)
            logger.debug('Added slave with id {0}.'.format(slave_id))
            for b in s.xpath('./blocks/*'):
                name = b.attrib['name']
                request_type = eval('mdef.' + b.xpath('./type/text()')[0])
                start_addr = int(b.xpath('./starting_address/text()')[0])
                size = int(b.xpath('./size/text()')[0])
                slave.add_block(name, request_type, start_addr, size)
                logger.debug('Added block {0} to slave {1}. (type={2}, start={3}, size={4})'.format(
                    name, slave_id, request_type, start_addr, size
                ))
        template_name = dom.xpath('//conpot_template/@name')[0]
        logger.info('Conpot modbus initialized using the {0} template.'.format(template_name))

    def handle(self, sock, address):
        sock.settimeout(self.timeout)

        session = conpot_core.get_session('modbus', address[0], address[1])

        self.start_time = time.time()
        logger.info('New connection from {0}:{1}. ({2})'.format(address[0], address[1], session.id))

        try:
            while True:
                request = sock.recv(7)
                if not request:
                    logger.info('Client disconnected. ({0})'.format(session.id))
                    break
                if request.strip().lower() == 'quit.':
                    logger.info('Client quit. ({0})'.format(session.id))
                    break
                tr_id, pr_id, length = struct.unpack(">HHH", request[:6])
                while len(request) < (length + 6):
                    new_byte = sock.recv(1)
                    request += new_byte
                query = modbus_tcp.TcpQuery()

                # logdata is a dictionary containing request, slave_id, function_code and response
                response, logdata = self._databank.handle_request(query, request)
                logdata['request'] = request.encode('hex')
                session.add_event(logdata)

                logger.debug('Modbus traffic from {0}: {1} ({2})'.format(address[0], logdata, session.id))

                if response:
                    sock.sendall(response)
        except socket.timeout:
            logger.debug('Socket timeout, remote: {0}. ({1})'.format(address[0], session.id))

    def get_server(self, host, port):
        connection = (host, port)
        server = StreamServer(connection, self.handle)
        logger.info('Modbus server started on: {0}'.format(connection))
        return server