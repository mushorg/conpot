import struct
import logging
import json
import uuid

import xml.etree.ElementTree as ET

from gevent.server import StreamServer

import modbus_tk.modbus_tcp as modbus_tcp
import modbus_tk.defines as mdef
from modbus_tk import modbus
from modules import slave_db, feeder, sqlite_log

import config


FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)


class ModbusServer(modbus.Server):
    def __init__(self, template, databank=None):

        if config.sqlite_enabled:
            self.sqlite_logger = sqlite_log.SQLiteLogger()
        if config.hpfriends_enabled:
            self.friends_feeder = feeder.HPFriendsLogger()
        """Constructor: initializes the server settings"""
        modbus.Server.__init__(self, databank if databank else modbus.Databank())

        #read and parse XML template
        tree = ET.parse(template)
        for xml_slave in tree.getroot():
            slave_id = int(xml_slave.attrib['id'])
            slave = self.add_slave(slave_id)
            logger.debug('Added slave with id {0}.'.format(slave_id))
            for block in xml_slave.iter(tag='block'):
                name = block.attrib['name']
                type_ = eval('mdef.' + block.find('type').text)
                start_addr = int(block.find('starting_address').text)
                size = int(block.find('size').text)
                slave.add_block(name, type_, start_addr, size)
                logger.debug('Added block {0} to slave {1}.'
                             '(type={2}, start={3}, size={4})'.format(name, slave_id, type_, start_addr, size))
                for value in block.iter(tag='value'):
                    addr = int(value.find('address').text)
                    value_ = eval(value.find('content').text)
                    slave.set_values(name, addr, value_)
                    logger.debug('Setting value at addr {0} to {1}.'.format(addr, value.find('content').text))

    def handle(self, socket, address):
        session_id = str(uuid.uuid4())
        logger.info('New connection from {0}:{1}. ({2})'.format(address[0], address[1], session_id))
        fileobj = socket.makefile()

        session_data = {'session_id': session_id, 'remote': address, 'data': []}

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
            response, data = self._databank.handle_request(query, request)
            session_data['data'].append(data)
            #reconstruct the dictionary as the sqlite module expects it
            basic_data = dict({'remote': address}.items() + data.items())

            logger.debug('Modbus traffic: {0}. ({1})'.format(basic_data, session_id))
            if config.sqlite_enabled:
                self.sqlite_logger.insert_queue.put(basic_data)
            if response:
                fileobj.write(response)
                fileobj.flush()

        if config.hpfriends_enabled:
            self.friends_feeder.insert(json.dumps(session_data))


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    modbus_server = ModbusServer('templates/default.xml', databank=slave_db.SlaveBase())
    connection = (config.host, config.port)
    server = StreamServer(connection, modbus_server.handle)
    logger.info("Serving on: {0}".format(connection))
    server.serve_forever()
