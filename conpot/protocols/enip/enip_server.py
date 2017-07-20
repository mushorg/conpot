# Copyright (C) 2017  Yuru Shao <shaoyuru@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import logging
import cpppo

from gevent.server import StreamServer
from lxml import etree
from cpppo.server import network
from cpppo.server.enip import logix
from cpppo.server.enip.main import enip_srv

logger = logging.getLogger(__name__)

class EnipConfig(object):
    """
    Configurations parsed from template
    """
    def __init__(self, template):
        self.template = template
        self.parse_template()

    def parse_template(self):
        dom = etree.parse(self.template)
        self.vendor_id = int(dom.xpath('//enip/device_info/VendorId/text()')[0])
        self.device_type = int(dom.xpath('//enip/device_info/DeviceType/text()')[0])
        self.product_revision = int(dom.xpath('//enip/device_info/ProductRevision/text()')[0])
        self.product_code = int(dom.xpath('//enip/device_info/ProductCode/text()')[0])
        self.product_name = dom.xpath('//enip/device_info/ProductName/text()')[0]
        self.serial_number = dom.xpath('//enip/device_info/SerialNumber/text()')[0]
        self.mode = dom.xpath('//enip/mode/text()')[0]


class EnipServer(object):
    """
    ENIP server
    """
    def __init__(self, template, template_directory, args, timeout=5):
        self.timeout = timeout
        self.config = EnipConfig(template)
        self.stopped = False
        logger.debug('ENIP server serial number: ' + self.config.serial_number)
        logger.debug('ENIP server product name: ' + self.config.product_name)

    def handle(self, sock, address, enip_process=None, delay=None, **kwds):
        logger.debug("Incoming client address: (%s, %s)" % (address[0], address[1]))

    def start(self, host, port):
        '''
        connection = (host, port)
        self.server = StreamServer(connection, self.handle)
        self.server.start()
        '''
        srv_ctl = cpppo.dotdict()
        srv_ctl.control = cpppo.apidict(timeout=20)
        srv_ctl.control['done'] = False
        srv_ctl.control['disable'] = False
        srv_ctl.control.setdefault('latency', 0.1)

        tags = cpppo.dotdict()
        options = cpppo.dotdict()
        options.setdefault('enip_process', logix.process)
        kwargs = dict(options, tags=tags, server=srv_ctl)

        logger.debug('ENIP server started on: %s:%d' % (host, port))
        while not self.stopped:
            logger.debug('Server loop')
            network.server_main(address=(host, port), target=enip_srv, kwargs=kwargs,
                                idle_service=None,
                                udp=False, tcp=True, thread_factory=network.server_thread)


    def stop(self):
        logger.debug('Stopping ENIP server')
        self.stopped = True
