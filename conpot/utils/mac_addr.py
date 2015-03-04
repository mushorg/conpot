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
import subprocess
import re

logger = logging.getLogger(__name__)


def check_mac(iface, addr):
    s = subprocess.Popen(["spoof-mac.py", "list"], stdout=subprocess.PIPE)
    data = s.stdout.readlines()
    for line in data:
        if iface in line:
            break
    mac = re.search(r'([0-9a-f]{2}[:]){5}([0-9a-f]{2})', line, re.I).group()
    if mac == addr:
        return True
    else:
        return False


def change_mac(config=None, iface=None, mac=None):
    if config:
        iface = config.get('mac', 'iface')
        mac = config.get('mac', 'addr')
    subprocess.check_call(["spoof-mac.py", "set", "%s" % mac, "%s" % iface])
    if check_mac(iface, mac):
        logger.info('MAC address of interface {0} changed'
                    ' : {1}.'.format(iface, mac))
        return True
    else:
        logger.warning('Could not change MAC address.')
        return False

if __name__ == "__main__":
    pass
