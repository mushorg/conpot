# Copyright (C) 2015  Adarsh Dinesh <adarshdinesh@gmail.com>
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

logger = logging.getLogger(__name__)


def check_mac(iface, addr):
    s = subprocess.Popen(["ifconfig", iface], stdout=subprocess.PIPE)
    data = s.stdout.read()
    if addr in data:
        return True
    else:
        return False


def change_mac(iface=None, mac=None, config=None, flag=None):
    if config:
        iface = config.get('change_mac_addr', 'iface')
        mac = config.get('change_mac_addr', 'addr')

    # Changing MAC address and restarting network
    subprocess.Popen(["/etc/init.d/networking", "stop"], stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
    subprocess.Popen(["ifconfig", iface, "hw", "ether", mac], stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
    subprocess.Popen(["/etc/init.d/networking", "start"], stderr=subprocess.STDOUT, stdout=subprocess.PIPE)

    if check_mac(iface, mac):
        if flag:
            logger.info('MAC address reverted to original %s' % (mac))
        else:
            logger.info('MAC address of interface %s changed %s' % (iface, mac))
    else:
        logger.warning('Could not change MAC address.')


def revert_mac(iface):
    s = subprocess.Popen(["ethtool", "-P", iface], stdout=subprocess.PIPE)
    mac = s.stdout.read().split(" ")[2].strip()
    change_mac(iface, mac, flag=True)
