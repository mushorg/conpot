import logging
import random

from pysnmp.entity.rfc3413 import cmdrsp
from pysnmp.proto import error
from pysnmp.proto.api import v2c
import pysnmp.smi.error
from pysnmp import debug
import gevent
import conpot.core as conpot_core
from conpot.utils.networking import get_interface_ip

logger = logging.getLogger(__name__)


def _tarpit_active(tarpit):
    return bool(tarpit) and tarpit != "0;0"


class conpot_extension(object):
    def _getStateInfo(self, snmpEngine, stateReference):
        state_dict = None
        for _, v in list(snmpEngine.message_processing_subsystems.items()):
            idx = v._cache.__dict__.get("_Cache__stateReferenceIndex", {})
            if stateReference in idx:
                state_dict = idx[stateReference][0]
                break
        if state_dict is None:
            raise KeyError("stateReference not found in MP cache")

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
        lbound, _, ubound = delay.partition(";")

        if not lbound or lbound is None:
            pass
        elif not ubound or ubound is None:
            gevent.sleep(float(lbound))
        else:
            gevent.sleep(random.uniform(float(lbound), float(ubound)))

    def check_evasive(self, state, threshold, addr, cmd):
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
                return True

        if int(threshold_overall) > 0:
            if int(state_overall) > int(threshold_overall):
                logger.warning(
                    "SNMPv%s: DDoS threshold exceeded (%s/%s).",
                    cmd,
                    state_individual,
                    threshold_overall,
                )
                return True

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

    def handle_management_operation(self, snmpEngine, stateReference, contextName, PDU):
        mib = self.snmpContext.get_mib_instrum(contextName)
        var_binds = v2c.apiPDU.get_varbinds(PDU)
        addr, snmp_version = self._getStateInfo(snmpEngine, stateReference)

        evasion_state = self.databus_mediator.update_evasion_table(addr)
        if self.check_evasive(
            evasion_state, self.threshold, addr, str(snmp_version) + " Get"
        ):
            return None

        ctx = dict(snmpEngine=snmpEngine, acFun=self.verify_access, cbCtx=self.cbCtx)
        rsp_var_binds = None
        try:
            rsp_var_binds = mib.read_variables(*var_binds, **ctx)
            reference_class = rsp_var_binds[0][1].__class__.__name__
            response = self.databus_mediator.get_response(
                reference_class, tuple(rsp_var_binds[0][0])
            )
            if response:
                rsp_var_binds = [(tuple(rsp_var_binds[0][0]), response)]
        finally:
            sock = snmpEngine.transport_dispatcher.socket
            self.log(snmp_version, "Get", addr, var_binds, rsp_var_binds, sock)

        if _tarpit_active(self.tarpit):
            self.do_tarpit(self.tarpit)

        self.send_varbinds(snmpEngine, stateReference, 0, 0, rsp_var_binds)
        self.release_state_information(stateReference)


class c_NextCommandResponder(cmdrsp.NextCommandResponder, conpot_extension):
    def __init__(self, snmpEngine, snmpContext, databus_mediator, host, port):
        self.databus_mediator = databus_mediator
        self.tarpit = "0;0"
        self.threshold = "0;0"
        self.host = host
        self.port = port

        cmdrsp.NextCommandResponder.__init__(self, snmpEngine, snmpContext)
        conpot_extension.__init__(self)

    def handle_management_operation(self, snmpEngine, stateReference, contextName, PDU):
        mib = self.snmpContext.get_mib_instrum(contextName)
        var_binds = list(v2c.apiPDU.get_varbinds(PDU))
        addr, snmp_version = self._getStateInfo(snmpEngine, stateReference)

        evasion_state = self.databus_mediator.update_evasion_table(addr)
        if self.check_evasive(
            evasion_state, self.threshold, addr, str(snmp_version) + " GetNext"
        ):
            return None

        ctx = dict(snmpEngine=snmpEngine, acFun=self.verify_access, cbCtx=self.cbCtx)
        rsp_var_binds = None
        try:
            while True:
                rsp_var_binds = mib.read_next_variables(*var_binds, **ctx)
                reference_class = rsp_var_binds[0][1].__class__.__name__
                response = self.databus_mediator.get_response(
                    reference_class, tuple(rsp_var_binds[0][0])
                )
                if response:
                    rsp_var_binds = [(tuple(rsp_var_binds[0][0]), response)]

                if _tarpit_active(self.tarpit):
                    self.do_tarpit(self.tarpit)

                try:
                    self.send_varbinds(snmpEngine, stateReference, 0, 0, rsp_var_binds)
                except error.StatusInformation as ex:
                    idx = ex["idx"]
                    var_binds[idx] = (rsp_var_binds[idx][0], var_binds[idx][1])
                else:
                    break
        finally:
            sock = snmpEngine.transport_dispatcher.socket
            self.log(snmp_version, "GetNext", addr, var_binds, rsp_var_binds, sock)

        self.release_state_information(stateReference)


