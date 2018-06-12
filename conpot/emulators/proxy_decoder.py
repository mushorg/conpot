import logging
import abc

logger = logging.getLogger(__name__)


class ProxyDecoder(abc.ABC):

    @abc.abstractmethod
    def decode_in(self, data):
        return data.decode('utf-8', 'replace').encode('utf-8')

    @abc.abstractmethod
    def decode_out(self, data):
        return data.decode('utf-8', 'replace').encode('utf-8')
