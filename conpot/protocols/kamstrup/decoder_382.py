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

import crc16


logger = logging.getLogger(__name__)


class Decoder(object):
    REQUEST_MAGIC = 0x80
    RESPONSE_MAGIC = 0x40
    EOT_MAGIC = 0x0d

    # Following constants has been taken from pykamstrup, thanks to PHK/Erik Jensen!
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
        31: 'MVA', 32: 'GVA', 33: 'V', 34: 'A', 35: 'kV', 36: 'kA', 37: 'C',
        38: 'K', 39: 'l', 40: 'm3', 41: 'l/h', 42: 'm3/h', 43: 'm3xC',
        44: 'ton', 45: 'ton/h', 46: 'h', 47: 'hh:mm:ss', 48: 'yy:mm:dd',
        49: 'yyyy:mm:dd', 50: 'mm:dd', 51: '', 52: 'bar', 53: 'RTC',
        54: 'ASCII', 55: 'm3 x 10', 56: 'ton x 10', 57: 'GJ x 10',
        58: 'minutes', 59: 'Bitfield', 60: 's', 61: 'ms', 62: 'days',
        63: 'RTC-Q', 64: 'Datetime'
    }

    ESCAPES = [0x06, 0x0d, 0x1b, 0x40, 0x80]

    KAMSTRUP_382_REGISTERS = {

        0x0001: "Energy in",
        0x0002: "Energy out",

        0x000d: "Energy in hi-res",
        0x000e: "Energy out hi-res",

        0x041e: "Voltage p1",
        0x041f: "Voltage p2",
        0x0420: "Voltage p3",

        0x0434: "Current p1",
        0x0435: "Current p2",
        0x0436: "Current p3",

        0x0438: "Power p1",
        0x0439: "Power p2",
        0x043a: "Power p3",
    }

    def __init__(self):
        self.in_data = []
        self.in_parsing = False
        self.out_data = []
        self.out_parsing = False
        self.command_map = {0x01: self._decode_cmd_get_type,
                            0x10: self._decode_cmd_get_register,
                            0x92: self._decode_cmd_login}

    def decode_in(self, data):
        for d in data:
            d = ord(d)
            if not self.in_parsing and d != Decoder.REQUEST_MAGIC:
                logger.debug('No kamstrup request magic received, got: {0}'.format(d.encode('hex-codec')))
            else:
                self.in_parsing = True
                if d is 0x0d:
                    if not self.valid_crc(self.in_data[1:]):
                        self.in_parsing = False
                        self.in_data = []
                        # TODO: Log discarded bytes?
                        return 'Request discarded due to invalid CRC.'
                    # now we expect (0x80, 0x3f, 0x10) =>
                    # (request magic, communication address, command byte)
                    comm_address = self.in_data[1]
                    if self.in_data[2] in self.command_map:
                        return self.command_map[self.in_data[2]]() + ' [{0}]'.format(hex(comm_address))
                    else:
                        return 'Expected request magic but got: {0}, ignoring request.' \
                            .format(self.in_data[2].encode('hex-codec'))
                else:
                    self.in_data.append(d)

    def _decode_cmd_get_register(self):
        assert (self.in_data[2] == 0x10)
        cmd = self.in_data[2]
        register_count = self.in_data[3]
        message = 'Request for {0} register(s): '.format(register_count)
        for count in range(register_count):
            register = self.in_data[4 + count] * 256 + self.in_data[5 + count]
            if register in Decoder.KAMSTRUP_382_REGISTERS:
                message += '{0} ({1})'.format(register, Decoder.KAMSTRUP_382_REGISTERS[register])
            else:
                message += 'Unknown ({1})'.format(register)
            if count + 1 < register_count:
                message += ', '
        self.in_data = []
        return message

    # meter type
    def _decode_cmd_get_type(self):
        assert (self.in_data[2] == 0x01)
        return 'Request for GetType'

    def _decode_cmd_login(self):
        assert (self.in_data[2] == 0x92)
        pin_code = self.in_data[3] * 256 + self.in_data[4]
        return 'Login command with pin_code: {0}'.format(pin_code)

    def decode_out(self, data):
        for d in data:
            d = ord(d)
            if not self.out_parsing and d != Decoder.RESPONSE_MAGIC:
                logger.debug('Expected response magic but got got: {0}'.format(d.encode('hex-codec')))
            else:
                self.out_parsing = True
                if d is 0x0d:
                    if not self.valid_crc(self.out_data[1:]):
                        self.out_parsing = False
                        # TODO: Log discarded bytes?
                        return 'Response discarded due to invalid CRC.'
                    return self._decode_req()
                else:
                    self.out_data.append(d)

    # supplied message should be stripped of leading and trailing magic
    def valid_crc(self, message):
        supplied_crc = message[-2] * 256 + message[-1]
        calculated_crc = crc16.crc16xmodem(''.join([chr(item) for item in message[:-2]]))
        return supplied_crc == calculated_crc

    def _decode_response(self):
        return 'Decoding of this response has not been implemented yet.'



