#!/usr/bin/env python3
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

"""
demo_break_and_fix.py - 30-second demonstration of Bumao Core.

Four beats, run in one command:
    1. green : run the check suite            -> ALL PASS
    2. red   : delete rule E-07 on purpose     -> FAIL, gates named
    3. fix   : restore the rule from backup   -> restored
    4. green : run the check suite again       -> ALL PASS

Usage:
    python demo_break_and_fix.py
"""
import os
import sys
import json
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
RULES = os.path.join(ROOT, "10_rac", "zhunze", "z01_example.json")
BACKUP = os.path.join(ROOT, "90_lishi", "demo_backup_z01.json")


def check():
    r = subprocess.run(
        [sys.executable, os.path.join("10_rac", "engine.py"), "check", "--strict"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return r.stdout + r.stderr, r.returncode


def banner(text):
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)


def main():
    banner("BEAT 1/4: clean run")
    out, rc = check()
    print(out.strip())
    if rc != 0:
        print("DEMO ABORTED: expected ALL PASS on a clean tree")
        return 1

    banner("BEAT 2/4: breaking on purpose - deleting rule E-07")
    with open(RULES, "r", encoding="utf-8") as f:
        original = f.read()
    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    with open(BACKUP, "w", encoding="utf-8") as f:
        f.write(original)
    rules = json.loads(original)
    rules = [r for r in rules if r["id"] != "E-07"]
    with open(RULES, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)
    out, rc = check()
    print(out.strip())
    failing = [l.split()[0] for l in out.splitlines()
               if l.startswith("G") and "  FAIL" in l]
    print(">>> RESULT: FAIL as expected. Red gates:", ", ".join(failing))
    if rc == 0:
        print("DEMO ABORTED: breaking the rule did NOT turn any gate red")
        with open(RULES, "w", encoding="utf-8", newline="\n") as f:
            f.write(original)
        return 1

    banner("BEAT 3/4: restoring E-07 from backup")
    with open(RULES, "w", encoding="utf-8", newline="\n") as f:
        f.write(original)
    print(">>> RESULT: rule E-07 restored")

    banner("BEAT 4/4: re-run after restore")
    out, rc = check()
    print(out.strip())
    if rc != 0:
        print("DEMO ABORTED: tree not green again after restore")
        return 1
    print("\nDEMO DONE: green -> red -> restored -> green. The gates bite.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
