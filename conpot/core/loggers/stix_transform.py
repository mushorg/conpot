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

import json
import ast
import textwrap

import stix
import stix.utils
from stix.core import STIXHeader, STIXPackage
from stix.common import InformationSource
from stix.common.vocabs import VocabString
from stix.incident import Incident
from stix.incident.time import Time as StixTime
from stix.indicator import Indicator
from stix.ttp import TTP, VictimTargeting
from stix.extensions.identity.ciq_identity_3_0 import CIQIdentity3_0Instance, STIXCIQIdentity3_0, OrganisationInfo

import cybox
from cybox.core import Observable
from cybox.objects.socket_address_object import SocketAddress
from cybox.objects.address_object import Address
from cybox.objects.port_object import Port
from cybox.objects.network_connection_object import NetworkConnection
from cybox.objects.artifact_object import Artifact, ZlibCompression, Base64Encoding
from cybox.common import ToolInformationList, ToolInformation
from cybox.common import Time as CyboxTime

from datetime import datetime

import conpot


class StixTransformer(object):
    def __init__(self, config, dom):
        self.config = config._sections['taxii']
        # This should not be hardcoded
        port_path_list = [
            '//conpot_template/protocols/modbus/@port',
            '//conpot_template/protocols/snmp/@port',
            '//conpot_template/protocols/http/@port',
            '//conpot_template/protocols/s7comm/@port'
        ]
        self.protocol_to_port_mapping = dict(
            modbus=502,
            snmp=161,
            http=80,
            s7comm=102,
        )
        for port_path in port_path_list:
            try:
                protocol_port = ast.literal_eval(dom.xpath(port_path)[0])
                protocol_name = port_path.rsplit("/", 2)[1]
                self.protocol_to_port_mapping[protocol_name] = protocol_port
            except IndexError:
                continue
        print self.protocol_to_port_mapping

    def _set_namespace(self, domain, name):
        stix_namespace = {domain: name}
        cybox_namespace = cybox.utils.nsparser.Namespace(domain, name)
        stix.utils.idgen.set_id_namespace(stix_namespace)
        cybox.utils.idgen.set_id_namespace(cybox_namespace)

    def _add_header(self, stix_package, title, desc):
        stix_header = STIXHeader()
        stix_header.title = title
        stix_header.description = desc
        stix_header.information_source = InformationSource()
        stix_header.information_source.time = CyboxTime()
        stix_header.information_source.time.produced_time = datetime.now()
        stix_package.stix_header = stix_header

    def transform(self, event):
        self._set_namespace(self.config['contact_domain'], self.config['contact_name'])
        stix_package = STIXPackage()
        self._add_header(stix_package, "Unauthorized traffic to honeypot", "Describes one or more honeypot incidents")

        incident = Incident(id_="%s:%s-%s" % (self.config['contact_name'], 'incident', event['session_id']))
        initial_time = StixTime()
        initial_time.initial_compromise = event['timestamp'].isoformat()
        incident.time = initial_time
        incident.title = "Conpot Event"
        incident.short_description = "Traffic to Conpot ICS honeypot"
        incident.add_category(VocabString(value='Scans/Probes/Attempted Access'))

        tool_list = ToolInformationList()
        tool_list.append(ToolInformation.from_dict({
            'name': "Conpot",
            'vendor': "Conpot Team",
            'version': conpot.__version__,
            'description': textwrap.dedent('Conpot is a low interactive server side Industrial Control Systems '
                                           'honeypot designed to be easy to deploy, modify and extend.')
        }))
        incident.reporter = InformationSource(tools=tool_list)

        incident.add_discovery_method("Monitoring Service")
        incident.confidence = "High"

        # Victim Targeting by Sector
        ciq_identity = CIQIdentity3_0Instance()
        #identity_spec = STIXCIQIdentity3_0()
        #identity_spec.organisation_info = OrganisationInfo(industry_type="Electricity, Industrial Control Systems")
        #ciq_identity.specification = identity_spec
        ttp = TTP(title="Victim Targeting: Electricity Sector and Industrial Control System Sector")
        ttp.victim_targeting = VictimTargeting()
        ttp.victim_targeting.identity = ciq_identity

        incident.leveraged_ttps.append(ttp)

        indicator = Indicator(title="Conpot Event")
        indicator.description = "Conpot network event"
        indicator.confidence = "High"
        source_port = Port.from_dict({'port_value': event['remote'][1], 'layer4_protocol': 'tcp'})
        dest_port = Port.from_dict({'port_value': self.protocol_to_port_mapping[event['data_type']],
                                    'layer4_protocol': 'tcp'})
        source_ip = Address.from_dict({'address_value': event['remote'][0], 'category': Address.CAT_IPV4})
        dest_ip = Address.from_dict({'address_value': event['public_ip'], 'category': Address.CAT_IPV4})
        source_address = SocketAddress.from_dict({'ip_address': source_ip.to_dict(), 'port': source_port.to_dict()})
        dest_address = SocketAddress.from_dict({'ip_address': dest_ip.to_dict(), 'port': dest_port.to_dict()})
        network_connection = NetworkConnection.from_dict(
            {'source_socket_address': source_address.to_dict(),
             'destination_socket_address': dest_address.to_dict(),
             'layer3_protocol': u"IPv4",
             'layer4_protocol': u"TCP",
             'layer7_protocol': event['data_type'],
             'source_tcp_state': u"ESTABLISHED",
             'destination_tcp_state': u"ESTABLISHED",
             }
        )
        indicator.add_observable(Observable(network_connection))

        artifact = Artifact()
        artifact.data = json.dumps(event['data'])
        artifact.packaging.append(ZlibCompression())
        artifact.packaging.append(Base64Encoding())
        indicator.add_observable(Observable(artifact))

        incident.related_indicators.append(indicator)
        stix_package.add_incident(incident)

        stix_package_xml = stix_package.to_xml()
        return stix_package_xml
