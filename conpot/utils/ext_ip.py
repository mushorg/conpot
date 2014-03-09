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


import logging
import socket

from HTMLParser import HTMLParser

import requests
from requests.exceptions import Timeout, ConnectionError


logger = logging.getLogger(__name__)


class AddressHTMLParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.address = None

    def handle_data(self, data):
        if "Address" in data:
            addr = data.rsplit(" ", 1)[1]
            self.address = addr


def _verify_address(addr):
    try:
        socket.inet_aton(addr)
        return True
    except socket.error:
        return False


def _parse_html(data):
    parser = AddressHTMLParser()
    parser.feed(data)
    return parser.address


def _fetch_data(url):
    data = None
    #we only want warning+ messages from the requests module
    logging.getLogger("requests").setLevel(logging.WARNING)
    try:
        req = requests.get(url)
        if req.status_code == 200:
            data = req.text
        else:
            raise ConnectionError
    except (Timeout, ConnectionError) as e:
        logger.warning('Could not fetch public ip: {0}'.format(e))
    finally:
        return data


def get_ext_ip(config=None, url=None):
    public_ip = None
    if config:
        url = config.get('fetch_public_ip', 'url')
    data = _fetch_data(url)
    public_ip = _parse_html(data)
    if _verify_address(public_ip):
        logger.info('Fetched {0} as external ip.'.format(public_ip))
    else:
        logger.warning('Could not fetch public ip: {0}'.format(public_ip))
    return public_ip


if __name__ == "__main__":
    print get_ext_ip(url="http://checkip.dyndns.org/")
