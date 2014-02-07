# Copyright (C) 2014 Johnny Vestergaard <jkv@unixcluster.dk>
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

import gevent
import inspect


class Databus(object):
    def __init__(self):
        self._data = {}
        self._observer_map = {}

    # the idea here is that we can store both values and functions in the key value store
    # functions could be used if a profile wants to simulate a sensor, or the function
    # could interface with a real sensor
    def get_value(self, key):
        assert(key in self._data)
        item = self._data[key]
        # if the item is a function return the result of the function
        if hasattr(item, '__call__'):
            # need MROW lock on this
            return item()
        else:
            return item

    def set_value(self, key, value):
        self._data[key] = value
        # notify observers
        if key in self._observer_map:
            gevent.spawn(self.notify_observers, key)

    def notify_observers(self, key):
        for cb in self._observer_map:
            cb(key)

    def observe_value(self, key, callback):
        assert(hasattr(callback, '__call__'))
        assert(len(inspect.getargspec(callback)[0]))
        if key not in self._observer_map:
            self._observer_map = []
        self._observer_map[key].append(callback)

