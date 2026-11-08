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

"""output_guard.py -- L3 high-risk intent review (stdlib only).

Reviews a model/tool payload for high-risk intents. On an un-authorized hit it
BLOCKS. `inspect()` returns a verdict dict (advisory); `enforce()` raises
GuardBlocked when the payload is not allowed (hard stop).

Design: fail-safe -- prefer a false positive (a human confirms) over a miss.
The reviewer only classifies; it never executes anything.

Patterns are deliberately narrowed so ambiguous verbs (clean/format/restart)
only count when they sit in command position (line start, or after ; & |) or
carry a conclusive argument (format D:, rm -rf). This avoids false-firing on
benign text like "npm run clean" or documentation that merely mentions restart.
"""
import io
import os
import re
import time

import rules_db as dbm

AUDIT_PATH = os.path.join(dbm.LOGS_DIR, "output_guard_audit.txt")

# (category, compiled regex, human-readable advice)
RULES = [
    ("shutdown", re.compile(
        r"(?im)\b(shutdown|reboot|logoff|hibernate)\b"
        r"|Restart-Computer|Stop-Computer"),
     "Shutdown/reboot/logoff requires explicit per-turn authorization"),
    ("disk_destructive", re.compile(
        r"(?im)(?:^|[;&|]\s*)(?:format|diskpart|chkdsk)\b"
        r"|\bformat\s+[a-z]:|convert\s+[a-z]:\s*/fs"
        r"|delete\s+partition|Clear-Disk|Format-Volume"
        r"|\bclean\s+(?:all|disk)\b"),
     "Disk-level writes (format/diskpart/clean all) are irreversible; show a rollback path first"),
    ("recursive_delete", re.compile(
        r"(?im)\brm\s+-[rf]{1,2}\b|\bdel\s+/[fsq]\b"
        r"|\bRemove-Item\b[^\n]*-Recurse|\brmdir\s+/s\b|\brd\s+/s\b"),
     "Deletion/recursive removal may be unrecoverable; confirm the target is in scope and authorized"),
    ("registry", re.compile(
        r"(?i)\breg\s+(add|delete|import)\b"),
     "Irreversible registry modification requires explicit authorization"),
    ("batch_overwrite", re.compile(
        r"(?i)\b(ren|rename)\b.*[*?]"),
     "Bulk rename / backup-less overwrite cannot be undone; confirm first"),
    ("download_exec", re.compile(
        r"(?i)\b(iex|invoke-expression)\b"
        r"|curl\b.*\|\s*(sh|bash)|wget\b.*\|\s*(sh|bash)"),
     "Download-and-execute is injection-prone; review the source first"),
]


def inspect(text, authorized=()):
    """Return {'allow':bool,'hits':[...],'advice':str}. authorized: set of approved categories."""
    hits = []
    for category, pat, advice in RULES:
        m = pat.search(text or "")
        if m:
            hits.append({"category": category, "matched": m.group(0)[:30],
                         "advice": advice, "authorized": category in authorized})
    blocked = [h for h in hits if not h["authorized"]]
    return {
        "allow": not blocked,
        "hits": hits,
        "advice": (" ; ".join(sorted({h["advice"] for h in blocked}))
                   if blocked else "no high-risk intent detected"),
    }


def audit_log(result, source="guard"):
    line = "%s | source=%s | allow=%s | %s" % (
        time.strftime("%Y-%m-%d %H:%M:%S"), source, result["allow"],
        ",".join("%s%s" % (h["category"], "(authorized)" if h["authorized"] else "")
                 for h in result["hits"]) or "no-hit")
    os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True)
    with io.open(AUDIT_PATH, "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")
    return line


def guard(text, authorized=(), source="guard", log=True):
    result = inspect(text, authorized)
    if log:
        result["audit"] = audit_log(result, source)
    return result


class GuardBlocked(Exception):
    """Hard block: raised by enforce() so a write/exec path cannot proceed."""

    def __init__(self, result):
        self.result = result
        super().__init__("High-risk payload hard-blocked by L3: %s" % result.get("advice", ""))


def enforce(text, authorized=(), source="guard", log=True):
    result = guard(text, authorized=authorized, source=source, log=log)
    if not result["allow"]:
        raise GuardBlocked(result)
    return result
