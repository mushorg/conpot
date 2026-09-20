# Copyright (C) 2026 MushMush Foundation
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
import threading
import time

import conpot.core as conpot_core
from conpot.emulators.plc.engine import ProcessImage
from conpot.emulators.plc.native import NativeLogicEngine

logger = logging.getLogger(__name__)


def _make_engine(engine_name):
    if engine_name == "native":
        return NativeLogicEngine()
    if engine_name == "awlsim":
        from conpot.emulators.plc.awlsim_engine import AwlsimEngine

        return AwlsimEngine()
    raise ValueError("Unknown PLC engine: {!r}".format(engine_name))


class PlcScanCycle:
    """Cyclic PLC scan over databus lists that Modbus already serves.

    Constructor args match ``{ function = "..." [, params = [...]] }`` in template.toml.
    """

    def __init__(
        self,
        scan_ms=50,
        engine_name="native",
        coils_key="memoryModbusSlave1BlockA",
        discrete_key="memoryModbusSlave1BlockB",
        holding_key="memoryModbusSlave1BlockD",
        analog_key="memoryModbusSlave1BlockC",
    ):
        self.scan_ms = int(scan_ms)
        self.engine_name = engine_name
        self.coils_key = coils_key
        self.discrete_key = discrete_key
        self.holding_key = holding_key
        self.analog_key = analog_key
        self._enabled = True
        self.stopped = threading.Event()
        threading.Thread(target=self.initialize, daemon=True).start()

    def stop(self):
        self._enabled = False
        self.stopped.wait(timeout=2)

    def initialize(self):
        databus = conpot_core.get_databus()
        databus.initialized.wait()
        if not self._enabled:
            self.stopped.set()
            return
        try:
            engine = _make_engine(self.engine_name)
            image = ProcessImage(
                coils=databus.get_value(self.coils_key),
                discrete=databus.get_value(self.discrete_key),
                holding=databus.get_value(self.holding_key),
                analog=databus.get_value(self.analog_key),
            )
        except Exception:
            logger.exception("PLC scan cycle failed to start")
            self.stopped.set()
            raise

        scan_s = max(self.scan_ms, 1) / 1000.0
        while self._enabled:
            try:
                engine.scan(image)
            except Exception:
                logger.exception("PLC scan failed")
            time.sleep(scan_s)
        self.stopped.set()
