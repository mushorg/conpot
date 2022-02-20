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

from enum import Enum

REQUEST_MAGIC = 0x80
RESPONSE_MAGIC = 0x40
EOT_MAGIC = 0x0D
ESCAPE = 0x1B

# what is 0x06?
NEED_ESCAPE = [0x06, EOT_MAGIC, ESCAPE, RESPONSE_MAGIC, REQUEST_MAGIC]

UNITS = {
    0: "None",
    1: "Wh",
    2: "kWh",
    3: "MWh",
    4: "GWh",
    5: "j",
    6: "kj",
    7: "Mj",
    8: "Gj",
    9: "Cal",
    10: "kCal",
    11: "MCal",
    12: "GCal",
    13: "varh",
    14: "kvarh",
    15: "Mvarh",
    16: "Gvarh",
    17: "VAh",
    18: "kVAh",
    19: "MVAh",
    20: "GVAh",
    21: "W",
    22: "kW",
    23: "MW",
    24: "GW",
    25: "var",
    26: "kvar",
    27: "MVar",
    28: "Gvar",
    29: "VA",
    30: "kVA",
    31: "MVA",
    32: "GVA",
    33: "V",
    34: "A",
    35: "kV",
    36: "kA",
    37: "C",
    38: "K",
    39: "I",
    40: "m3",
    41: "I_h",
    42: "m3_h",
    43: "m3xC",
    44: "ton",
    45: "ton_h",
    46: "h",
    47: "clock",  # hh:mm:ss
    48: "date1",  # yy:mm:dd
    49: "date2",  # yyyy:mm:dd
    50: "date3",  # mm:dd
    51: "number",
    52: "bar",
    53: "RTC",
    54: "ASCII",
    55: "m3x10",
    56: "tonx10",
    57: "GJx10",
    58: "minutes",
    59: "Bitfield",
    60: "s",
    61: "ms",
    62: "days",
    63: "RTC_Q",
    64: "Datetime",
    65: "imp_L",
    66: "L_imp",
    67: "Hz",
    68: "Degree",
    69: "Percent",
    70: "USgal",
    71: "USgal_min",
    72: "KamDateTime",
    73: "IPv4Address",
    74: "IPv6Address",
}


class MeterTypes(Enum):
    Unknown = (0,)
    K382M = (1,)
    K162M = (2,)
    K351C = (3,)
    OMNIA = (4,)
    # where does 382J fit in? together with 382M?
