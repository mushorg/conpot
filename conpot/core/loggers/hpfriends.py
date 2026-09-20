# Copyright (C) 2013 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

import logging
import socket
import threading
import time

import hpfeeds

logger = logging.getLogger(__name__)


class HPFriendsLogger(object):
    def __init__(self, host, port, ident, secret, channels):
        self.host = host
        self.port = port
        self.ident = ident
        self.secret = secret
        self.channels = channels
        self.max_retires = 5
        self._initial_connection_happend = False
        self.hpc = None
        self._thread = threading.Thread(
            target=self._start_connection,
            args=(host, port, ident, secret),
            daemon=True,
            name="hpfriends-connect",
        )
        self._thread.start()

    def _start_connection(self, host, port, ident, secret):
        # if no initial connection to hpfeeds this will hang forever, reconnect=True
        # only comes into play when lost connection after the initial connect.
        self.hpc = hpfeeds.new(host, port, ident, secret)
        self._initial_connection_happend = True

    def log(self, data):
        retries = 0
        if self._initial_connection_happend:
            while True:
                if retries >= self.max_retires:
                    break
                try:
                    self.hpc.publish(self.channels, data)
                except socket.error:
                    retries += 1
                    self.__init__(
                        self.host, self.port, self.ident, self.secret, self.channels
                    )
                    time.sleep(0.5)
                else:
                    break
            error_msg = self.hpc.wait()
            return error_msg
        else:
            error_msg = (
                "Not logging event because initial hpfeeds connect has not happend yet."
            )
            logger.warning(error_msg)
            return error_msg
