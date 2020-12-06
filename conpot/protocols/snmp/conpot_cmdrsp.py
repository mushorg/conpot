import sys
import logging
import random

from pysnmp.entity.rfc3413 import cmdrsp
from pysnmp.proto import error
from pysnmp.proto.api import v2c
import pysnmp.smi.error
from pysnmp import debug
import gevent
import conpot.core as conpot_core
from conpot.utils.ext_ip import get_interface_ip

logger = logging.getLogger(__name__)


class conpot_extension(object):
    def _getStateInfo(self, snmpEngine, stateReference):
        for _, v in list(snmpEngine.messageProcessingSubsystems.items()):
            if stateReference in v._cache.__dict__["_Cache__stateReferenceIndex"]:
                state_dict = v._cache.__dict__["_Cache__stateReferenceIndex"][
                    stateReference
                ][0]

        addr = state_dict["transportAddress"]

        # msgVersion 0/1 to SNMPv1/2, msgversion 3 corresponds to SNMPv3
        if state_dict["msgVersion"] < 3:
            snmp_version = state_dict["msgVersion"] + 1
        else:
            snmp_version = state_dict["msgVersion"]

        return addr, snmp_version

    def log(self, version, msg_type, addr, req_varBinds, res_varBinds=None, sock=None):
        session = conpot_core.get_session(
            "snmp", addr[0], addr[1], get_interface_ip(addr[0]), sock.getsockname()[1]
        )
        req_oid = req_varBinds[0][0]
        req_val = req_varBinds[0][1]
        event_type = "SNMPv{0} {1}".format(version, msg_type)
        request = {"oid": str(req_oid), "val": str(req_val)}
        response = None

        logger.info("%s request from %s: %s %s", event_type, addr, req_oid, req_val)

        if res_varBinds:
            res_oid = ".".join(map(str, res_varBinds[0][0]))
            res_val = res_varBinds[0][1]
            logger.info("%s response to %s: %s %s", event_type, addr, res_oid, res_val)
            response = {"oid": str(res_oid), "val": str(res_val)}

        session.add_event(
            {"type": event_type, "request": request, "response": response}
        )

    def do_tarpit(self, delay):

        # sleeps the thread for $delay ( should be either 1 float to apply a static period of time to sleep,
        # or 2 floats seperated by semicolon to sleep a randomized period of time determined by ( rand[x;y] )

        lbound, _, ubound = delay.partition(";")

        if not lbound or lbound is None:
            # no lower boundary found. Assume zero latency
            pass
        elif not ubound or ubound is None:
            # no upper boundary found. Assume static latency
            gevent.sleep(float(lbound))
        else:
            # both boundaries found. Assume random latency between lbound and ubound
            gevent.sleep(random.uniform(float(lbound), float(ubound)))

    def check_evasive(self, state, threshold, addr, cmd):

        # checks if current states are > thresholds and returns True if the request
        # is considered to be a DoS request.

        state_individual, state_overall = state
        threshold_individual, _, threshold_overall = threshold.partition(";")

        if int(threshold_individual) > 0:
            if int(state_individual) > int(threshold_individual):
                logger.warning(
                    "SNMPv%s: DoS threshold for %s exceeded (%s/%s).",
                    cmd,
                    addr,
                    state_individual,
                    threshold_individual,
                )
                # DoS threshold exceeded.
                return True

        if int(threshold_overall) > 0:
            if int(state_overall) > int(threshold_overall):
                logger.warning(
                    "SNMPv%s: DDoS threshold exceeded (%s/%s).",
                    cmd,
                    state_individual,
                    threshold_overall,
                )
                # DDoS threshold exceeded
                return True

        # This request will be answered
        return False


