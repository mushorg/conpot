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

import logging

import libtaxii
import libtaxii.messages
from libtaxii.messages_11 import ContentBlock, InboxMessage, generate_message_id
from libtaxii.clients import HttpClient

from conpot.core.loggers.stix_transform import StixTransformer

logger = logging.getLogger(__name__)


class TaxiiLogger(object):
    def __init__(self, config, dom):
        self.host = config.get("taxii", "host")
        self.port = config.getint("taxii", "port")
        self.inbox_path = config.get("taxii", "inbox_path")
        self.use_https = config.getboolean("taxii", "use_https")

        self.client = HttpClient()
        self.client.setProxy("noproxy")
        self.stix_transformer = StixTransformer(config, dom)

    def log(self, event):
        # converts from conpot log format to STIX compatible xml
        stix_package = self.stix_transformer.transform(event)

        # wrapping the stix message in a TAXII envelope
        content_block = ContentBlock(
            libtaxii.CB_STIX_XML_11, stix_package.encode("utf-8")
        )
        inbox_message = InboxMessage(
            message_id=generate_message_id(), content_blocks=[content_block]
        )
        inbox_xml = inbox_message.to_xml()

        # the actual call to the TAXII web service
        response = self.client.callTaxiiService2(
            self.host, self.inbox_path, libtaxii.VID_TAXII_XML_11, inbox_xml, self.port
        )
        response_message = libtaxii.get_message_from_http_response(response, "0")

        if response_message.status_type != libtaxii.messages.ST_SUCCESS:
            logger.error(
                "Error while transmitting message to TAXII server: %s",
                response_message.message,
            )
            return False
        else:
            return True
