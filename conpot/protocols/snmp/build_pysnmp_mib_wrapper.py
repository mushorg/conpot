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

from gevent import subprocess
import logging
import os
import re


logger = logging.getLogger(__name__)

BUILD_SCRIPT = 'build-pysnmp-mib'

# dict of lists, where the list contain the dependency names for the given dict key
mib_dependency_map = {}
compiled_mibs = []
# key = mib name, value = full path to the file
file_map = {}


def mib2pysnmp(mib_file):
    """
    Wraps the 'build-pysnmp-mib' script.

    :param mib_file: Path to the MIB file.
    :return: A string representation of the compiled MIB file (string).
    """
    import os.path
    from pysmi.reader import FileReader
    from pysmi.searcher import PyFileSearcher, PyPackageSearcher, StubSearcher
    from pysmi.writer import PyFileWriter
    from pysmi.parser import SmiStarParser
    from pysmi.codegen import PySnmpCodeGen
    from pysmi.compiler import MibCompiler

    # Initialize compiler infrastructure
    mibCompiler = MibCompiler(SmiStarParser(),
                              PySnmpCodeGen(),
                              PyFileWriter('.pysnmp-mibs'))

    # search for source MIBs here
    mibCompiler.addSources(FileReader('/usr/share/snmp/mibs'))
    path_chunks = os.path.realpath(mib_file).split('/')[:-1]  # all but last item
    mib_file_dir = '/'.join(path_chunks)  # rebuild path
    mibCompiler.addSources(FileReader(mib_file_dir))

    # check compiled MIBs in our own productions
    mibCompiler.addSearchers(PyFileSearcher('.pysnmp-mibs'))
    # ...and at default PySNMP MIBs packages
    mibCompiler.addSearchers(*[PyPackageSearcher(x) for x in PySnmpCodeGen.defaultMibPackages])

    # never recompile MIBs with MACROs
    mibCompiler.addSearchers(StubSearcher(*PySnmpCodeGen.baseMibs))

    # run [possibly recursive] MIB compilation
    logger.debug('Compiling mib file: %s', mib_file)
    results = mibCompiler.compile('IF-MIB', 'IP-MIB')

    mibstr = ', '.join(['%s:%s' % (x, results[x]) for x in results])
    logger.debug('Successfully compiled MIB file: %s', mib_file)
    return mibstr

def _get_files(raw_mibs_dir, recursive):
    for dir_path, dirs, files in os.walk(raw_mibs_dir, followlinks=True):
        for file_name in files:
            yield os.path.join(dir_path, file_name)
        if not recursive:
            break


def generate_dependencies(data, mib_name):
    """
    Parses a MIB for dependencies and populates an internal dependency map.
    :param data: A string representing an entire MIB file (string).
    :param mib_name: Name of the MIB (string).
    """
    if mib_name not in mib_dependency_map:
        mib_dependency_map[mib_name] = []
    imports_section_search = re.search('IMPORTS(?P<imports_section>.*?);', data, re.DOTALL)
    if imports_section_search:
        imports_section = imports_section_search.group('imports_section')
        for dependency in re.finditer('FROM (?P<mib_name>[\w-]+)', imports_section):
            dependency_name = dependency.group('mib_name')
            if dependency_name not in mib_dependency_map:
                mib_dependency_map[dependency_name] = []
            mib_dependency_map[mib_name].append(dependency_name)


def find_mibs(raw_mibs_dirs, recursive=True):
    """
    Scans for MIB files and populates an internal MIB->path mapping.
    :param raw_mibs_dirs: Directories to search for MIB files (list of strings).
    :param recursive:  If True raw_mibs_dirs will be scanned recursively.
    :return: A list of found MIB names (list of strings).
    """
    files_scanned = 0
    for raw_mibs_dir in raw_mibs_dirs:
        for _file in _get_files(raw_mibs_dir, recursive):
            files_scanned += 1
            # making sure we don't start parsing some epic file
            if os.path.getsize(_file) > '1048576':
                continue
            data = open(_file).read()
            # 2048 - just like a rock star.
            mib_search = re.search('(?P<mib_name>[\w-]+) DEFINITIONS ::= BEGIN', data[0:2048], re.IGNORECASE)
            if mib_search:
                mib_name = mib_search.group('mib_name')
                file_map[mib_name] = _file
                generate_dependencies(data, mib_name)
    logging.debug('Done scanning for mib files, recursive scan was initiated from {0} directories and found {1} '
                  'MIB files of {2} scanned files.'
                  .format(len(raw_mibs_dirs), len(file_map), files_scanned))
    return file_map.keys()


def compile_mib(mib_name, output_dir):
    """
    Compiles the given mib_name if it is found in the internal MIB file map. If the MIB depends on other MIBs,
    these will get compiled automatically.
    :param mib_name: Name of mib to compile (string).
    :param output_dir: Output directory (string).
    """
    # resolve dependencies recursively
    for dependency in mib_dependency_map[mib_name]:
        if dependency not in compiled_mibs and dependency in file_map:
            compile_mib(dependency, output_dir)
    _compile_mib(mib_name, output_dir)


def _compile_mib(mib_name, output_dir):
    pysnmp_str_obj = mib2pysnmp(file_map[mib_name])
    output_filename = os.path.basename(os.path.splitext(mib_name)[0]) + '.py'
    with open(os.path.join(output_dir, output_filename), 'w') as output:
        output.write(pysnmp_str_obj)
        compiled_mibs.append(mib_name)
