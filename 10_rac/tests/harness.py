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

"""harness.py -- tiny zero-dependency test runner used by all tests/."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class Runner:
    def __init__(self, title):
        self.title = title
        self.n = self.np = self.nf = 0

    def case(self, name, fn):
        self.n += 1
        try:
            ok, note = fn()
        except Exception as e:
            ok, note = False, "raised %r" % e
        if ok:
            self.np += 1
            print("  PASS  %-40s %s" % (name, note))
        else:
            self.nf += 1
            print("  FAIL  %-40s %s" % (name, note))

    def counts(self):
        return self.n, self.np, self.nf
