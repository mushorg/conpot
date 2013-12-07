# Copyright (C) 2013  Johnny Vestergaard <jkv@unixcluster.dk>
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

from datetime import datetime
import logging

from conpot.logging.stix_transform import StixTransformer
import libtaxii
from libtaxii.messages import ContentBlock, InboxMessage, generate_message_id
from libtaxii.clients import HttpClient

logger = logging.getLogger(__name__)


class TaxiiLogger(object):
    def __init__(self, host, port, inbox_path, use_https):
        self.host = host
        self.port = port
        self.inbox_path = inbox_path

        self.client = HttpClient()
        self.client.use_https = use_https
        self.client.setProxy('noproxy')

        self.stix_transformer = StixTransformer()

    def log(self, event):
        # converts from conpot log format to STIX compatible xml
        stix_package = self.stix_transformer.transform(event)

        # wrapping the stix message in a TAXII envelope
        content_block = ContentBlock(libtaxii.CB_STIX_XML_10, stix_package)
        inbox_message = InboxMessage(message_id=generate_message_id(), content_blocks=[content_block])
        inbox_xml = inbox_message.to_xml()

        # the actual call to the TAXII web service
        response = self.client.callTaxiiService2(self.host, self.inbox_path, libtaxii.VID_TAXII_XML_10, inbox_xml, self.port)
        response_message = libtaxii.get_message_from_http_response(response, '0')

        if response_message.status_type != libtaxii.messages.ST_SUCCESS:
            logger.error('Error while transmitting message to TAXII server: {0}'.format(response_message.status_detail))

if __name__ == '__main__':

        test_event = {'remote': ('127.0.0.1', 54872), 'data_type': 's7comm',
                      'timestamp': datetime.now(),
                      'session_id': '101d9884-b695-4d8b-bf24-343c7dda1b68',
                     }
        taxii_logger = TaxiiLogger('taxiitest.mitre.org', 80, '/services/inbox/default/', False)
        taxii_logger.log(test_event)
