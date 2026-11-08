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

"""capability.py -- L4 capability whitelist (default deny, explicit allow).

A request reaches a tool only if the capability name is registered here. Tiers:
  read : read-only, does not go through L3
  write: writes, payload goes through L3 output guard
  exec : execution, payload MUST go through L3 output guard

Honest boundary (stated, not hidden): this gate governs THIS program's own
runtime entry points. If a host grants the agent a bare shell outside this
process, this code cannot revoke it. That is a host-level permission; we record
it truthfully rather than claiming "everything is locked down".
"""
import io
import os
import time

import rules_db as dbm

AUDIT_PATH = os.path.join(dbm.LOGS_DIR, "capability_audit.txt")

TIER_READ, TIER_WRITE, TIER_EXEC = "read", "write", "exec"

# capability name -> (tier, one-line purpose). Add new tools here explicitly.
# Not registered == default deny.
POLICY = {
    "preflight":   (TIER_READ, "run whoami + check before starting work"),
    "check_run":   (TIER_READ, "run the strict gate suite"),
    "render_run":  (TIER_WRITE, "render SSOT -> views, then force a check"),
    "show_clause": (TIER_READ, "read a single clause"),
    "search":      (TIER_READ, "search/read within the project (no path traversal)"),
    "file_write":  (TIER_WRITE, "controlled file write: payload passes L3, fully audited"),
    "action_review": (TIER_EXEC, "review a proposed action; only proceeds if L3 allows it"),
    "run_command": (TIER_EXEC, "run a fixed, non-arbitrary command; command string passes L3"),
}


class CapDenied(ValueError):
    """Default deny: capability not in the whitelist, or wrong-tier use."""


def list_policy():
    return [{"name": n, "tier": t, "purpose": p}
            for n, (t, p) in sorted(POLICY.items())]


def tier_of(name):
    if name not in POLICY:
        raise CapDenied("default deny: capability %r is not whitelisted" % name)
    return POLICY[name][0]


def audit(decision, name, detail=""):
    line = "%s | %s | %s | %s" % (
        time.strftime("%Y-%m-%d %H:%M:%S"), decision, name, detail[:120])
    os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True)
    with io.open(AUDIT_PATH, "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")
    return line


def check(name, payload="", authorized=(), source="gateway"):
    """Gate entry. Returns (tier, l3_result_or_None). Raises on deny/block."""
    try:
        tier = tier_of(name)
    except CapDenied as e:
        audit("DENY", name, "not registered")
        raise
    g3 = None
    if tier in (TIER_WRITE, TIER_EXEC):
        import output_guard as og
        try:
            g3 = og.enforce(payload, authorized=tuple(authorized),
                            source="%s:%s" % (source, name))
        except og.GuardBlocked as gb:
            audit("BLOCK", name, "L3: %s" % gb.result.get("advice", "")[:80])
            raise
    audit("ALLOW", name, "tier=%s" % tier)
    return tier, g3
