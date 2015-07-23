# Copyright (C) 2015 Andrea De Pasquale <andrea@de-pasquale.name>
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
import json
from pyshark import InMemCapture

logger = logging.getLogger(__name__)


class WiresharkDecoder(object):

    def __init__(self):
        self.dissector = InMemCapture()

    def dissect(self, data):
        return self.dissector.feed_packet(data)

    def _print_packet(self, packet):
        return NotImplementedError

    def decode_in(self, data):
        packet_in = self.dissect(data)
        return self._print_packet(packet_in)

    def decode_out(self, data):
        packet_out = self.dissect(data)
        return self._print_packet(packet_out)


class GenericWiresharkDecoder(WiresharkDecoder):

    def _print_packet(self, packet):
        # using packet.pretty_print() doesn't seem a good idea, so...
        return json.dumps(self._packet_to_json(packet))

    def _packet_to_json(self, packet):
        p_data = {}
        for layer in packet.layers:
            l_data = {}
            for field in layer.field_names:
                l_data[field] = layer.get_field(field)
            p_data[layer.layer_name] = l_data
        return p_data
