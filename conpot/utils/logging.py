# Copyright (C) 2013 MushMush Foundation
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

"""Process logging setup (console + file). Not attack-event sinks."""

import logging


def _get_log_level(verbose):
    if verbose:
        return logging.DEBUG
    return logging.INFO


def setup_console_logging(verbose, reset=False):
    log_level = _get_log_level(verbose)

    log_format = logging.Formatter("%(asctime)-15s %(message)s")
    root_logger = logging.getLogger()
    if reset:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            handler.close()

    console_log = logging.StreamHandler()
    console_log.setLevel(log_level)
    console_log.setFormatter(log_format)

    root_logger.setLevel(log_level)
    root_logger.addHandler(console_log)


def setup_file_logging(log_file, verbose):
    log_level = _get_log_level(verbose)
    log_format = logging.Formatter("%(asctime)-15s %(message)s")

    file_log = logging.FileHandler(log_file)
    file_log.setFormatter(log_format)
    file_log.setLevel(log_level)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_log)


def setup_logging(log_file, verbose):
    setup_console_logging(verbose)
    setup_file_logging(log_file, verbose)
