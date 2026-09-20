# Copyright (C) 2014 Johnny Vestergaard <jkv@unixcluster.dk>
# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

import asyncio
import logging
import inspect
import threading

# this is needed because we use it in template value expressions.
import random  # noqa: F401

logger = logging.getLogger(__name__)


class Databus(object):
    def __init__(self):
        self._data = {}
        self._observer_map = {}
        self.initialized = threading.Event()

    def get_value(self, key):
        logger.debug("DataBus: Get value from key: [%s]", key)
        assert key in self._data
        item = self._data[key]
        if getattr(item, "get_value", None):
            value = item.get_value()
            logger.debug("(K, V): (%s, %s)" % (key, value))
            return value
        elif hasattr(item, "__call__"):
            return item()
        else:
            logger.debug("(K, V): (%s, %s)" % (key, item))
            return item

    def set_value(self, key, value):
        logger.debug("DataBus: Storing key: [%s] value: [%s]", key, value)
        self._data[key] = value
        if key in self._observer_map:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._notify_observers_async(key))
            except RuntimeError:
                threading.Thread(
                    target=self.notify_observers, args=(key,), daemon=True
                ).start()

    async def _notify_observers_async(self, key):
        for cb in list(self._observer_map.get(key, [])):
            result = cb(key)
            if asyncio.iscoroutine(result):
                await result

    def notify_observers(self, key):
        for cb in list(self._observer_map.get(key, [])):
            cb(key)

    def observe_value(self, key, callback):
        assert hasattr(callback, "__call__")
        assert len(inspect.getfullargspec(callback)[0])
        if key not in self._observer_map:
            self._observer_map[key] = []
        self._observer_map[key].append(callback)

    def initialize(self, template):
        """Initialize from a TOML template dict."""
        self.reset()
        assert self.initialized.is_set() is False
        self._initialize_from_toml(template)
        self.initialized.set()

    def _initialize_from_toml(self, template):
        logger.debug("Initializing databus from TOML template")
        for key, value in template["core"]["databus"]["key_value_mappings"].items():
            assert key not in self._data
            logger.debug("Initializing %s with %s", key, value)
            if isinstance(value, dict):
                if "function" in value:
                    namespace, _classname = value["function"].rsplit(".", 1)
                    module = __import__(namespace, fromlist=[_classname])
                    _class = getattr(module, _classname)
                    params = value.get("params")
                    if params is not None:
                        self.set_value(key, _class(*(tuple(params))))
                    else:
                        self.set_value(key, _class())
                elif "value" in value:
                    self.set_value(key, eval(value["value"]))
                else:
                    raise Exception(
                        "Unknown databus mapping for {0}: {1}".format(key, value)
                    )
            else:
                self.set_value(key, value)

    def reset(self):
        logger.debug("Resetting databus.")
        for value in list(self._data.values()):
            if getattr(value, "stop", None):
                value.stop()
        self._data.clear()
        self._observer_map.clear()
        self.initialized.clear()
