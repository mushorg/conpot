# Copyright (C) 2014  Daniel creo Haslinger <creo-conpot@blackmesa.at>
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
import logging
import gevent

logger = logging.getLogger(__name__)


class JsonLogger(object):

    def __init__(self, file, sensorid, public_ip):
        self.file = file
        self.sensorid = sensorid
        self.public_ip = public_ip
	self.outfile = open(file, 'a',0) 

    def log(self, event, retry=1):
	data = {}
	data['sensor'] = str(self.sensorid)
	data['id'] = str(event["id"])
	data['src_ip'] = event["remote"][0]
	data['src_port'] = event["remote"][1]
	data['dst_ip'] = self.public_ip
	data['data_type'] = event["data_type"]
	data['request'] = event["data"].get('request')
	data['response']  = event["data"].get('response')
	 
        json.dump(data, self.outfile)

        return 1

    def log_session(self, session):
        pass