class c_GetCommandResponder(cmdrsp.GetCommandResponder, conpot_extension):
    def __init__(self, snmpEngine, snmpContext, databus_mediator, host, port):
        self.databus_mediator = databus_mediator
        self.tarpit = "0;0"
        self.threshold = "0;0"
        self.host = host
        self.port = port

        cmdrsp.GetCommandResponder.__init__(self, snmpEngine, snmpContext)
        conpot_extension.__init__(self)

    def handleMgmtOperation(self, snmpEngine, stateReference, contextName, PDU, acInfo):
        (acFun, acCtx) = acInfo
        # rfc1905: 4.2.1.1
        mgmtFun = self.snmpContext.getMibInstrum(contextName).readVars

        varBinds = v2c.apiPDU.getVarBinds(PDU)
        addr, snmp_version = self._getStateInfo(snmpEngine, stateReference)

        evasion_state = self.databus_mediator.update_evasion_table(addr)
        if self.check_evasive(
            evasion_state, self.threshold, addr, str(snmp_version) + " Get"
        ):
            return None

        rspVarBinds = None
        try:
            # generate response
            rspVarBinds = mgmtFun(v2c.apiPDU.getVarBinds(PDU), (acFun, acCtx))

            # determine the correct response class and update the dynamic value table
            reference_class = rspVarBinds[0][1].__class__.__name__
            # reference_value = rspVarBinds[0][1]

            response = self.databus_mediator.get_response(
                reference_class, tuple(rspVarBinds[0][0])
            )
            if response:
                rspModBinds = [(tuple(rspVarBinds[0][0]), response)]
                rspVarBinds = rspModBinds

        finally:
            sock = snmpEngine.transportDispatcher.socket
            self.log(snmp_version, "Get", addr, varBinds, rspVarBinds, sock)

        # apply tarpit delay
        if self.tarpit != 0:
            self.do_tarpit(self.tarpit)

        # send response
        self.sendRsp(snmpEngine, stateReference, 0, 0, rspVarBinds)
        self.releaseStateInformation(stateReference)


class c_NextCommandResponder(cmdrsp.NextCommandResponder, conpot_extension):
    def __init__(self, snmpEngine, snmpContext, databus_mediator, host, port):
        self.databus_mediator = databus_mediator
        self.tarpit = "0;0"
        self.threshold = "0;0"
        self.host = host
        self.port = port

        cmdrsp.NextCommandResponder.__init__(self, snmpEngine, snmpContext)
        conpot_extension.__init__(self)

    def handleMgmtOperation(self, snmpEngine, stateReference, contextName, PDU, acInfo):
        (acFun, acCtx) = acInfo
        # rfc1905: 4.2.2.1

        mgmtFun = self.snmpContext.getMibInstrum(contextName).readNextVars
        varBinds = v2c.apiPDU.getVarBinds(PDU)

        addr, snmp_version = self._getStateInfo(snmpEngine, stateReference)

        evasion_state = self.databus_mediator.update_evasion_table(addr)
        if self.check_evasive(
            evasion_state, self.threshold, addr, str(snmp_version) + " GetNext"
        ):
            return None

        rspVarBinds = None
        try:
            while 1:
                rspVarBinds = mgmtFun(varBinds, (acFun, acCtx))

                # determine the correct response class and update the dynamic value table
                reference_class = rspVarBinds[0][1].__class__.__name__
                # reference_value = rspVarBinds[0][1]

                response = self.databus_mediator.get_response(
                    reference_class, tuple(rspVarBinds[0][0])
                )
                if response:
                    rspModBinds = [(tuple(rspVarBinds[0][0]), response)]
                    rspVarBinds = rspModBinds

                # apply tarpit delay
                if self.tarpit != 0:
                    self.do_tarpit(self.tarpit)

                # send response
                try:
                    self.sendRsp(snmpEngine, stateReference, 0, 0, rspVarBinds)
                except error.StatusInformation:
                    idx = sys.exc_info()[1]["idx"]
                    varBinds[idx] = (rspVarBinds[idx][0], varBinds[idx][1])
                else:
                    break

        finally:
            sock = snmpEngine.transportDispatcher.socket
            self.log(snmp_version, "GetNext", addr, varBinds, rspVarBinds, sock)

        self.releaseStateInformation(stateReference)


