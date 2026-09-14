# Command Responder (GET/GETNEXT)
# Based on examples from http://pysnmp.sourceforge.net/

import logging

from pysmi.reader import FileReader, HttpReader
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import context
from pysnmp.smi.compiler import add_mib_compiler
import gevent

from conpot.protocols.snmp import conpot_cmdrsp
from conpot.protocols.snmp.databus_mediator import DatabusMediator
from conpot.protocols.snmp.gevent_transport import GeventUdpTransport

logger = logging.getLogger(__name__)


class CommandResponder(object):
    def __init__(self, host, port, raw_mibs, compiled_mibs):
        self.oid_mapping = {}
        self.databus_mediator = DatabusMediator(self.oid_mapping)
        # mapping between OID and databus keys

        # Create SNMP engine
        self.snmpEngine = engine.SnmpEngine()

        # Configure SNMP compiler
        mib_builder = self.snmpEngine.get_mib_builder()
        add_mib_compiler(mib_builder, destination=compiled_mibs)
        compiler = mib_builder.get_mib_compiler()
        compiler.add_sources(FileReader(raw_mibs))
        # Standard MIB ASN.1 (SNMPv2-SMI, …) for compiling custom MIBs
        compiler.add_sources(HttpReader("https://mibs.pysnmp.com/asn1/@mib@"))

        # Transport setup
        udp_sock = gevent.socket.socket(gevent.socket.AF_INET, gevent.socket.SOCK_DGRAM)
        udp_sock.setsockopt(gevent.socket.SOL_SOCKET, gevent.socket.SO_BROADCAST, 1)
        udp_sock.bind((host, port))
        self.server_port = udp_sock.getsockname()[1]
        config.add_transport(
            self.snmpEngine, udp.SNMP_UDP_DOMAIN, GeventUdpTransport(udp_sock)
        )

        # SNMPv1
        config.add_v1_system(self.snmpEngine, "public-read", "public")

        # SNMPv3/USM setup
        # user: usr-md5-des, auth: MD5, priv DES
        config.add_v3_user(
            self.snmpEngine,
            "usr-md5-des",
            config.USM_AUTH_HMAC96_MD5,
            "authkey1",
            config.USM_PRIV_CBC56_DES,
            "privkey1",
        )
        # user: usr-sha-none, auth: SHA, priv NONE
        config.add_v3_user(
            self.snmpEngine,
            "usr-sha-none",
            config.USM_AUTH_HMAC96_SHA,
            "authkey1",
        )
        # user: usr-sha-aes128, auth: SHA, priv AES/128
        config.add_v3_user(
            self.snmpEngine,
            "usr-sha-aes128",
            config.USM_AUTH_HMAC96_SHA,
            "authkey1",
            config.USM_PRIV_CFB128_AES,
            "privkey1",
        )

        # Allow full MIB access for each user at VACM
        config.add_vacm_user(
            self.snmpEngine,
            1,
            "public-read",
            "noAuthNoPriv",
            readSubTree=(1, 3, 6, 1, 2, 1),
            writeSubTree=(1, 3, 6, 1, 2, 1),
        )
        config.add_vacm_user(
            self.snmpEngine,
            2,
            "public-read",
            "noAuthNoPriv",
            readSubTree=(1, 3, 6, 1, 2, 1),
            writeSubTree=(1, 3, 6, 1, 2, 1),
        )
        config.add_vacm_user(
            self.snmpEngine,
            3,
            "usr-md5-des",
            "authPriv",
            readSubTree=(1, 3, 6, 1, 2, 1),
            writeSubTree=(1, 3, 6, 1, 2, 1),
        )
        config.add_vacm_user(
            self.snmpEngine,
            3,
            "usr-sha-none",
            "authNoPriv",
            readSubTree=(1, 3, 6, 1, 2, 1),
            writeSubTree=(1, 3, 6, 1, 2, 1),
        )
        config.add_vacm_user(
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

    def register(self, mibname, symbolname, instance, value, profile_map_name):
        """Register OID"""
        mib = self.snmpEngine.get_mib_builder()
        mib.load_modules(mibname)
        s = self._get_mibSymbol(mibname, symbolname)

        if s:
            self.oid_mapping[s.name + instance] = profile_map_name

            (MibScalarInstance,) = mib.import_symbols("SNMPv2-SMI", "MibScalarInstance")
            x = MibScalarInstance(s.name, instance, s.syntax.clone(value))
            mib.export_symbols(mibname, x)

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
        modules = self.snmpEngine.get_mib_builder().mibSymbols
        if mibname in modules:
            if symbolname in modules[mibname]:
                return modules[mibname][symbolname]

    def serve_forever(self):
        self.snmpEngine.transport_dispatcher.run_dispatcher()

    def stop(self):
        self.snmpEngine.transport_dispatcher.stop()
