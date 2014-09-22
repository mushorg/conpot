# Copyright (C) 2014 Lukas Rist <glaslos@gmail.com>
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

    def __init__(self):
        self.in_data = []
        self.in_parsing = False
        self.in_data_escaped = False
        self.out_data = []
        self.out_parsing = False
        self.out_data_escaped = False

    def decode_in(self, data):
        for d in data:
            pass

    def decode_out(self, data):
        for d in data:
            pass