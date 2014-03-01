import struct
import uuid
import socket
import time
import logging
import ast

from datetime import datetime

import modbus_tk.modbus_tcp as modbus_tcp
from modbus_tk import modbus
# Following imports are required for modbus template evaluation
import modbus_tk.defines as mdef
import random

from gevent.server import StreamServer

from lxml import etree
from conpot.protocols.modbus import slave_db

logger = logging.getLogger(__name__)


class ModbusServer(modbus.Server):

    def __init__(self, template, log_queue, timeout=5):

        self.log_queue = log_queue
        self.timeout = timeout
        databank = slave_db.SlaveBase(template)

        # Constructor: initializes the server settings
        modbus.Server.__init__(self, databank if databank else modbus.Databank())

        # not sure how this class remember slave configuration across instance creation, i guess there are some
        # well hidden away class variables somewhere.
        self.remove_all_slaves()

        # move this check to outside this class?
        dom = etree.parse(template)
        modbus_enabled = ast.literal_eval(dom.xpath('//conpot_template/protocols/modbus/@enabled')[0])
        template_name = dom.xpath('//conpot_template/@name')[0]
        self._configure_slaves(dom)

        logger.info('Conpot modbus initialized using the {0} template.'.format(template_name))

    def _configure_slaves(self, dom):
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
                logger.debug('Added block {0} to slave {1}. (type={2}, start={3}, size={4})'
                .format(name, slave_id, request_type, start_addr, size))

    def _add_log_data(self, logdata):
        elapse_ms = int((time.time() - self.start_time) * 1000)
        while elapse_ms in self.session_data["data"]:
            elapse_ms += 1
        elapse_ms = int(time.time() - self.start_time) * 1000
        self.session_data['data'][elapse_ms] = logdata

    def handle(self, sock, address):
        sock.settimeout(self.timeout)
        session_id = str(uuid.uuid4())
        self.session_data = {'session_id': session_id, 'remote': address, 'timestamp': datetime.utcnow(),
                             'data_type': 'modbus', 'data': {}}

        self.start_time = time.time()
        logger.info('New connection from {0}:{1}. ({2})'.format(address[0], address[1], session_id))

        try:
            while True:
                request = sock.recv(7)
                if not request:
                    logger.info('Client disconnected. ({0})'.format(session_id))
                    break
                if request.strip().lower() == 'quit.':
                    logger.info('Client quit. ({0})'.format(session_id))
                    break
                tr_id, pr_id, length = struct.unpack(">HHH", request[:6])
                while len(request) < (length + 6):
                    new_byte = sock.recv(1)
                    request += new_byte
                query = modbus_tcp.TcpQuery()

                # logdata is a dictionary containing request, slave_id, function_code and response
                response, logdata = self._databank.handle_request(query, request)
                logdata['request'] = request.encode('hex')
                self._add_log_data(logdata)

                logger.debug('Modbus traffic from {0}: {1} ({2})'.format(address[0], logdata, session_id))

                if response:
                    sock.sendall(response)
        except socket.timeout:
            logger.debug('Socket timeout, remote: {0}. ({1})'.format(address[0], session_id))

        self.log_queue.put(self.session_data)

    def get_server(self, host, port):
        connection = (host, port)
        server = StreamServer(connection, self.handle)
        logger.info('Modbus server started on: {0}'.format(connection))
        return server