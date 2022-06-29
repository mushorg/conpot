# Command Responder (GET/GETNEXT)
# Based on examples from http://pysnmp.sourceforge.net/

from pysnmp.entity import engine, config
from pysnmp.carrier.asynsock.dgram import udp
from pysnmp.entity.rfc3413 import cmdgen


class SNMPClient(object):
    def __init__(self, host, port):

        # Create SNMP engine instance
        self.snmpEngine = engine.SnmpEngine()

        # user: usr-sha-aes, auth: SHA, priv AES
        config.addV3User(
            self.snmpEngine,
            "usr-sha-aes128",
            config.usmHMACSHAAuthProtocol,
            "authkey1",
            config.usmAesCfb128Protocol,
            "privkey1",
        )
        config.addTargetParams(
            self.snmpEngine, "my-creds", "usr-sha-aes128", "authPriv"
        )

        # Setup transport endpoint and bind it with security settings yielding
        # a target name (choose one entry depending of the transport needed).

        # UDP/IPv4
        config.addSocketTransport(
            self.snmpEngine, udp.domainName, udp.UdpSocketTransport().openClientMode()
        )
        config.addTargetAddr(
            self.snmpEngine, "my-router", udp.domainName, (host, port), "my-creds"
        )

    # Error/response receiver
    def cbFun(
        self,
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
            # Prepare and send a request message
        cmdgen.GetCommandGenerator().sendReq(
            self.snmpEngine,
            "my-router",
            (OID,),
            callback,
        )
        self.snmpEngine.transportDispatcher.runDispatcher()
        # Run I/O dispatcher which would send pending queries and process responses
        self.snmpEngine.transportDispatcher.runDispatcher()

    def set_command(self, OID, callback=None):
        if not callback:
            callback = self.cbFun
        cmdgen.SetCommandGenerator().sendReq(
            self.snmpEngine,
            "my-router",
            (OID,),
            callback,
        )
        self.snmpEngine.transportDispatcher.runDispatcher()

    def walk_command(self, OID, callback=None):
        if not callback:
            callback = self.cbFun
        cmdgen.NextCommandGenerator().sendReq(
            self.snmpEngine,
            "my-router",
            (OID,),
            callback,
        )


if __name__ == "__main__":
    snmp_client = SNMPClient("127.0.0.1", 161)
    OID = ((1, 3, 6, 1, 2, 1, 1, 1, 0), None)
    snmp_client.get_command(OID)
