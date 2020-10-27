# Copyright (C) 2017  Patrick Reichenberger (University of Passau) <patrick.reichenberger@t-online.de>
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


class InvalidFieldValueException(ValueError):

    """This error is raised if a field value is not allowed"""

    def __init__(self, *args):
        self.args = args


class FrameError(Exception):

    """This error is raised if the IEC104 frame is wrong or ain't a IEC104 packet at all"""

    def __init__(self, *args):
        self.args = args


class Timeout_t1(BaseException):
    """Base class for exceptions in this module."""


class Timeout_t1_2nd(BaseException):
    """Base class for exceptions in this module."""


class Timeout_t3(BaseException):
    """Base class for exceptions in this module."""
