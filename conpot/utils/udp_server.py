# Copyright (c) 2009-2010 Denis Bilenko. See LICENSE for details.


import sys
import logging
import errno
from gevent import socket
from gevent import core
from gevent.baseserver import BaseServer


__all__ = ['DatagramServer']

logger = logging.getLogger(__name__)

class DatagramServer(BaseServer):
    """A generic UDP server. Receive UDP package on a listening socket and spawns user-provided *handle*
    for each connection with 2 arguments: the client message and the client address.

    Note that although the errors in a successfully spawned handler will not affect the server or other connections,
    the errors raised by :func:`accept` and *spawn* cause the server to stop accepting for a short amount of time. The
    exact period depends on the values of :attr:`min_delay` and :attr:`max_delay` attributes.

    The delay starts with :attr:`min_delay` and doubles with each successive error until it reaches :attr:`max_delay`.
    A successful :func:`accept` resets the delay to :attr:`min_delay` again.
    """

    # the number of seconds to sleep in case there was an error in recefrom() call
    # for consecutive errors the delay will double until it reaches max_delay
    # when accept() finally succeeds the delay will be reset to min_delay again
    min_delay = 0.01
    max_delay = 1

    def __init__(self, listener, handle=None, backlog=None, spawn='default', **ssl_args):
        BaseServer.__init__(self, listener, handle=handle, backlog=backlog, spawn=spawn)
        self.delay = self.min_delay
        self._recv_event = None
        self._start_receving_timer = None

    def set_listener(self, listener, backlog=None):
        BaseServer.set_listener(self, listener, backlog=backlog)
        try:
            self.socket = self.socket._sock
        except AttributeError:
            pass

    def set_spawn(self, spawn):
        BaseServer.set_spawn(self, spawn)
        if self.pool is not None:
            self.pool._semaphore.rawlink(self._start_receiving)

    def set_handle(self, handle):
        BaseServer.set_handle(self, handle)
        self._handle = self.handle

    @property
    def isStarted(self):
        return self._recv_event is not None or self._start_receving_timer is not None

    def start_accepting(self):
        if self._recv_event is None:
            self._recv_event = core.read_event(self.socket.fileno(), self._do_recv, persist=True)

    def _start_receiving(self, _event):
        if self._recv_event is None:
            if 'socket' not in self.__dict__:
                return
            self._recv_event = core.read_event(self.socket.fileno(), self._do_recv, persist=True)

    def stop_accepting(self):
        if self._recv_event is not None:
            self._recv_event.cancel()
            self._recv_event = None
        if self._start_receving_timer is not None:
            self._start_receving_timer.cancel()
            self._start_receving_timer = None

    def _do_recv(self, event, _evtype):
        assert event is self._recv_event
        address = None
        try:
            if self.full():
                self.stop_accepting()
                return
            try:
                msg, address = self.socket.recvfrom(1024)
            except socket.error, err:
                if err[0] == errno.EAGAIN:
                    sys.exc_clear()
                    return
                raise

            self.delay = self.min_delay
            spawn = self._spawn
            if spawn is None:
                self._handle(msg, address)
            else:
                spawn(self._handle, msg, address)
            return
        except Exception as ex:
            logger.exception('Exception caught:'.format(ex))
            ex = sys.exc_info()[1]
            if self.is_fatal_error(ex):
                self.kill()
                sys.stderr.write('ERROR: %s failed with %s\n' % (self, str(ex) or repr(ex)))
                return
        try:
            if address is None:
                sys.stderr.write('%s: Failed.\n' % (self, ))
            else:
                sys.stderr.write('%s: Failed to handle request from %s\n' % (self, address, ))
        except Exception as ex:
            logger.exception('Exception caught:'.format(ex))
        if self.delay >= 0:
            self.stop_accepting()
            self._start_receving_timer = core.timer(self.delay, self.start_accepting)
            self.delay = min(self.max_delay, self.delay * 2)
        sys.exc_clear()

    def is_fatal_error(self, ex):
        return isinstance(ex, socket.error) and ex[0] in (errno.EBADF, errno.EINVAL, errno.ENOTSOCK)