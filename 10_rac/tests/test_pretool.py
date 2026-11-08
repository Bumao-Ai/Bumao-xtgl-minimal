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

"""PreToolUse adapter: deny dangerous/unknown, allow read, escape token one-time."""
import json
import os
import subprocess
import sys

import harness  # noqa: F401
import rules_db as dbm
import output_guard as og
from pretool.core import decide
from pretool import escape

og.AUDIT_PATH = os.path.join(dbm.ROOT, "tests", "_tmp_pt_guard.txt")
escape.VAULT = os.path.join(dbm.ROOT, "tests", "_tmp_escape_tokens.json")
escape.AUDIT = os.path.join(dbm.ROOT, "tests", "_tmp_escape_audit.txt")
for p in (escape.VAULT, escape.AUDIT):
    if os.path.exists(p):
        os.remove(p)


def main():
    r = harness.Runner("PreToolUse adapter")

    r.case("dangerous bash denied", lambda: (not decide("Bash", {"command": "rm -rf /tmp/x"})["allow"], "deny"))
    r.case("shutdown bash denied", lambda: (not decide("Bash", {"command": "shutdown /s"})["allow"], "deny"))
    r.case("unknown tool denied", lambda: (not decide("LaserZap", {})["allow"], "default deny"))
    r.case("read tool allowed", lambda: (decide("Read", {"file_path": "a.py"})["allow"], "allow"))
    r.case("benign bash allowed", lambda: (decide("Bash", {"command": "python --version"})["allow"], "allow"))
    r.case("benign write allowed", lambda: (decide("Write", {"file_path": "a.txt", "content": "hello"})["allow"], "allow"))

    def escape_once():
        tok = escape.issue_token("user authorized one cleanup", ttl_seconds=600)
        first = decide("Bash", {"command": "rm -rf build/"}, escape_token=tok)
        second = decide("Bash", {"command": "rm -rf build/"}, escape_token=tok)
        return (first["allow"] and not second["allow"],
                "first=%s second=%s (consumed)" % (first["allow"], second["allow"]))

    r.case("escape token honors once then consumed", escape_once)

    def empty_reason_refused():
        try:
            escape.issue_token("")
        except ValueError:
            return (True, "empty reason refused")
        return (False, "issued a token with no reason")

    r.case("empty reason refused", empty_reason_refused)

    def stdio_end_to_end():
        adapter = os.path.join(dbm.ROOT, "pretool", "stdio_adapter.py")
        # dangerous bash -> exit 3, decision deny
        p = subprocess.run([sys.executable, adapter, "--input-json",
                            json.dumps({"command": "format C:"})],
                           input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "format C:"}}),
                           capture_output=True, text=True)
        denied = p.returncode == 3 and json.loads(p.stdout)["decision"] == "deny"
        # read -> exit 0, allow
        p2 = subprocess.run([sys.executable, adapter],
                            input=json.dumps({"tool_name": "Read", "tool_input": {"file_path": "x"}}),
                            capture_output=True, text=True)
        allowed = p2.returncode == 0 and json.loads(p2.stdout)["allow"] is True
        return (denied and allowed, "deny_exit=%d allow_exit=%d" % (p.returncode, p2.returncode))

    r.case("stdio end-to-end deny/allow", stdio_end_to_end)

    n, npass, nf = r.counts()
    print("\n%d cases / %d pass / %d fail" % (n, npass, nf))
    sys.exit(1 if nf else 0)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
