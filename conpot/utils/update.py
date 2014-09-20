import sys
import os

import gevent
from gevent import subprocess


class UpdateService(object):
    def __init__(self, config=None, logger=None, servers=None, protocol_greenlets=None):
        self.config = config
        self.logger = logger
        self.servers = servers
        self.protocol_greenlets = protocol_greenlets

    @classmethod
    def _pip_update_available(cls):
        r = subprocess.check_output(['pip', 'search', 'conpot'])
        if not "LATEST" in r:
            return False
        installed = map(int, r.split("INSTALLED: ")[1].split("\n")[0].strip().split("."))
        latest = map(int, r.split("LATEST: ")[1].split("\n")[0].strip().split("."))
        for idx, val in enumerate(installed):
            if val < latest[idx]:
                return True
        return False

    @classmethod
    def install_from_pip(cls):
        r = subprocess.check_output(['pip', 'install', '-U', 'conpot==0.2.1'])
        print r

    def run(self):
        while True:
            gevent.sleep(1)
            self.install_from_pip()
            if self._pip_update_available():
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
    print UpdateService._pip_update_available()
