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

from conpot.emulators.plc.engine import ProcessImage


class NativeLogicEngine:
    """Hardcoded start/stop plant used until an AWL backend is wired.

    Coil [0] is start, coil [1] is stop (stop wins). Discrete [0] is the
    running bit. Holding [0] increments while running (16-bit wrap).
    Analog [0] is a derived process value from that counter.
    """

    def __init__(self):
        self._running = False

    def scan(self, image: ProcessImage) -> None:
        if image.coils[1]:
            self._running = False
        elif image.coils[0]:
            self._running = True

        image.discrete[0] = 1 if self._running else 0
        if self._running:
            image.holding[0] = (int(image.holding[0]) + 1) & 0xFFFF
        image.analog[0] = (int(image.holding[0]) * 10) % 65536
