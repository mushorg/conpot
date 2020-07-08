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


def _check_mac(iface, addr):
    s = subprocess.Popen(["ifconfig", iface], stdout=subprocess.PIPE)
    data = s.stdout.read()
    if addr in data:
        return True
    else:
        return False


def _is_dhcp(iface):
    s = subprocess.Popen(
        ["cat", "/var/lib/dhcp/dhclient.leases"], stdout=subprocess.PIPE
    )
    data = s.stdout.read()
    if iface in data:
        return True
    else:
        return False


def _renew_lease(iface):
    subprocess.Popen(["dhclient", "-r"], stdout=subprocess.PIPE)
    subprocess.Popen(["dhclient", iface], stdout=subprocess.PIPE)


def change_mac(iface=None, mac=None, config=None, revert=None):
    if config:
        iface = config.get("change_mac_addr", "iface")
        mac = config.get("change_mac_addr", "addr")

    # Changing MAC address and restarting network
    subprocess.Popen(
        ["ip", "link", "set", iface, "down"],
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
    )
    subprocess.Popen(
        ["ip", "link", "set", "dev", iface, "address", mac],
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
    )
    subprocess.Popen(
        ["ip", "link", "set", iface, "up"],
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
    )

    if _check_mac(iface, mac):
        if revert:
            logger.info("MAC address reverted for interface %s", iface)
        else:
            logger.info("MAC address of interface %s changed %s", iface, mac)
        if _is_dhcp(iface):
            _renew_lease(iface)
            logger.info("Interface has a DHCP lease, refreshed.")
    else:
        logger.warning("Could not change MAC address.")


def revert_mac(iface):
    s = subprocess.Popen(["ethtool", "-P", iface], stdout=subprocess.PIPE)
    mac = s.stdout.read().split(" ")[2].strip()
    change_mac(iface, mac, revert=True)
