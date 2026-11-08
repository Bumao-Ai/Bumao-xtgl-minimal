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

"""L4 capability whitelist: unknown denied, tiers honored, exec payload passes L3."""
import os
import sys

import harness  # noqa: F401
import rules_db as dbm
import capability as cap
import output_guard as og

og.AUDIT_PATH = os.path.join(dbm.ROOT, "tests", "_tmp_cap_audit.txt")
cap.AUDIT_PATH = og.AUDIT_PATH


def main():
    r = harness.Runner("L4 capability whitelist")

    r.case("read capability tier", lambda: (cap.tier_of("search") == "read", "search=read"))
    r.case("write capability tier", lambda: (cap.tier_of("file_write") == "write", "file_write=write"))
    r.case("exec capability tier", lambda: (cap.tier_of("run_command") == "exec", "run_command=exec"))

    def unknown_denied():
        try:
            cap.tier_of("launch_missiles")
        except cap.CapDenied:
            return (True, "CapDenied raised")
        return (False, "unknown capability was allowed")

    r.case("unknown capability denied", unknown_denied)

    r.case("read check allowed", lambda: (cap.check("search", payload="") == ("read", None), "read -> no L3"))

    def exec_blocked():
        try:
            cap.check("run_command", payload="rm -rf /important")
        except cap.CapDenied:
            return (True, "denied")
        except og.GuardBlocked:
            return (True, "L3 blocked")
        return (False, "dangerous exec was allowed")

    r.case("exec dangerous payload blocked", exec_blocked)
    r.case("exec benign payload allowed", lambda: (cap.check("run_command", payload="python --version")[0] == "exec", "benign exec ok"))

    n, npass, nf = r.counts()
    print("\n%d cases / %d pass / %d fail" % (n, npass, nf))
    sys.exit(1 if nf else 0)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
