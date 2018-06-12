from conpot.core import get_interface
from datetime import datetime

core_interface = get_interface()


def conpot_protocol(cls):
    class Wrapper(object):
        def __init__(self, *args, **kwargs):
            self.wrapped = cls(*args, **kwargs)
            self.cls = cls
            if self.cls.__name__ not in 'Proxy':
                core_interface.protocols[self.cls] = self.wrapped

        def __getattr__(self, name):
            if name == 'handle':
                # assuming that handle function from a class is only called when a client tries to connect with an
                # enabled protocol, update the last_active (last_attacked attribute)
                # FIXME: No handle function in HTTPServer
                core_interface.last_active = datetime.now().strftime("%b %d %Y - %H:%M:%S")
            return getattr(core_interface.protocols[self.cls], name)

        def __repr__(self):
            return self.cls.__repr__(self.wrapped)

        __doc__ = property(lambda self: self.cls.__doc__)
        __module__ = property(lambda self: self.cls.__module__)
        __name__ = property(lambda self: self.cls.__name__)
    return Wrapper
