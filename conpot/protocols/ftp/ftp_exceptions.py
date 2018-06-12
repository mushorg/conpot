class FTPBaseException(Exception):
    pass


class FTPMaxLoginAttemptsExceeded(FTPBaseException):
    pass