# Command Responder (GET/GETNEXT)
# Based on examples from http://pysnmp.sourceforge.net/

import logging

from pysnmp.entity import config
from pysnmp.entity.rfc3413 import cmdrsp, context
from pysnmp.carrier.asynsock.dgram import udp

import gevent
from gevent import socket

from modules.udp_server import DatagramServer
from modules import snmp_engine as engine

import config as conpot_config

logger = logging.getLogger(__name__)

class SNMPDispatcher(DatagramServer):

    def __init__(self):
        self.__timerResolution = 0.5

    def registerRecvCbFun(self, recvCbFun):
        self.recvCbFun = recvCbFun

    def handle(self, msg, address):
        print "in", repr(msg), address
        self.recvCbFun(self, self.transportDomain, address, msg)

    def registerTransport(self, tDomain, transport):
        DatagramServer.__init__(self, transport, self.handle)
        self.transportDomain = tDomain

    def registerTimerCbFun(self, timerCbFun, tickInterval=None):
        pass

    def sendMessage(self, outgoingMessage, transportDomain, transportAddress):
        print "out", repr(outgoingMessage), transportDomain, transportAddress
        self.socket.sendto(outgoingMessage, transportAddress)

    def getTimerResolution(self):
        return self.__timerResolution


class CommandResponder(object):

    def addSocketTransport(self, snmpEngine, transportDomain, transport):
        """Add transport object to socket dispatcher of snmpEngine"""
        if not snmpEngine.transportDispatcher:
            snmpEngine.registerTransportDispatcher(SNMPDispatcher())
        snmpEngine.transportDispatcher.registerTransport(transportDomain, transport)

    def register(self, mibname, symbolname, value):
        s = self._get_mibSymbol(mibname, symbolname)
        logger.info('Registered: {0}'.format(s))
        MibScalarInstance, = self.snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder.importSymbols('SNMPv2-SMI', 'MibScalarInstance')
        scalar = MibScalarInstance(s.name, (0,), s.syntax.clone(value))
        self.snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder.exportSymbols('PYSNMP-EXAMPLE-MIB', scalar)


    def _get_mibSymbol(self, mibname, symbolname):
        modules = self.snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder.mibSymbols
        if mibname in modules:
            if symbolname in modules[mibname]:
                return modules[mibname][symbolname]

    def __init__(self):
        # Create SNMP engine
        self.snmpEngine = engine.SnmpEngine()
        # Transport setup

        udp_sock = gevent.socket.socket(gevent.socket.AF_INET, gevent.socket.SOCK_DGRAM)
        udp_sock.setsockopt(gevent.socket.SOL_SOCKET, gevent.socket.SO_BROADCAST, 1)
        udp_sock.bind((conpot_config.snmp_host, conpot_config.snmp_port))
        # UDP over IPv4
        self.addSocketTransport(
            self.snmpEngine,
            udp.domainName,
            udp_sock
        )

        #TODO: Figure out why v1 is not working
        config.addV1System(self.snmpEngine, 'test-agent', 'public')

        # SNMPv3/USM setup
        # user: usr-md5-des, auth: MD5, priv DES
        config.addV3User(
            self.snmpEngine, 'usr-md5-des',
            config.usmHMACMD5AuthProtocol, 'authkey1',
            config.usmDESPrivProtocol, 'privkey1'
        )
        # user: usr-sha-none, auth: SHA, priv NONE
        config.addV3User(
            self.snmpEngine, 'usr-sha-none',
            config.usmHMACSHAAuthProtocol, 'authkey1'
        )
        # user: usr-sha-aes128, auth: SHA, priv AES/128
        config.addV3User(
            self.snmpEngine, 'usr-sha-aes128',
            config.usmHMACSHAAuthProtocol, 'authkey1',
            config.usmAesCfb128Protocol, 'privkey1'
        )

        # Allow full MIB access for each user at VACM
        config.addVacmUser(self.snmpEngine, 3, 'usr-md5-des', 'authPriv',
                           (1, 3, 6, 1, 2, 1), (1, 3, 6, 1, 2, 1))
        config.addVacmUser(self.snmpEngine, 3, 'usr-sha-none', 'authNoPriv',
                           (1, 3, 6, 1, 2, 1), (1, 3, 6, 1, 2, 1))
        config.addVacmUser(self.snmpEngine, 3, 'usr-sha-aes128', 'authPriv',
                           (1, 3, 6, 1, 2, 1), (1, 3, 6, 1, 2, 1))

        # Get default SNMP context this SNMP engine serves
        snmpContext = context.SnmpContext(self.snmpEngine)

        # Register SNMP Applications at the SNMP engine for particular SNMP context
        cmdrsp.GetCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.SetCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.NextCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.BulkCommandResponder(self.snmpEngine, snmpContext)

    def serve_forever(self):
        self.snmpEngine.transportDispatcher.serve_forever()


if __name__ == "__main__":
    server = CommandResponder()
    print 'Starting echo server on port 161'
    server.serve_forever()