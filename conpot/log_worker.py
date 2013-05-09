import json

from conpot.modules.loggers.sqlite_log import SQLiteLogger
from conpot.modules.loggers.feeder import HPFriendsLogger


class LogWorker(object):
    def __init__(self, config, log_queue):
        self.log_queue = log_queue
        self.sqlite_logger = None
        self.friends_feeder = None

        if config.getboolean('sqlite', 'enabled'):
            self.sqlite_logger = SQLiteLogger()
        if config.getboolean('hpfriends', 'enabled'):
            self.friends_feeder = HPFriendsLogger()
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