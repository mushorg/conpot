# Copyright (C) 2013 Johnny Vestergaard <jkv@unixcluster.dk>
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

import subprocess
import logging
import sys


logger = logging.getLogger(__name__)

BUILD_SCRIPT = 'build-pysnmp-mib'


def mib2pysnmp(mib_file):
    proc = subprocess.Popen([BUILD_SCRIPT, mib_file], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    return_code = proc.wait()
    stderr = '\n'.join(proc.stderr.readlines())
    #string representation of the PySNMP MIB object
    stdout = '\n'.join(proc.stdout.readlines())

    if return_code != 0:
        logger.critical('Error while parsing processing MIB file using {0}. STDERR: {1}, STDOUT: {2}'
                        .format(BUILD_SCRIPT, stderr, stdout))
        raise Exception(stderr)
    else:
        logger.debug('Successfully compiled MIB file: {0}. STDOUT: {1}, STDERR: {2} '
                     .format(mib_file, stdout, stderr))
        return stdout

if __name__ == '__main__':
    print mib2pysnmp(sys.argv[1])
