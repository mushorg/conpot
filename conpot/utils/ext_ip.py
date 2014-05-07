# Copyright (C) 2014  Lukas Rist <glaslos@gmail.com>
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
import socket

import requests
from requests.exceptions import Timeout, ConnectionError


logger = logging.getLogger(__name__)


def _verify_address(addr):
    try:
        socket.inet_aton(addr)
        return True
    except (socket.error, UnicodeEncodeError, TypeError):
        return False


def _fetch_data(urls):
    # we only want warning+ messages from the requests module
    logging.getLogger("requests").setLevel(logging.WARNING)
    for url in urls:
        try:
            req = requests.get(url)
            if req.status_code == 200:
                data = req.text.strip()
                if data is None or not _verify_address(data):
                    continue
                else:
                    return data
            else:
                raise ConnectionError
        except (Timeout, ConnectionError) as e:
            logger.warning('Could not fetch public ip from {0}'.format(url))
    return None


def get_ext_ip(config=None, urls=None):
    if config:
        urls = json.loads(config.get('fetch_public_ip', 'urls'))
    public_ip = _fetch_data(urls)
    if public_ip:
        logger.info('Fetched {0} as external ip.'.format(public_ip))
    else:
        logger.warning('Could not fetch public ip: {0}'.format(public_ip))
    return public_ip


if __name__ == "__main__":
    print get_ext_ip(urls=["http://www.telize.com/ip", "http://queryip.net/ip/", "http://ifconfig.me/ip"])
