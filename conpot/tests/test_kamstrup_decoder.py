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

import unittest

from conpot.protocols.kamstrup.meter_protocol.decoder_382 import Decoder382


class TestKamstrupDecoder(unittest.TestCase):
    # TODO: Rename functions when i figure out the actual meaning of the requests / responses
    def test_request_one(self):
        request = [chr(0x80), chr(0x3f), chr(0x10), chr(0x01), chr(0x04), chr(0x1e), chr(0x7a), chr(0xbb), chr(0x0d)]
        decoder = Decoder382()
        result = decoder.decode_in(request)
        self.assertEqual(result, 'Request for 1 register(s): 1054 (Voltage p1) [0x3f]')

    def test_invalid_crc(self):
        invalid_sequences = [
            [chr(0x80), chr(0x3f), chr(0x10), chr(0x02), chr(0x00), chr(0x01), chr(0x55), chr(0xa1), chr(0x0d)],
            [chr(0x80), chr(0x3f), chr(0x10), chr(0x01), chr(0x00), chr(0x02), chr(0x65), chr(0xcf), chr(0x0d)]]

        for seq in invalid_sequences:
            decoder = Decoder382()
            result = decoder.decode_in(seq)
            self.assertEqual(result, 'Request discarded due to invalid CRC.',
                             'Invalid CRC {0} tested valid'.format(seq))

            # def test_request_two(self):
            #     request = "803f1001000265c20d".encode('hex-codec')
            #     decoder = Decoder()
            #     result = decoder.decode_in(request)
            #
            # def test_response_one(self):
            #     response = "403f1000010204000000008be1900d".encode('hex-codec')
            #     decoder = Decoder()
            #     result = decoder.decode_in(response)
            #
            # def test_response_two(self):
            #     response = "403f10000202040000000000091bf90d".encode('hex-codec')
            #     decoder = Decoder()
            #     result = decoder.decode_in(response)