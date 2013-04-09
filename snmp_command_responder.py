# Command Responder (GET/GETNEXT)
# Based on examples from http://pysnmp.sourceforge.net/

import time
import bisect

from pyasn1.codec.ber import encoder, decoder
from pysnmp.proto import api
from pysnmp.entity import engine
from pysnmp.smi import builder

import gevent
from gevent import socket
from modules.udp_server import DatagramServer


class SysDescr(object):
    name = (1, 3, 6, 1, 2, 1, 1, 1, 0)

    def __cmp__(self, other):
        return cmp(self.name, other)

    def __call__(self, protoVer):
        return api.protoModules[protoVer].OctetString('PySNMP example command responder at %s' % __file__)


class Uptime(object):
    name = (1, 3, 6, 1, 2, 1, 1, 3, 0)
    birthday = time.time()

    def __cmp__(self, other):
        return cmp(self.name, other)

    def __call__(self, protoVer):
        return api.protoModules[protoVer].TimeTicks(
            (time.time() - self.birthday) * 100)


class SNMPServer(DatagramServer):

    def _import_mib(self):
        snmpEngine = engine.SnmpEngine()
        mibBuilder = snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder
        mibSources = mibBuilder.getMibSources() + (
            builder.DirMibSource('.'),
        )
        mibBuilder.setMibSources(*mibSources)

        # Create and put on-line my managed object
        deliveryTime, = mibBuilder.importSymbols('TRS-MIB', 'trsDeliveryTime')
        Integer32, = snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder.importSymbols('SNMPv2-SMI', 'Integer32')

        MibScalarInstance, = mibBuilder.importSymbols('SNMPv2-SMI', 'MibScalarInstance')

        class MyDeliveryTime(Integer32):

            def readGet(self, name, val, idx, (acFun, acCtx)):
                return name, self.syntax.clone(42)

        deliveryTimeInstance = MibScalarInstance(
            deliveryTime.name, (0,), deliveryTime.syntax
        )
        mibBuilder.exportSymbols('TRS-MIB', deliveryTimeInstance=deliveryTimeInstance)  # creating MIB

    def handle(self, msg, address):
        mibInstr = [SysDescr(), Uptime()]  # sorted by object name
        mibInstrIdx = {}
        for mibVar in mibInstr:
            mibInstrIdx[mibVar.name] = mibVar

        while msg:
            msg_version = api.decodeMessageVersion(msg)
            print "msg_version", msg_version
            try:
                pMod = api.protoModules[msg_version]
            except KeyError:
                print 'Unsupported SNMP version %s' % msg_version
                return
            reqMsg, msg = decoder.decode(msg, asn1Spec=pMod.Message(),)
            rspMsg = pMod.apiMessage.getResponse(reqMsg)
            rspPDU = pMod.apiMessage.getPDU(rspMsg)
            reqPDU = pMod.apiMessage.getPDU(reqMsg)
            varBinds = []
            errorIndex = -1

            # GETNEXT PDU
            if reqPDU.isSameTypeWith(pMod.GetNextRequestPDU()):
                # Produce response var-binds
                errorIndex = -1
                for oid, val in pMod.apiPDU.getVarBinds(reqPDU):
                    errorIndex += 1
                    # Search next OID to report
                    nextIdx = bisect.bisect(mibInstr, oid)
                    if nextIdx == len(mibInstr):
                        # Out of MIB
                        pMod.apiPDU.setEndOfMibError(rspPDU, errorIndex)
                    else:
                        # Report value if OID is found
                        varBinds.append(
                            (mibInstr[nextIdx].name, mibInstr[nextIdx](msg_version))
                        )

            elif reqPDU.isSameTypeWith(pMod.GetRequestPDU()):
                for oid, val in pMod.apiPDU.getVarBinds(reqPDU):
                    if not oid in mibInstrIdx:
                        print "No such instance"
                        pMod.apiPDU.setNoSuchInstanceError(rspPDU, errorIndex)
                        varBinds = pMod.apiPDU.getVarBinds(reqPDU)
                        break

                    varBinds.append((oid, mibInstrIdx[oid](msg_version)))

            else:
                # Report unsupported request type
                pMod.apiPDU.setErrorStatus(rspPDU, 'genErr')

            pMod.apiPDU.setVarBinds(rspPDU, varBinds)
            data = encoder.encode(rspMsg)
            self.socket.sendto(data, address)


if __name__ == "__main__":
    udp_sock = gevent.socket.socket(gevent.socket.AF_INET, gevent.socket.SOCK_DGRAM)
    udp_sock.setsockopt(gevent.socket.SOL_SOCKET, gevent.socket.SO_BROADCAST, 1)
    udp_sock.bind(('localhost', 161))
    server = SNMPServer(udp_sock)
    print 'Starting echo server on port 161'
    server.serve_forever()