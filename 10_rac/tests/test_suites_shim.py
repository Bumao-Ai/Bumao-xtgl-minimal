# -*- coding: utf-8 -*-
# Copyright 2026 Bumao
#
# Licensed under the Apache License, Version 2.0.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""unittest-compatible shim for `python -m unittest discover tests`.

This edition's native suites use a tiny zero-dependency harness (harness.Runner) and
are meant to be executed directly (`python tests/test_xxx.py`). To also support
the standard `python -m unittest discover tests` entry point, this shim runs each
script-style suite as a subprocess and treats a zero exit code as a pass. The
native suites still report their own `N cases / N pass / 0 fail` summary; this
file only proves they all exit green under discovery.
"""
import os
import subprocess
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

_SUITES = [
    "test_output_guard.py",
    "test_capability.py",
    "test_pretool.py",
    "test_render.py",
    "test_reverse.py",
]


def _run_suite(name):
    p = subprocess.run([sys.executable, os.path.join("tests", name)],
                       cwd=_ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


class ScriptSuites(unittest.TestCase):
    def test_output_guard_suite(self):
        code, out = _run_suite("test_output_guard.py")
        self.assertEqual(0, code, out)

    def test_capability_suite(self):
        code, out = _run_suite("test_capability.py")
        self.assertEqual(0, code, out)

    def test_pretool_suite(self):
        code, out = _run_suite("test_pretool.py")
        self.assertEqual(0, code, out)

    def test_render_suite(self):
        code, out = _run_suite("test_render.py")
        self.assertEqual(0, code, out)

    def test_reverse_suite(self):
        code, out = _run_suite("test_reverse.py")
        self.assertEqual(0, code, out)


if __name__ == "__main__":
    unittest.main()
