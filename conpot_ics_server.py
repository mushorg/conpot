import logging
import json

import gevent
from gevent.queue import Queue

from lxml import etree

from modules import snmp_command_responder, modbus_server

import config
from modules.loggers import sqlite_log, feeder

logger = logging.getLogger()


def log_worker(log_queue):
    if config.sqlite_enabled:
        sqlite_logger = sqlite_log.SQLiteLogger()
    if config.hpfriends_enabled:
        friends_feeder = feeder.HPFriendsLogger()

    while True:
        event = log_queue.get()
        assert 'data_type' in event
        assert 'timestamp' in event

        if config.hpfriends_enabled:
            friends_feeder.log(json.dumps(event))

        if config.sqlite_enabled:
            sqlite_logger.log(event)


def create_snmp_server(template, log_queue):
    dom = etree.parse(template)
    mibs = dom.xpath('//conpot_template/snmp/mibs/*')
    #only enable snmp server if we have configuration items
    if not mibs:
        snmp_server = None
    else:
        snmp_server = snmp_command_responder.CommandResponder(log_queue)

    for mib in mibs:
        mib_name = mib.attrib['name']
        for symbol in mib:
            symbol_name = symbol.attrib['name']
            value = symbol.xpath('./value/text()')[0]
            snmp_server.register(mib_name, symbol_name, value)
    return snmp_server


if __name__ == "__main__":

    root_logger = logging.getLogger()

    console_log = logging.StreamHandler()
    console_log.setLevel(logging.DEBUG)
    console_log.setFormatter(logging.Formatter('%(asctime)-15s %(message)s'))
    root_logger.addHandler(console_log)

    servers = []

    log_queue = Queue()
    gevent.spawn(log_worker, log_queue)

    logger.setLevel(logging.DEBUG)
    modbus_daemon = modbus_server.ModbusServer('templates/default.xml', log_queue).get_server()
    servers.append(gevent.spawn(modbus_daemon.serve_forever))

    snmp_server = create_snmp_server('templates/default.xml', log_queue)
    if snmp_server:
        logger.info('SNMP server started.')
        servers.append(gevent.spawn(snmp_server.serve_forever))

    gevent.joinall(servers)
