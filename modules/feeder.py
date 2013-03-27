import hpfeeds
import config


class HPFriendsLogger(object):

    def __init__(self):
        try:
            self.hpc = hpfeeds.new(config.hpfeeds_host, config.hpfeeds_port,
                                   config.hpfeeds_ident, config.hpfeeds_secret)
            self.hpc.connect()
        except Exception as e:
            raise

    def insert(self, data):
        for chan in config.hpfeeds_channels:
            self.hpc.publish(chan, data)