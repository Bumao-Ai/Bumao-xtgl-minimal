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

"""stdio_adapter.py -- host integration surface (stdin/stdout JSON).

A host pipes a JSON request on stdin:
    {"tool_name": "Bash",
     "tool_input": {"command": "..."},
     "authorized": [],
     "escape_token": ""}
and receives a decision on stdout. Exit code 0 = allow, 3 = deny.

Two protocols:
  generic (default): {"decision":"allow|deny","allow":bool,"reason":...}
  claude (--proto claude): hookSpecificOutput permissionDecision shape.
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from core import decide  # noqa: E402


def _read_stdin_json():
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {"tool_name": "Bash", "tool_input": {"command": raw}}


def to_host_decision(dec, proto="generic"):
    if proto == "claude":
        if dec["allow"]:
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                           "permissionDecision": "allow"}}
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                       "permissionDecision": "deny",
                                       "permissionDecisionReason": dec["reason"]}}
    return {"decision": dec["decision"], "allow": dec["allow"],
            "tier": dec["tier"], "reason": dec["reason"]}


def main(argv=None):
    p = argparse.ArgumentParser(description="PreToolUse guard adapter")
    p.add_argument("--proto", default="generic", choices=["generic", "claude"])
    p.add_argument("--tool-name", default=None)
    p.add_argument("--input-json", default=None,
                   help="give tool_input JSON directly instead of stdin (local testing)")
    args = p.parse_args(argv)

    payload = _read_stdin_json()
    tool_name = args.tool_name or payload.get("tool_name", "")
    tool_input = payload.get("tool_input")
    if tool_input is None and args.input_json:
        tool_input = json.loads(args.input_json)
    authorized = payload.get("authorized", []) or []
    escape_token = payload.get("escape_token", "") or ""

    dec = decide(tool_name, tool_input, authorized=authorized,
                 escape_token=escape_token, source="pretool-hook")
    out = to_host_decision(dec, args.proto)
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    return 0 if dec["allow"] else 3


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
