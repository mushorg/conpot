from session_manager import SessionManager

sessionManager = SessionManager()


def get_sessionManager():
    return sessionManager


def get_session(*args, **kwargs):
    return sessionManager.get_session(*args, **kwargs)

