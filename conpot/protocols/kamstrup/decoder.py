# Copyright (C) 2014  Johnny Vestergaard <jkv@unixcluster.dk>
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

logger = logging.getLogger(__name__)


class Decoder(object):

    REQUEST_MAGIC = 0x80
    RESPONSE_MAGIC = 0x40
    EOT_MAGIC = 0x0d

    # Following constants has been taken from pykamstrup, thanks PHK/Erik Jensen!
    # I owe beer...
    # ----------------------------------------------------------------------------
    # "THE BEER-WARE LICENSE" (Revision 42):
    # <phk@FreeBSD.ORG> wrote this file.  As long as you retain this notice you
    # can do whatever you want with this stuff. If we meet some day, and you think
    # this stuff is worth it, you can buy me a beer in return.   Poul-Henning Kamp
    # ----------------------------------------------------------------------------
    UNITS = {
                0: '', 1: 'Wh', 2: 'kWh', 3: 'MWh', 4: 'GWh', 5: 'j', 6: 'kj', 7: 'Mj',
                8: 'Gj', 9: 'Cal', 10: 'kCal', 11: 'Mcal', 12: 'Gcal', 13: 'varh',
                14: 'kvarh', 15: 'Mvarh', 16: 'Gvarh', 17: 'VAh', 18: 'kVAh',
                19: 'MVAh', 20: 'GVAh', 21: 'kW', 22: 'kW', 23: 'MW', 24: 'GW',
                25: 'kvar', 26: 'kvar', 27: 'Mvar', 28: 'Gvar', 29: 'VA', 30: 'kVA',
                31: 'MVA', 32: 'GVA', 33: 'V', 34: 'A', 35: 'kV',36: 'kA', 37: 'C',
                38: 'K', 39: 'l', 40: 'm3', 41: 'l/h', 42: 'm3/h', 43: 'm3xC',
                44: 'ton', 45: 'ton/h', 46: 'h', 47: 'hh:mm:ss', 48: 'yy:mm:dd',
                49: 'yyyy:mm:dd', 50: 'mm:dd', 51: '', 52: 'bar', 53: 'RTC',
                54: 'ASCII', 55: 'm3 x 10', 56: 'ton x 10', 57: 'GJ x 10',
                58: 'minutes', 59: 'Bitfield', 60: 's', 61: 'ms', 62: 'days',
                63: 'RTC-Q', 64: 'Datetime'
            }

    ESCAPES = [0x06, 0x0d, 0x1b, 0x40, 0x80]

    def __init__(self):
        self.in_data = []
        self.in_parsing = False
        self.out_data = []
        self.out_parsing = False

    def decode_in(self, data):
        for d in data:
            if not self.in_parsing and d != Decoder.REQUEST_MAGIC:
                logger.debug('No kamstrup request magic received, got: {0)'.format(data[0].encode('hex-codec')))
            else:
                self.in_parsing = True
                # TODO: alot of stuff here

    def decode_out(self, data):
        for d in data:
            if not self.out_parsing and d != Decoder.RESPONSE_MAGIC:
                    logger.debug('No kamstrup request magic received, got: {0)'.format(data[0].encode('hex-codec')))
            else:
                self.out_parsing = True
                # TODO: alot of stuff here
