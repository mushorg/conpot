class ParseException(Exception):
    def __init__(self, protocol, reason, payload=""):
        self.proto = protocol
        self.reason = reason
        self.payload = payload

    def __str__(self):
        return "DissectException: proto:{0} reason:{1}".format(self.proto, self.reason)


class AssembleException(Exception):
    def __init__(self, protocol, reason, payload=""):
        self.proto = protocol
        self.reason = reason
        self.payload = payload

    def __str__(self):
        return "AssembleException: proto:{0} reason:{1}".format(self.proto, self.reason)
