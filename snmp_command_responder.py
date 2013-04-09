# Command Responder (GET/GETNEXT)
# Based on examples from http://pysnmp.sourceforge.net/

from pyasn1.codec.ber import encoder, decoder
from pysnmp.proto import api
import time
import bisect

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

    def handle(self, msg, address):
        while msg:
            msgVer = api.decodeMessageVersion(msg)

            try:
                pMod = api.protoModules[msgVer]
            except KeyError:
                print 'Unsupported SNMP version %s' % msgVer
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
                            (mibInstr[nextIdx].name, mibInstr[nextIdx](msgVer))
                        )

            elif reqPDU.isSameTypeWith(pMod.GetRequestPDU()):
                for oid, val in pMod.apiPDU.getVarBinds(reqPDU):
                    if not oid in mibInstrIdx.has_key:
                        # No such instance
                        pMod.apiPDU.setNoSuchInstanceError(rspPDU, errorIndex)
                        varBinds = pMod.apiPDU.getVarBinds(reqPDU)
                        break

                    varBinds.append((oid, mibInstrIdx[oid](msgVer)))

            else:
                # Report unsupported request type
                pMod.apiPDU.setErrorStatus(rspPDU, 'genErr')

            pMod.apiPDU.setVarBinds(rspPDU, varBinds)
            data = encoder.encode(rspMsg)
            #self.socket.sendto(encoder.encode(rspMsg), address)
            self.socket.sendto('Received %s bytes' % len(data), address)


mibInstr = [SysDescr(), Uptime()]  # sorted by object name

mibInstrIdx = {}
for mibVar in mibInstr:
    mibInstrIdx[mibVar.name] = mibVar


if __name__ == "__main__":
    udp_sock = gevent.socket.socket(gevent.socket.AF_INET, gevent.socket.SOCK_DGRAM)
    udp_sock.setsockopt(gevent.socket.SOL_SOCKET, gevent.socket.SO_BROADCAST, 1)
    udp_sock.bind(('localhost', 161))
    server = SNMPServer(udp_sock)
    print 'Starting echo server on port 161'
    server.serve_forever()