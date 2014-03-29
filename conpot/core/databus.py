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

import logging
import json
import inspect
import random

import gevent
from lxml import etree


logger = logging.getLogger(__name__)


class Databus(object):
    def __init__(self):
        self._data = {}
        self._observer_map = {}

    # the idea here is that we can store both values and functions in the key value store
    # functions could be used if a profile wants to simulate a sensor, or the function
    # could interface with a real sensor
    def get_value(self, key):
        logger.debug('Get value from key: {0}'.format(key))
        assert (key in self._data)
        item = self._data[key]
        # if the item is a function return the result of the function
        if getattr(item, "get_value", None):
            # need MROW lock on this
            return item.get_value()
        else:
            return item

    def set_value(self, key, value):
        logger.debug('Settings [{0}] = {1}'.format(key, value))
        self._data[key] = value
        # notify observers
        if key in self._observer_map:
            gevent.spawn(self.notify_observers, key)

    def notify_observers(self, key):
        for cb in self._observer_map:
            cb(key)

    def observe_value(self, key, callback):
        assert (hasattr(callback, '__call__'))
        assert (len(inspect.getargspec(callback)[0]))
        if key not in self._observer_map:
            self._observer_map = []
        self._observer_map[key].append(callback)

    # What was this for?
    def _initialize_value(self):
        pass

    def initialize(self, config_file):
        self._reset()
        logger.debug('Initializing databus using {0}.'.format(config_file))
        dom = etree.parse(config_file)
        entries = dom.xpath('//conpot_template/core/datastore/key_value_mappings/*')
        for entry in entries:
            key = entry.attrib['name']
            value = entry.xpath('./value/text()')[0]
            value_type = str(entry.xpath('./value/@type')[0])
            assert (key not in self._data)
            logging.debug('Initializing {0} with {1} as a {2}.'.format(key, value, value_type))
            if value_type == 'value':
                self.set_value(key, eval(value))
            elif value_type == 'function':
                namespace, _classname = value.rsplit('.', 1)
                params = entry.xpath('./value/@param')
                module = __import__(namespace, fromlist=[_classname])
                _class = getattr(module, _classname)
                if len(params) > 0:
                    self.set_value(key, _class(*(tuple(params))))
                else:
                    self.set_value(key, _class())
            else:
                raise Exception('Unknown value type: {0}'.format(value_type))

    def get_shapshot(self):
        # takes a snapshot of the internal honeypot state and returns it as json.
        snapsnot = {}
        for key in self._data.keys():
            snapsnot[key] = self.get_value(key)
        return json.dumps(snapsnot)

    def _reset(self):
        logger.debug('Resetting databus.')
        self._data.clear()
        self._observer_map.clear()
