import json
import logging

from conpot.logging.sqlite_log import SQLiteLogger
from conpot.logging.feeder import HPFriendsLogger

logger = logging.getLogger(__name__)


class LogWorker(object):
    def __init__(self, config, log_queue):
        self.log_queue = log_queue
        self.sqlite_logger = None
        self.friends_feeder = None

        if config.getboolean('sqlite', 'enabled'):
            self.sqlite_logger = SQLiteLogger()
        if config.getboolean('hpfriends', 'enabled'):
            host = config.get('hpfriends', 'host')
            port = config.getint('hpfriends', 'port')
            ident = config.get('hpfriends', 'ident')
            secret = config.get('hpfriends', 'secret')
            channels = eval(config.get('hpfriends', 'channels'))
            try:
                self.friends_feeder = HPFriendsLogger(host, port, ident, secret, channels)
            except Exception as e:
                logger.exception(e.message)
                self.friends_feeder = None
        self.enabled = True

    def start(self):
        self.enabled = True
        while self.enabled:
            event = self.log_queue.get()
            assert 'data_type' in event
            assert 'timestamp' in event

            if self.friends_feeder:
                self.friends_feeder.log(json.dumps(event))

            if self.sqlite_logger:
                self.sqlite_logger.log(event)

    def stop(self):
        self.enabled = False