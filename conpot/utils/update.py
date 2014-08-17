import sys
import os

import gevent
from gevent import subprocess


class UpdateService(object):
    def __init__(self, logger=None, servers=None, protocol_greenlets=None):
        self.logger = logger
        self.servers = servers
        self.protocol_greenlets = protocol_greenlets

    def check_pip(self):
        r = subprocess.check_output(['pip', 'search', 'conpot'])
        installed = map(
            int, r.split("INSTALLED: ")[1].split("\n")[0].strip().split(".")
        )
        latest = map(
            int, r.split("LATEST: ")[1].split("\n")[0].strip().split(".")
        )
        for idx, val in enumerate(installed):
            if val < latest[idx]:
                pass

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


if __name__ == "__main__":
    us = UpdateService()
    us.check_pip()