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
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


# one instance per connection
class AttackSession(object):

    def __init__(self, protocol, source_ip, source_port, databus):
        self.id = uuid.uuid4()
        logger.info('New {0} session from {1} ({2})'.format(protocol, source_ip, self.id))
        self.protocol = protocol
        self.source_ip = source_ip
        self.source_port = source_port
        self.timestamp = datetime.utcnow()
        self.databus = databus




