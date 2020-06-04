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
import inspect

# this is needed because we use it in the xml.
import random

import gevent
import gevent.event
from lxml import etree


logger = logging.getLogger(__name__)


class Databus(object):
    def __init__(self):
        self._data = {}
        self._observer_map = {}
        self.initialized = gevent.event.Event()

    # the idea here is that we can store both values and functions in the key value store
    # functions could be used if a profile wants to simulate a sensor, or the function
    # could interface with a real sensor
    def get_value(self, key):
        logger.debug("DataBus: Get value from key: [%s]", key)
        assert key in self._data
        item = self._data[key]
        if getattr(item, "get_value", None):
            # this could potentially generate a context switch, but as long the called method
            # does not "callback" the databus we should be fine
            value = item.get_value()
            logger.debug("(K, V): (%s, %s)" % (key, value))
            return value
        elif hasattr(item, "__call__"):
            return item()
        else:
            # guaranteed to not generate context switch
            logger.debug("(K, V): (%s, %s)" % (key, item))
            return item

    def set_value(self, key, value):
        logger.debug("DataBus: Storing key: [%s] value: [%s]", key, value)
        self._data[key] = value
        # notify observers
        if key in self._observer_map:
            gevent.spawn(self.notify_observers, key)

    def notify_observers(self, key):
        for cb in self._observer_map[key]:
            cb(key)

    def observe_value(self, key, callback):
        assert hasattr(callback, "__call__")
        assert len(
            inspect.getfullargspec(callback)[0]
        )  # depreciated in py3.5, un-depreciated in py3.6
        if key not in self._observer_map:
            self._observer_map[key] = []
        self._observer_map[key].append(callback)

    def initialize(self, config_file):
        self.reset()
        assert self.initialized.isSet() is False
        logger.debug("Initializing databus using %s.", config_file)
        dom = etree.parse(config_file)
        entries = dom.xpath("//core/databus/key_value_mappings/*")
        for entry in entries:
            key = entry.attrib["name"]
            value = entry.xpath("./value/text()")[0].strip()
            value_type = str(entry.xpath("./value/@type")[0])
            assert key not in self._data
            logging.debug("Initializing %s with %s as a %s.", key, value, value_type)
            if value_type == "value":
                self.set_value(key, eval(value))
            elif value_type == "function":
                namespace, _classname = value.rsplit(".", 1)
                params = entry.xpath("./value/@param")
                module = __import__(namespace, fromlist=[_classname])
                _class = getattr(module, _classname)
                if len(params) > 0:
                    # eval param to list
                    params = eval(params[0])
                    self.set_value(key, _class(*(tuple(params))))
                else:
                    self.set_value(key, _class())
            else:
                raise Exception("Unknown value type: {0}".format(value_type))
        self.initialized.set()

    def reset(self):
        logger.debug("Resetting databus.")

        # if the class has a stop method call it.
        for value in list(self._data.values()):
            if getattr(value, "stop", None):
                value.stop()

        self._data.clear()
        self._observer_map.clear()
        self.initialized.clear()
