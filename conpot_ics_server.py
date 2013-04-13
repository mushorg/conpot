import struct
import logging
import json
import uuid
import random
import socket

import gevent
from gevent.server import StreamServer
from gevent.queue import Queue

from lxml import etree

import modbus_tk.modbus_tcp as modbus_tcp
import modbus_tk.defines as mdef
from modbus_tk import modbus
from modules import slave_db, feeder, sqlite_log, snmp_command_responder

import config


FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)


class ModbusServer(modbus.Server):
    def __init__(self, template, databank=None):

        self.log_queue = Queue()
        gevent.spawn(self.log_worker)

        """Constructor: initializes the server settings"""
        modbus.Server.__init__(self, databank if databank else modbus.Databank())

        dom = etree.parse(template)

        #parse slave configuration
        slaves = dom.xpath('//conpot_template/slaves/*')
        template_name = dom.xpath('//conpot_template/@name')[0]
        for s in slaves:
            id = int(s.attrib['id'])
            slave = self.add_slave(id)
            logger.debug('Added slave with id {0}.'.format(id))
            for b in s.xpath('./blocks/*'):
                name = b.attrib['name']
                type = eval('mdef.' + b.xpath('./type/text()')[0])
                start_addr = int(b.xpath('./starting_address/text()')[0])
                size = int(b.xpath('./size/text()')[0])
                slave.add_block(name, type, start_addr, size)
                logger.debug('Added block {0} to slave {1}. (type={2}, start={3}, size={4})'
                .format(name, id, type, start_addr, size))
                for v in b.xpath('./values/*'):
                    addr = int(v.xpath('./address/text()')[0])
                    value = eval(v.xpath('./content/text()')[0])
                    slave.set_values(name, addr, value)
                    logger.debug('Setting value at addr {0} to {1}.'.format(addr, v.xpath('./content/text()')[0]))

        logger.info('Conpot initialized using the {0} template.'.format(template_name))

    def handle(self, socket, address):
        print gevent.getcurrent().__dict__
        session_id = str(uuid.uuid4())
        logger.info('New connection from {0}:{1}. ({2})'.format(address[0], address[1], session_id))

        socket.settimeout(5)
        fileobj = socket.makefile()

        session_data = {'session_id': session_id, 'remote': address, 'data': []}

        try:
            while True:
                request = fileobj.read(7)
                if not request:
                    logger.info('Client disconnected. ({0})'.format(session_id))
                    break
                if request.strip().lower() == 'quit.':
                    logger.info('Client quit. ({0})'.format(session_id))
                    break
                tr_id, pr_id, length = struct.unpack(">HHH", request[:6])
                while len(request) < (length + 6):
                    new_byte = fileobj.read(1)
                    request += new_byte
                query = modbus_tcp.TcpQuery()

                #logdata is a dictionary containing request_pdu, slave_id, function_code and response_pdu
                response, logdata = self._databank.handle_request(query, request)
                session_data['data'].append(logdata)

                logger.debug('Modbus traffic from {0}: {1} ({2})'.format(address[0], logdata, session_id))

                if response:
                    fileobj.write(response)
                    fileobj.flush()
        except socket.timeout:
            logger.debug('Socket timeout, remote: {0}. ({1})'.format(address[0], session_id))

        self.log_queue.put(session_data)

    def log_worker(self):
        if config.sqlite_enabled:
            self.sqlite_logger = sqlite_log.SQLiteLogger()
        if config.hpfriends_enabled:
            self.friends_feeder = feeder.HPFriendsLogger()

        while True:
            event = self.log_queue.get()
            if config.hpfriends_enabled:
                self.friends_feeder.log(json.dumps(event))

            if config.sqlite_enabled:
                for pdu_data in event['data']:
                    self.sqlite_logger.log(dict({'remote': event['remote']}.items() + pdu_data.items()))

def create_snmp_server(template):
    snmp_server = snmp_command_responder.CommandResponder()
    dom = etree.parse(template)
    mibs = dom.xpath('//conpot_template/snmp/mibs/*')
    for mib in mibs:
        mib_name = mib.attrib['name']
        for symbol in mib:
            symbol_name = symbol.attrib['name']
            value = symbol.xpath('./value/text()')[0]
            snmp_server.register(mib_name, symbol_name, value)
    return snmp_server


if __name__ == "__main__":
    servers = []

    logger.setLevel(logging.DEBUG)
    modbus_server = ModbusServer('templates/default.xml', databank=slave_db.SlaveBase())
    connection = (config.host, config.port)
    server = StreamServer(connection, modbus_server.handle)
    logger.info('Modbus server started on: {0}'.format(connection))
    servers.append(gevent.spawn(server.serve_forever))

    snmp_server = create_snmp_server('templates/default.xml')
    logger.info('SNMP server started.')
    servers.append(gevent.spawn(snmp_server.serve_forever))

    gevent.joinall(servers)
