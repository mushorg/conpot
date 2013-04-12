from pysnmp.entity.engine import SnmpEngine


class Engine(SnmpEngine):

    def __init__(self):
        SnmpEngine.__init__(self, snmpEngineID=None, maxMessageSize=65507, msgAndPduDsp=None)