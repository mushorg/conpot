# Copyright (C) 2013  Lukas Rist <glaslos@gmail.com>
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

import os
import subprocess
import unittest


class TestMakeDocs(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_make_docs(self):
        cmd = "make -C docs/ html"
        project_root = os.path.join(os.path.dirname(__file__), "..", "..")

        process = subprocess.Popen(
            cmd.split(), cwd=project_root, stdout=subprocess.PIPE
        )
        output = process.communicate()[0].decode()

        self.assertIn("Build finished. The HTML pages are in build/html.", output)
