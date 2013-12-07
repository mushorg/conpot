# Copyright (C) 2013 Johnny Vestergaard <jkv@unixcluster.dk>
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
import jinja2
import uuid
from jinja2 import Template
import os


class StixTransformer(object):
    def __init__(self):
        template_loader = jinja2.FileSystemLoader(searchpath=os.path.dirname(__file__))
        template_env = jinja2.Environment(loader=template_loader, undefined=jinja2.StrictUndefined)
        self.template = template_env.get_template('stix_template.xml')

    def transform(self, event):
        vars = {'package_id': str(uuid.uuid4()),
                'namespace': 'ConPot',
                'namespace_uri': 'http://conpot.org/stix-1',
                'package_timestamp': datetime.utcnow().isoformat(),
                'incident_id': event['session_id'],
                'incident_timestamp': event['timestamp'].isoformat(),
                'observable_id': str(uuid.uuid4()),
                'source_ip': event['remote'][0],
                'source_port': event['remote'][1],
                'l7_protocol': event['data_type']}
        return self.template.render(vars)


if __name__ == '__main__':
        test_event =      {'remote': ('127.0.0.1', 54872), 'data_type': 'modbus',
                           'timestamp': datetime.now(),
                           'session_id': '101d9884-b695-4d8b-bf24-343c7dda1b68',
                           'public_ip': '111.111.222.111'}
        stixTransformer = StixTransformer()
        xml_string = stixTransformer.transform(test_event)
        print xml_string
