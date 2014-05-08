# Copyright (C) 2014 Johnny Vestergaard <jkv@unixcluster.dk>
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
from lxml import etree

from bacpypes.comm import Server

import conpot.core as conpot_core

logger = logging.getLogger(__name__)

class BacnetServer(Server):
    def __init__(self, template):
        dom = etree.parse(template)
        template_name = dom.xpath('//conpot_template/@name')[0]
        databus = conpot_core.get_databus()
        identifier_key = dom.xpath('//conpot_template/protocols/bacnet/device_identifier/text()')[0]
        self.device_identifier = databus.get_value(identifier_key)
        name_key = dom.xpath('//conpot_template/protocols/bacnet/device_name/text()')[0]
        self.device_name = databus.get_value(name_key)
        logger.info('Conpot Bacnet initialized using the {0} template.'.format(template_name))

    def get_server(self, host, port):
        connection = (host, port)
        logger.info('Bacnet server started on: {0}'.format(connection))
        return None
