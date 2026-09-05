# Copyright (C) 2026  Lukas Rist <glaslos@gmail.com>
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
import os
import tempfile

from conpot.utils.logging import setup_logging


def test_setup_logging_info_level():
    root = logging.getLogger()
    # Clear handlers left by other tests
    root.handlers.clear()

    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as fh:
        log_path = fh.name

    try:
        setup_logging(log_path, verbose=False)
        assert root.level == logging.INFO
        assert len(root.handlers) == 2
        assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)
        assert any(isinstance(h, logging.FileHandler) for h in root.handlers)
        for handler in root.handlers:
            assert handler.level == logging.INFO
    finally:
        root.handlers.clear()
        os.unlink(log_path)


def test_setup_logging_verbose_debug():
    root = logging.getLogger()
    root.handlers.clear()

    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as fh:
        log_path = fh.name

    try:
        setup_logging(log_path, verbose=True)
        assert root.level == logging.DEBUG
        for handler in root.handlers:
            assert handler.level == logging.DEBUG
    finally:
        root.handlers.clear()
        os.unlink(log_path)
