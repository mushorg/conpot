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

"""Awlsim AWL backend (not wired yet).

Intended process-image mapping when the hardware-module bridge lands:

* Modbus coils (writable commands) -> S7 I (or M used as commands)
* Engine-written discrete inputs   -> S7 Q (status bits)
* Holding / analog registers       -> MW / PIW

Awlsim's interpreter must run in a native thread so a scan cannot block
the asyncio event loop. Do not import this module from required Conpot
dependencies.
"""

from conpot.emulators.plc.engine import ProcessImage


class AwlsimEngine:
    def __init__(self):
        try:
            import awlsim  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "AwlsimEngine requires the awlsim package. Install it "
                "separately; it is not a Conpot runtime dependency."
            ) from exc
        raise NotImplementedError(
            "Awlsim OB1 execution is not wired yet. Use engine 'native'."
        )

    def scan(self, image: ProcessImage) -> None:
        raise NotImplementedError(
            "Awlsim OB1 execution is not wired yet. Use engine 'native'."
        )
