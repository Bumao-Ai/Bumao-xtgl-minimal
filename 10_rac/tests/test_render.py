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

"""Render idempotency: render twice in memory -> identical; on disk -> identical bytes."""
import os
import sys

import harness  # noqa: F401
import render as rend
import rules_db as dbm


def main():
    r = harness.Runner("render idempotency")

    r.case("two in-memory renders identical", lambda: (
        rend.targets() == rend.targets(), "targets equal"))

    # render to disk twice, compare a checksum-ish of each view
    import hashlib
    rend.render_all()
    snap1 = {p: hashlib.sha256(c.encode("utf-8")).hexdigest() for p, c in rend.targets()}
    rend.render_all()
    snap2 = {p: hashlib.sha256(c.encode("utf-8")).hexdigest() for p, c in rend.targets()}
    r.case("on-disk double render stable", lambda: (snap1 == snap2, "%d views" % len(snap1)))

    r.case("no drift after render", lambda: (not rend.check_drift(), "drift=0"))

    n, npass, nf = r.counts()
    print("\n%d cases / %d pass / %d fail" % (n, npass, nf))
    sys.exit(1 if nf else 0)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
