import sys
import os

import gevent


class UpdateService(object):
    def __init__(self, logger, servers, protocol_greenlets):
        self.logger = logger
        self.servers = servers
        self.protocol_greenlets = protocol_greenlets

    def run(self):
        while True:
            gevent.sleep(1)
            for server in self.servers:
                server.stop()
            for p_greenlet in self.protocol_greenlets:
                p_greenlet.kill()
            gevent.joinall(self.protocol_greenlets)
            args = sys.argv[:]
            self.logger.info('Re-spawning %s' % ' '.join(args))
            args.insert(0, sys.executable)
            os.execv(sys.executable, args)