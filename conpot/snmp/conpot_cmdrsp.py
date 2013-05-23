import sys
import logging

from pysnmp.entity.rfc3413 import cmdrsp
from pysnmp.proto import error
from pysnmp.proto.api import v2c
import pysnmp.smi.error
from pysnmp import debug

logger = logging.getLogger(__name__)


class conpot_extension(object):
    def _getStateInfo(self, snmpEngine, stateReference):
        for k, v in snmpEngine.messageProcessingSubsystems.items():
            if stateReference in v._cache.__dict__['_Cache__stateReferenceIndex']:
                state_dict = v._cache.__dict__['_Cache__stateReferenceIndex'][stateReference][0]

        addr = state_dict['transportAddress']

        if state_dict['msgVersion'] < 3:
            snmp_version = state_dict['msgVersion'] + 1
        else:
            snmp_version = state_dict['msgVersion']

        return addr, snmp_version


class c_GetCommandResponder(cmdrsp.GetCommandResponder, conpot_extension):
    def handleMgmtOperation(
            self, snmpEngine, stateReference, contextName, PDU, acInfo):
        (acFun, acCtx) = acInfo
        # rfc1905: 4.2.1.1
        mgmtFun = self.snmpContext.getMibInstrum(contextName).readVars

        varBinds = v2c.apiPDU.getVarBinds(PDU)
        addr, snmp_version = self._getStateInfo(snmpEngine, stateReference)
        logger.info('SNMPv{0} Get request from {1}: {2}'.format(snmp_version, addr, varBinds))
        rspVarBinds = mgmtFun(v2c.apiPDU.getVarBinds(PDU), (acFun, acCtx))
        logger.info('SNMPv{0} response to {1}: {2}'.format(snmp_version, addr, rspVarBinds))

        self.sendRsp(
            snmpEngine, stateReference, 0, 0, rspVarBinds)
        self.releaseStateInformation(stateReference)


class c_NextCommandResponder(cmdrsp.NextCommandResponder, conpot_extension):
    def handleMgmtOperation(self, snmpEngine, stateReference, contextName, PDU, acInfo):
        (acFun, acCtx) = acInfo
        # rfc1905: 4.2.2.1
        mgmtFun = self.snmpContext.getMibInstrum(contextName).readNextVars
        varBinds = v2c.apiPDU.getVarBinds(PDU)

        addr, snmp_version = self._getStateInfo(snmpEngine, stateReference)
        logger.info('SNMPv{0} GetNext request from {1}: {2}'.format(snmp_version, addr, varBinds))

        while 1:
            rspVarBinds = mgmtFun(varBinds, (acFun, acCtx))
            logger.info('SNMPv{0} response to {1}: {2}'.format(snmp_version, addr, rspVarBinds))
            try:
                self.sendRsp(snmpEngine, stateReference, 0, 0, rspVarBinds)
            except error.StatusInformation:
                idx = sys.exc_info()[1]['idx']
                varBinds[idx] = (rspVarBinds[idx][0], varBinds[idx][1])
            else:
                break

        self.releaseStateInformation(stateReference)


class c_BulkCommandResponder(cmdrsp.BulkCommandResponder, conpot_extension):
    def handleMgmtOperation(
            self, snmpEngine, stateReference, contextName, PDU, acInfo
    ):
        (acFun, acCtx) = acInfo
        nonRepeaters = v2c.apiBulkPDU.getNonRepeaters(PDU)
        if nonRepeaters < 0:
            nonRepeaters = 0
        maxRepetitions = v2c.apiBulkPDU.getMaxRepetitions(PDU)
        if maxRepetitions < 0:
            maxRepetitions = 0

        reqVarBinds = v2c.apiPDU.getVarBinds(PDU)
        addr, snmp_version = self._getStateInfo(snmpEngine, stateReference)
        logger.info('SNMPv{0} Bulk request from {1}: {2}'.format(snmp_version, addr, reqVarBinds))

        N = min(int(nonRepeaters), len(reqVarBinds))
        M = int(maxRepetitions)
        R = max(len(reqVarBinds) - N, 0)

        if R: M = min(M, self.maxVarBinds / R)

        debug.logger & debug.flagApp and debug.logger('handleMgmtOperation: N %d, M %d, R %d' % (N, M, R))

        mgmtFun = self.snmpContext.getMibInstrum(contextName).readNextVars

        if N:
            rspVarBinds = mgmtFun(reqVarBinds[:N], (acFun, acCtx))
        else:
            rspVarBinds = []

        varBinds = reqVarBinds[-R:]
        while M and R:
            rspVarBinds.extend(
                mgmtFun(varBinds, (acFun, acCtx))
            )
            varBinds = rspVarBinds[-R:]
            M = M - 1

        logger.info('SNMPv{0} response to {1}: {2}'.format(snmp_version, addr, rspVarBinds))
        if len(rspVarBinds):
            self.sendRsp(
                snmpEngine, stateReference, 0, 0, rspVarBinds
            )
            self.releaseStateInformation(stateReference)
        else:
            raise pysnmp.smi.error.SmiError()


class c_SetCommandResponder(cmdrsp.SetCommandResponder, conpot_extension):
    def handleMgmtOperation(
            self, snmpEngine, stateReference, contextName, PDU, acInfo):
        (acFun, acCtx) = acInfo
        mgmtFun = self.snmpContext.getMibInstrum(contextName).writeVars

        varBinds = v2c.apiPDU.getVarBinds(PDU)
        addr, snmp_version = self._getStateInfo(snmpEngine, stateReference)
        logger.info('SNMPv{0} Set request from {1}: {2}'.format(snmp_version, addr, varBinds))

        # rfc1905: 4.2.5.1-13
        try:
            rspVarBinds = mgmtFun(v2c.apiPDU.getVarBinds(PDU), (acFun, acCtx))
            logger.info('SNMPv{0} response to {1}: {2}'.format(snmp_version, addr, rspVarBinds))
            self.sendRsp(
                snmpEngine, stateReference, 0, 0, rspVarBinds
            )
            self.releaseStateInformation(stateReference)
        except ( pysnmp.smi.error.NoSuchObjectError,
                 pysnmp.smi.error.NoSuchInstanceError ):
            e = pysnmp.smi.error.NotWritableError()
            e.update(sys.exc_info()[1])
            raise e
