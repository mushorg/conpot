import sys
import logging
from datetime import datetime

from pysnmp.entity.rfc3413 import cmdrsp
from pysnmp.proto import error
from pysnmp.proto.api import v2c
import pysnmp.smi.error
from pysnmp import debug

logger = logging.getLogger(__name__)


class conpot_extension(object):
    def __init__(self, log_queue):
        self.log_queue = log_queue

    def _getStateInfo(self, snmpEngine, stateReference):
        for k, v in snmpEngine.messageProcessingSubsystems.items():
            if stateReference in v._cache.__dict__['_Cache__stateReferenceIndex']:
                state_dict = v._cache.__dict__['_Cache__stateReferenceIndex'][stateReference][0]

        addr = state_dict['transportAddress']

        #msgVersion 0/1 to SNMPv1/2, msgversion 3 corresponds to SNMPv3
        if state_dict['msgVersion'] < 3:
            snmp_version = state_dict['msgVersion'] + 1
        else:
            snmp_version = state_dict['msgVersion']

        return addr, snmp_version

    def log(self, version, type, addr, req_varBinds, res_varBinds=None):

        log_dict = {'remote': addr,
                    'timestamp': datetime.utcnow(),
                    'data_type': 'snmp',
                    'data': {0: {'request': 'SNMPv{0} {1}: {2}'.format(version, type, req_varBinds)}}}

        logger.info('SNMPv{0} {1} request from {2}: {3}'.format(version, type, addr, req_varBinds))

        if res_varBinds:
            logger.info('SNMPv{0} response to {1}: {2}'.format(version, addr, res_varBinds))
            log_dict['data'][0]['response'] = 'SNMPv{0} response: {1}'.format(version, res_varBinds)

        self.log_queue.put(log_dict)

class c_GetCommandResponder(cmdrsp.GetCommandResponder, conpot_extension):
    def __init__(self, snmpEngine, snmpContext, log_queue):
        cmdrsp.GetCommandResponder.__init__(self, snmpEngine, snmpContext)
        conpot_extension.__init__(self, log_queue)

    def handleMgmtOperation(
            self, snmpEngine, stateReference, contextName, PDU, acInfo):
        (acFun, acCtx) = acInfo
        # rfc1905: 4.2.1.1
        mgmtFun = self.snmpContext.getMibInstrum(contextName).readVars

        varBinds = v2c.apiPDU.getVarBinds(PDU)
        addr, snmp_version = self._getStateInfo(snmpEngine, stateReference)

        rspVarBinds = None
        try:
            rspVarBinds = mgmtFun(v2c.apiPDU.getVarBinds(PDU), (acFun, acCtx))
        finally:
            self.log(snmp_version, 'Get', addr, varBinds, rspVarBinds)

        self.sendRsp(
            snmpEngine, stateReference, 0, 0, rspVarBinds)
        self.releaseStateInformation(stateReference)


class c_NextCommandResponder(cmdrsp.NextCommandResponder, conpot_extension):
    def __init__(self, snmpEngine, snmpContext, log_queue):
        cmdrsp.NextCommandResponder.__init__(self, snmpEngine, snmpContext)
        conpot_extension.__init__(self, log_queue)

    def handleMgmtOperation(self, snmpEngine, stateReference, contextName, PDU, acInfo):
        (acFun, acCtx) = acInfo
        # rfc1905: 4.2.2.1
        mgmtFun = self.snmpContext.getMibInstrum(contextName).readNextVars
        varBinds = v2c.apiPDU.getVarBinds(PDU)

        addr, snmp_version = self._getStateInfo(snmpEngine, stateReference)

        rspVarBinds = None
        try:
            while 1:
                rspVarBinds = mgmtFun(varBinds, (acFun, acCtx))

                try:
                    self.sendRsp(snmpEngine, stateReference, 0, 0, rspVarBinds)
                except error.StatusInformation:
                    idx = sys.exc_info()[1]['idx']
                    varBinds[idx] = (rspVarBinds[idx][0], varBinds[idx][1])
                else:
                    break
        finally:
            self.log(snmp_version, 'GetNext', addr, varBinds, rspVarBinds)


        self.releaseStateInformation(stateReference)


class c_BulkCommandResponder(cmdrsp.BulkCommandResponder, conpot_extension):
    def __init__(self, snmpEngine, snmpContext, log_queue):
        cmdrsp.BulkCommandResponder.__init__(self, snmpEngine, snmpContext)
        conpot_extension.__init__(self, log_queue)

    def handleMgmtOperation(self, snmpEngine, stateReference, contextName, PDU, acInfo):
        (acFun, acCtx) = acInfo
        nonRepeaters = v2c.apiBulkPDU.getNonRepeaters(PDU)
        if nonRepeaters < 0:
            nonRepeaters = 0
        maxRepetitions = v2c.apiBulkPDU.getMaxRepetitions(PDU)
        if maxRepetitions < 0:
            maxRepetitions = 0

        reqVarBinds = v2c.apiPDU.getVarBinds(PDU)
        addr, snmp_version = self._getStateInfo(snmpEngine, stateReference)

        try:
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
        finally:
            self.log(snmp_version, 'Bulk', addr, varBinds, rspVarBinds)

        if len(rspVarBinds):
            self.sendRsp(
                snmpEngine, stateReference, 0, 0, rspVarBinds
            )
            self.releaseStateInformation(stateReference)
        else:
            raise pysnmp.smi.error.SmiError()


class c_SetCommandResponder(cmdrsp.SetCommandResponder, conpot_extension):
    def __init__(self, snmpEngine, snmpContext, log_queue):
        conpot_extension.__init__(self, log_queue)
        cmdrsp.SetCommandResponder.__init__(self, snmpEngine, snmpContext)

    def handleMgmtOperation(self, snmpEngine, stateReference, contextName, PDU, acInfo):
        (acFun, acCtx) = acInfo
        mgmtFun = self.snmpContext.getMibInstrum(contextName).writeVars

        varBinds = v2c.apiPDU.getVarBinds(PDU)
        addr, snmp_version = self._getStateInfo(snmpEngine, stateReference)

        # rfc1905: 4.2.5.1-13
        rspVarBinds = None
        try:
            rspVarBinds = mgmtFun(v2c.apiPDU.getVarBinds(PDU), (acFun, acCtx))
            self.sendRsp(
                snmpEngine, stateReference, 0, 0, rspVarBinds
            )
            self.releaseStateInformation(stateReference)
        except ( pysnmp.smi.error.NoSuchObjectError,
                 pysnmp.smi.error.NoSuchInstanceError ):
            e = pysnmp.smi.error.NotWritableError()
            e.update(sys.exc_info()[1])
            raise e
        finally:
            self.log(snmp_version, 'Set', addr, varBinds, rspVarBinds)
