# Copyright (C) 2013  Daniel creo Haslinger <creo-conpot@blackmesa.at>
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

from logging.handlers import SysLogHandler
import logging

class SysLogger(object):
    def __init__(self):
        logger = logging.getLogger()
        logger.addHandler(SysLogHandler('/dev/log'))

    def log(self, event):
        for entry in event['data'].values():
            logging.warn("REMOTE[{0}] PROTOCOL[{1}] REQUEST[{2}] RESPONSE[{3}]".format(str(event["remote"]),
                                                                                        event['data_type'],
                                                                                        entry.get('request'),
                                                                                        entry.get('response')))