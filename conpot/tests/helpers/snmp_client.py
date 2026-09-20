# Command generator (GET/SET client) for tests — stdlib UDP + PySNMP asyncio transport.

import asyncio
import socket

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import cmdgen


class SNMPClient(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def _setup_engine(self, loop):
        snmpEngine = engine.SnmpEngine()

        config.add_v3_user(
            snmpEngine,
            "usr-sha-aes128",
            config.USM_AUTH_HMAC96_SHA,
            "authkey1",
            config.USM_PRIV_CFB128_AES,
            "privkey1",
        )
        config.add_target_parameters(
            snmpEngine, "my-creds", "usr-sha-aes128", "authPriv"
        )

        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.bind(("0.0.0.0", 0))
        udp_sock.setblocking(False)
        transport = udp.UdpTransport(loop=loop)
        transport.open_server_mode(sock=udp_sock)
        config.add_transport(snmpEngine, udp.SNMP_UDP_DOMAIN, transport)
        config.add_target_address(
            snmpEngine,
            "my-router",
            udp.SNMP_UDP_DOMAIN,
            (self.host, self.port),
            "my-creds",
        )
        return snmpEngine, transport

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

    async def _run_command(self, send):
        loop = asyncio.get_running_loop()
        snmpEngine, transport = self._setup_engine(loop)
        if transport._lport is not None:
            await transport._lport

        done = asyncio.Event()
        result = {}

        def _cb(
            engine_,
            sendRequestHandle,
            errorIndication,
            errorStatus,
            errorIndex,
            varBindTable,
            cbCtx,
        ):
            result["args"] = (
                engine_,
                sendRequestHandle,
                errorIndication,
                errorStatus,
                errorIndex,
                varBindTable,
                cbCtx,
            )
            done.set()

        send(snmpEngine, _cb)
        try:
            await asyncio.wait_for(done.wait(), timeout=10.0)
        finally:
            snmpEngine.transport_dispatcher.close_dispatcher()
        return result.get("args")

    def _dispatch(self, send, callback):
        args = asyncio.run(self._run_command(send))
        if args is not None and callback is not None:
            callback(*args)

    def get_command(self, OID=((1, 3, 6, 1, 2, 1, 1, 1, 0), None), callback=None):
        if not callback:
            callback = self.cbFun

        def send(snmpEngine, cb):
            cmdgen.GetCommandGenerator().send_varbinds(
                snmpEngine,
                "my-router",
                None,
                "",
                (OID,),
                cb,
            )

        self._dispatch(send, callback)

    def set_command(self, OID, callback=None):
        if not callback:
            callback = self.cbFun

        def send(snmpEngine, cb):
            cmdgen.SetCommandGenerator().send_varbinds(
                snmpEngine,
                "my-router",
                None,
                "",
                (OID,),
                cb,
            )

        self._dispatch(send, callback)

    def walk_command(self, OID, callback=None):
        if not callback:
            callback = self.cbFun

        def send(snmpEngine, cb):
            cmdgen.NextCommandGenerator().send_varbinds(
                snmpEngine,
                "my-router",
                None,
                "",
                (OID,),
                cb,
            )

        self._dispatch(send, callback)


if __name__ == "__main__":
    snmp_client = SNMPClient("127.0.0.1", 161)
    OID = ((1, 3, 6, 1, 2, 1, 1, 1, 0), None)
    snmp_client.get_command(OID)
