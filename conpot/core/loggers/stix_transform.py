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

import uuid
import os
import json
import ast

from datetime import datetime

import jinja2

import conpot


class StixTransformer(object):
    def __init__(self, config, dom):
        template_loader = jinja2.FileSystemLoader(searchpath=os.path.dirname(__file__))
        template_env = jinja2.Environment(loader=template_loader)
        self.config = config._sections['taxii']
        modbus_port = ast.literal_eval(dom.xpath('//conpot_template/protocols/modbus/@port')[0])
        snmp_port = ast.literal_eval(dom.xpath('//conpot_template/protocols/snmp/@port')[0])
        self.protocol_to_port_mapping = {'modbus': modbus_port,
                                         'http': config.getint('http', 'port'),
                                         's7comm': config.getint('s7', 'port'),
                                         'snmp': snmp_port}
        self.template = template_env.get_template('stix_template.xml')

    def transform(self, event):
        data = {'package_id': str(uuid.uuid4()),
                'namespace': 'ConPot',
                'namespace_uri': 'http://conpot.org/stix-1',
                'package_timestamp': datetime.utcnow().isoformat(),
                'incident_id': event['session_id'],
                'incident_timestamp': event['timestamp'].isoformat(),
                'conpotlog_observable_id': str(uuid.uuid4()),
                'network_observable_id': str(uuid.uuid4()),
                'source_ip': event['remote'][0],
                'source_port': event['remote'][1],
                'l7_protocol': event['data_type'],
                'conpot_version': conpot.__version__,
                'session_log': json.dumps(event['data']),
                'include_contact_info': self.config['include_contact_info'],
                'contact_name': self.config['contact_name'],
                'contact_mail': self.config['contact_email']}

        if 'public_ip' in event:
            data['destination_ip'] = event['public_ip']

        if event['data_type'] in self.protocol_to_port_mapping:
            data['destination_port'] = self.protocol_to_port_mapping[event['data_type']]
        else:
            raise Exception('No port mapping could be found for {0}'.format(event['data_type']))

        return self.template.render(data)
