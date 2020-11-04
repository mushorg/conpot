# Command Responder (GET/GETNEXT)
# Based on examples from http://pysnmp.sourceforge.net/

import logging

from pysmi.reader import FileReader, FtpReader
from pysnmp.entity import config
from pysnmp.entity.rfc3413 import context
from pysnmp.carrier.asynsock.dgram import udp
from pysnmp.entity import engine
from pysnmp.smi.compiler import addMibCompiler
import gevent

from conpot.protocols.snmp import conpot_cmdrsp
from conpot.protocols.snmp.databus_mediator import DatabusMediator
from gevent.server import DatagramServer

logger = logging.getLogger(__name__)


class SNMPDispatcher(DatagramServer):
    def __init__(self):
        self.__timerResolution = 0.5

    def registerRecvCbFun(self, recvCbFun, recvId=None):
        self.recvCbFun = recvCbFun

    def handle(self, msg, address):
        try:
            self.recvCbFun(self, self.transportDomain, address, msg)
        except Exception as e:
            logger.info("SNMP Exception: %s", e)

    def registerTransport(self, tDomain, transport):
        DatagramServer.__init__(self, transport, self.handle)
        self.transportDomain = tDomain

    def registerTimerCbFun(self, timerCbFun, tickInterval=None):
        pass

    def sendMessage(self, outgoingMessage, transportDomain, transportAddress):
        self.socket.sendto(outgoingMessage, transportAddress)

    def getTimerResolution(self):
        return self.__timerResolution


class CommandResponder(object):
    def __init__(self, host, port, raw_mibs, compiled_mibs):

        self.oid_mapping = {}
        self.databus_mediator = DatabusMediator(self.oid_mapping)
        # mapping between OID and databus keys

        # Create SNMP engine
        self.snmpEngine = engine.SnmpEngine()

        # Configure SNMP compiler
        mib_builder = self.snmpEngine.getMibBuilder()
        addMibCompiler(mib_builder, destination=compiled_mibs)
        mib_builder.getMibCompiler().addSources(FileReader(raw_mibs))
        mib_builder.getMibCompiler().addSources(
            FtpReader("ftp.cisco.com", "/pub/mibs/v2/@mib@", 80)
        )

        # Transport setup
        udp_sock = gevent.socket.socket(gevent.socket.AF_INET, gevent.socket.SOCK_DGRAM)
        udp_sock.setsockopt(gevent.socket.SOL_SOCKET, gevent.socket.SO_BROADCAST, 1)
        udp_sock.bind((host, port))
        self.server_port = udp_sock.getsockname()[1]
        # UDP over IPv4
        self.addSocketTransport(self.snmpEngine, udp.domainName, udp_sock)

        # SNMPv1
        config.addV1System(self.snmpEngine, "public-read", "public")

        # SNMPv3/USM setup
        # user: usr-md5-des, auth: MD5, priv DES
        config.addV3User(
            self.snmpEngine,
            "usr-md5-des",
            config.usmHMACMD5AuthProtocol,
            "authkey1",
            config.usmDESPrivProtocol,
            "privkey1",
        )
        # user: usr-sha-none, auth: SHA, priv NONE
        config.addV3User(
            self.snmpEngine, "usr-sha-none", config.usmHMACSHAAuthProtocol, "authkey1"
        )
        # user: usr-sha-aes128, auth: SHA, priv AES/128
        config.addV3User(
            self.snmpEngine,
            "usr-sha-aes128",
            config.usmHMACSHAAuthProtocol,
            "authkey1",
            config.usmAesCfb128Protocol,
            "privkey1",
        )

        # Allow full MIB access for each user at VACM
        config.addVacmUser(
            self.snmpEngine,
            1,
            "public-read",
            "noAuthNoPriv",
            readSubTree=(1, 3, 6, 1, 2, 1),
            writeSubTree=(1, 3, 6, 1, 2, 1),
        )
        config.addVacmUser(
            self.snmpEngine,
            2,
            "public-read",
            "noAuthNoPriv",
            readSubTree=(1, 3, 6, 1, 2, 1),
            writeSubTree=(1, 3, 6, 1, 2, 1),
        )
        config.addVacmUser(
            self.snmpEngine,
            3,
            "usr-md5-des",
            "authPriv",
            readSubTree=(1, 3, 6, 1, 2, 1),
            writeSubTree=(1, 3, 6, 1, 2, 1),
        )
        config.addVacmUser(
            self.snmpEngine,
            3,
            "usr-sha-none",
            "authNoPriv",
            readSubTree=(1, 3, 6, 1, 2, 1),
            writeSubTree=(1, 3, 6, 1, 2, 1),
        )
        config.addVacmUser(
            self.snmpEngine,
            3,
            "usr-sha-aes128",
            "authPriv",
            readSubTree=(1, 3, 6, 1, 2, 1),
            writeSubTree=(1, 3, 6, 1, 2, 1),
        )

        # Get default SNMP context this SNMP engine serves
        snmpContext = context.SnmpContext(self.snmpEngine)

        # Register SNMP Applications at the SNMP engine for particular SNMP context
        self.resp_app_get = conpot_cmdrsp.c_GetCommandResponder(
            self.snmpEngine, snmpContext, self.databus_mediator, host, port
        )
        self.resp_app_set = conpot_cmdrsp.c_SetCommandResponder(
            self.snmpEngine, snmpContext, self.databus_mediator, host, port
        )
        self.resp_app_next = conpot_cmdrsp.c_NextCommandResponder(
            self.snmpEngine, snmpContext, self.databus_mediator, host, port
        )
        self.resp_app_bulk = conpot_cmdrsp.c_BulkCommandResponder(
            self.snmpEngine, snmpContext, self.databus_mediator, host, port
        )

    def addSocketTransport(self, snmpEngine, transportDomain, transport):
        """Add transport object to socket dispatcher of snmpEngine"""
        if not snmpEngine.transportDispatcher:
            snmpEngine.registerTransportDispatcher(SNMPDispatcher())
        snmpEngine.transportDispatcher.registerTransport(transportDomain, transport)

    def register(self, mibname, symbolname, instance, value, profile_map_name):
        """Register OID"""
        self.snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder.loadModules(
            mibname
        )
        s = self._get_mibSymbol(mibname, symbolname)

        if s:
            self.oid_mapping[s.name + instance] = profile_map_name

            (
                MibScalarInstance,
            ) = self.snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder.importSymbols(
                "SNMPv2-SMI", "MibScalarInstance"
            )
            x = MibScalarInstance(s.name, instance, s.syntax.clone(value))
            self.snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder.exportSymbols(
                mibname, x
            )

            logger.debug(
                "Registered: OID %s Instance %s ASN.1 (%s @ %s) value %s dynrsp.",
                s.name,
                instance,
                s.label,
                mibname,
                value,
            )

        else:
            logger.warning(
                "Skipped: OID for symbol %s not found in MIB %s", symbolname, mibname
            )

    def _get_mibSymbol(self, mibname, symbolname):
        modules = (
            self.snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder.mibSymbols
        )
        if mibname in modules:
            if symbolname in modules[mibname]:
                return modules[mibname][symbolname]

    def serve_forever(self):
        self.snmpEngine.transportDispatcher.serve_forever()

    def stop(self):
        self.snmpEngine.transportDispatcher.stop()