class c_BulkCommandResponder(cmdrsp.BulkCommandResponder, conpot_extension):
    def __init__(self, snmpEngine, snmpContext, databus_mediator, host, port):
        self.databus_mediator = databus_mediator
        self.tarpit = "0;0"
        self.threshold = "0;0"
        self.host = host
        self.port = port

        cmdrsp.BulkCommandResponder.__init__(self, snmpEngine, snmpContext)
        conpot_extension.__init__(self)

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

        evasion_state = self.databus_mediator.update_evasion_table(addr)
        if self.check_evasive(
            evasion_state, self.threshold, addr, str(snmp_version) + " Bulk"
        ):
            return None
        raise Exception("This class is not converted to new architecture")
        try:
            N = min(int(nonRepeaters), len(reqVarBinds))
            M = int(maxRepetitions)
            R = max(len(reqVarBinds) - N, 0)

            if R:
                M = min(M, self.maxVarBinds / R)

            debug.logger & debug.flagApp and debug.logger(
                "handleMgmtOperation: N %d, M %d, R %d" % (N, M, R)
            )

            mgmtFun = self.snmpContext.getMibInstrum(contextName).readNextVars

            if N:
                rspVarBinds = mgmtFun(reqVarBinds[:N], (acFun, acCtx))
            else:
                rspVarBinds = []

            varBinds = reqVarBinds[-R:]
            while M and R:
                rspVarBinds.extend(mgmtFun(varBinds, (acFun, acCtx)))
                varBinds = rspVarBinds[-R:]
                M = M - 1
        finally:
            sock = snmpEngine.transportDispatcher.socket
            self.log(snmp_version, "Bulk", addr, varBinds, rspVarBinds, sock)

        # apply tarpit delay
        if self.tarpit != 0:
            self.do_tarpit(self.tarpit)

        # send response
        if len(rspVarBinds):
            self.sendRsp(snmpEngine, stateReference, 0, 0, rspVarBinds)
            self.releaseStateInformation(stateReference)
        else:
            raise pysnmp.smi.error.SmiError()


class c_SetCommandResponder(cmdrsp.SetCommandResponder, conpot_extension):
    def __init__(self, snmpEngine, snmpContext, databus_mediator, host, port):
        self.databus_mediator = databus_mediator
        self.tarpit = "0;0"
        self.threshold = "0;0"
        self.host = host
        self.port = port

        conpot_extension.__init__(self)
        cmdrsp.SetCommandResponder.__init__(self, snmpEngine, snmpContext)

    def handleMgmtOperation(self, snmpEngine, stateReference, contextName, PDU, acInfo):
        (acFun, acCtx) = acInfo

        mgmtFun = self.snmpContext.getMibInstrum(contextName).writeVars

        varBinds = v2c.apiPDU.getVarBinds(PDU)
        addr, snmp_version = self._getStateInfo(snmpEngine, stateReference)

        evasion_state = self.databus_mediator.update_evasion_table(addr)
        if self.check_evasive(
            evasion_state, self.threshold, addr, str(snmp_version) + " Set"
        ):
            return None

        # rfc1905: 4.2.5.1-13
        rspVarBinds = None

        # apply tarpit delay
        if self.tarpit != 0:
            self.do_tarpit(self.tarpit)

        try:
            rspVarBinds = mgmtFun(v2c.apiPDU.getVarBinds(PDU), (acFun, acCtx))

            # generate response
            self.sendRsp(snmpEngine, stateReference, 0, 0, rspVarBinds)
            self.releaseStateInformation(stateReference)

            oid = tuple(rspVarBinds[0][0])
            self.databus_mediator.set_value(oid, rspVarBinds[0][1])

        except (
            pysnmp.smi.error.NoSuchObjectError,
            pysnmp.smi.error.NoSuchInstanceError,
        ):
            e = pysnmp.smi.error.NotWritableError()
            e.update(sys.exc_info()[1])
            raise e
        finally:
            sock = snmpEngine.transportDispatcher.socket
            self.log(snmp_version, "Set", addr, varBinds, rspVarBinds, sock)