class c_BulkCommandResponder(cmdrsp.BulkCommandResponder, conpot_extension):
    def __init__(self, snmpEngine, snmpContext, databus_mediator, host, port):
        self.databus_mediator = databus_mediator
        self.tarpit = "0;0"
        self.threshold = "0;0"
        self.host = host
        self.port = port

        cmdrsp.BulkCommandResponder.__init__(self, snmpEngine, snmpContext)
        conpot_extension.__init__(self)

    def handle_management_operation(self, snmpEngine, stateReference, contextName, PDU):
        non_repeaters = v2c.apiBulkPDU.get_non_repeaters(PDU)
        if non_repeaters < 0:
            non_repeaters = 0
        max_repetitions = v2c.apiBulkPDU.get_max_repetitions(PDU)
        if max_repetitions < 0:
            max_repetitions = 0

        req_var_binds = v2c.apiPDU.get_varbinds(PDU)
        addr, snmp_version = self._getStateInfo(snmpEngine, stateReference)

        evasion_state = self.databus_mediator.update_evasion_table(addr)
        if self.check_evasive(
            evasion_state, self.threshold, addr, str(snmp_version) + " Bulk"
        ):
            return None

        N = min(int(non_repeaters), len(req_var_binds))
        M = int(max_repetitions)
        R = max(len(req_var_binds) - N, 0)

        if R:
            M = min(M, self.max_varbinds // R)

        debug.logger & debug.FLAG_APP and debug.logger(
            "handle_management_operation: N %d, M %d, R %d" % (N, M, R)
        )

        mgmt_fun = self.snmpContext.get_mib_instrum(contextName).read_next_variables
        ctx = dict(snmpEngine=snmpEngine, acFun=self.verify_access, cbCtx=self.cbCtx)

        rsp_var_binds = []
        var_binds = []
        try:
            if N:
                rsp_var_binds = mgmt_fun(*req_var_binds[:N], **ctx)
            var_binds = list(req_var_binds[-R:])
            while M and R:
                rsp_var_binds.extend(mgmt_fun(*var_binds, **ctx))
                var_binds = rsp_var_binds[-R:]
                M -= 1
        finally:
            sock = snmpEngine.transport_dispatcher.socket
            self.log(snmp_version, "Bulk", addr, var_binds, rsp_var_binds, sock)

        if _tarpit_active(self.tarpit):
            self.do_tarpit(self.tarpit)

        if len(rsp_var_binds):
            self.send_varbinds(snmpEngine, stateReference, 0, 0, rsp_var_binds)
            self.release_state_information(stateReference)
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

    def handle_management_operation(self, snmpEngine, stateReference, contextName, PDU):
        mib = self.snmpContext.get_mib_instrum(contextName)
        var_binds = v2c.apiPDU.get_varbinds(PDU)
        addr, snmp_version = self._getStateInfo(snmpEngine, stateReference)

        evasion_state = self.databus_mediator.update_evasion_table(addr)
        if self.check_evasive(
            evasion_state, self.threshold, addr, str(snmp_version) + " Set"
        ):
            return None

        rsp_var_binds = None
        if _tarpit_active(self.tarpit):
            self.do_tarpit(self.tarpit)

        ctx = dict(snmpEngine=snmpEngine, acFun=self.verify_access, cbCtx=self.cbCtx)
        instrum_error = None
        try:
            try:
                rsp_var_binds = mib.write_variables(*var_binds, **ctx)
            except (
                pysnmp.smi.error.NoSuchObjectError,
                pysnmp.smi.error.NoSuchInstanceError,
            ) as cause:
                instrum_error = pysnmp.smi.error.NotWritableError()
                instrum_error.update(cause)
            else:
                self.send_varbinds(snmpEngine, stateReference, 0, 0, rsp_var_binds)
                oid = tuple(rsp_var_binds[0][0])
                self.databus_mediator.set_value(oid, rsp_var_binds[0][1])
            self.release_state_information(stateReference)
            if instrum_error:
                raise instrum_error
        finally:
            sock = snmpEngine.transport_dispatcher.socket
            self.log(snmp_version, "Set", addr, var_binds, rsp_var_binds, sock)
