import hpfeeds
import config


class HPFriendsLogger(object):

    def __init__(self):
        try:
            self.hpc = hpfeeds.new(config.hpfriends_host, config.hpfriends_port,
                                   config.hpfriends_ident, config.hpfriends_secret)
            self.hpc.connect()
        except Exception as e:
            raise

    def log(self, data):
        for chan in config.hpfriends_channels:
            self.hpc.publish(chan, data)