# Command generator (GET/SET client) for tests — gevent UDP + SNMPv3 (matches server USM users).

import gevent.socket

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import cmdgen

from conpot.protocols.snmp.gevent_transport import GeventClientUdpTransport


class SNMPClient(object):
    def __init__(self, host, port):
        self.snmpEngine = engine.SnmpEngine()

        config.add_v3_user(
            self.snmpEngine,
            "usr-sha-aes128",
            config.USM_AUTH_HMAC96_SHA,
            "authkey1",
            config.USM_PRIV_CFB128_AES,
            "privkey1",
        )
        config.add_target_parameters(
            self.snmpEngine, "my-creds", "usr-sha-aes128", "authPriv"
        )

        udp_sock = gevent.socket.socket(gevent.socket.AF_INET, gevent.socket.SOCK_DGRAM)
        udp_sock.bind(("0.0.0.0", 0))
        config.add_transport(
            self.snmpEngine, udp.SNMP_UDP_DOMAIN, GeventClientUdpTransport(udp_sock)
        )
        config.add_target_address(
            self.snmpEngine,
            "my-router",
            udp.SNMP_UDP_DOMAIN,
            (host, port),
            "my-creds",
        )

    def cbFun(
        self,
        snmpEngine,
        sendRequestHandle,
        errorIndication,
        errorStatus,
        errorIndex,
        varBindTable,
        cbCtx,
    ):
        if errorIndication:
            print(errorIndication)
        elif errorStatus:
            print(
                (
                    "%s at %s"
                    % (
                        errorStatus.prettyPrint(),
                        errorIndex and varBindTable[-1][int(errorIndex) - 1] or "?",
                    )
                )
            )
        else:
            for oid, val in varBindTable:
                print(("%s = %s" % (oid.prettyPrint(), val.prettyPrint())))

    def get_command(self, OID=((1, 3, 6, 1, 2, 1, 1, 1, 0), None), callback=None):
        if not callback:
            callback = self.cbFun
        cmdgen.GetCommandGenerator().send_varbinds(
            self.snmpEngine,
            "my-router",
            None,
            "",
            (OID,),
            callback,
        )
        self.snmpEngine.transport_dispatcher.run_dispatcher()

    def set_command(self, OID, callback=None):
        if not callback:
            callback = self.cbFun
        cmdgen.SetCommandGenerator().send_varbinds(
            self.snmpEngine,
            "my-router",
            None,
            "",
            (OID,),
            callback,
        )
        self.snmpEngine.transport_dispatcher.run_dispatcher()

    def walk_command(self, OID, callback=None):
        if not callback:
            callback = self.cbFun
        cmdgen.NextCommandGenerator().send_varbinds(
            self.snmpEngine,
            "my-router",
            None,
            "",
            (OID,),
            callback,
        )


if __name__ == "__main__":
    snmp_client = SNMPClient("127.0.0.1", 161)
    OID = ((1, 3, 6, 1, 2, 1, 1, 1, 0), None)
    snmp_client.get_command(OID)
