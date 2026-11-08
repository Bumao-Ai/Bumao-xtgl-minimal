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

"""break_it.py -- inject the template pack, prove the green baseline, then break the SSOT.

This edition declares zero_rules, so rules/ ships empty and there is nothing to break in
place. The script therefore walks the documented injection path first:

  1. copy examples/r*.json into rules/ -- and refuse to touch rules/ if it already holds a
     chapter file that is neither byte-identical to its examples/ twin nor demo-broken
     (a rule pack you wrote yourself is never demo dust)
  2. `python render.py write`, then this edition's entry point
     `python BumaoXTGL_Minimal_v01.py check --strict`, and require ALL PASS -- the
     baseline is measured, not assumed
  3. break rules/r02_safety.json clause 2.5: id -> "2.4" (a duplicate) and its title
     tagged " [DEMO-BROKEN]", deliberately WITHOUT re-rendering, so the views drift too
  4. run check --strict again and print the gates that went red

The gate engine is the shared kernel outside this directory, reached through the entry
point above; nothing here imports or calls a local engine.py.
Idempotent: re-running restores the pristine example bytes before breaking again.
Exit code: 0 when the break succeeded (check --strict then exits non-zero).
Return to green with fix_it.py; return to the shipped empty rules/ with fix_it.py --uninject.
"""
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RULES = os.path.join(ROOT, "rules")
EXAMPLES = os.path.join(ROOT, "examples")
ENTRY = "BumaoXTGL_Minimal_v01.py"
DEMO_CHAPTER = "r02_safety.json"
DEMO_CLAUSE = 4                       # index of clause 2.5 inside r02_safety.json
MARK = "[DEMO-BROKEN]"

CHAPTER_FILE = re.compile(r"^r\d{2}.*\.json$")
GATE_ID = re.compile(r"^[A-Z]{1,2}\d{1,2}$")


def safe_print(*a):
    # tolerate a downstream consumer closing stdout early (e.g. | Select -First N)
    try:
        print(*a)
    except OSError:
        pass


def text_of(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def classify(fn):
    """pristine | broken | foreign -- 'foreign' means a file this demo must not touch."""
    live = os.path.join(RULES, fn)
    twin = os.path.join(EXAMPLES, fn)
    if not os.path.exists(twin) or not os.path.exists(live):
        return "foreign"
    a = text_of(live)
    if a == text_of(twin):
        return "pristine"
    return "broken" if MARK in a else "foreign"


def rule_files(d):
    return sorted(f for f in os.listdir(d) if CHAPTER_FILE.match(f)) if os.path.isdir(d) else []


def red_gates(text):
    return [p[1] for p in (ln.strip().split() for ln in text.splitlines())
            if len(p) > 1 and p[0] == "FAIL" and GATE_ID.match(p[1])]


def run(*args):
    p = subprocess.run([sys.executable] + list(args), cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def check_strict():
    return run(ENTRY, "check", "--strict")


def main():
    os.chdir(ROOT)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=== ALL PASS -> FAIL  (demo break) ===")

    foreign = [fn for fn in rule_files(RULES) if classify(fn) == "foreign"]
    if foreign:
        safe_print("ERROR: rules/ holds %s, which matches no file in examples/." % foreign)
        safe_print("Refusing to break a rule pack this demo did not inject. Remove it, or run")
        safe_print("the demo on a clone of the shipped repository.")
        return 2

    injected = rule_files(RULES)
    if injected:
        shutil.copyfile(os.path.join(EXAMPLES, DEMO_CHAPTER), os.path.join(RULES, DEMO_CHAPTER))
        safe_print("already injected -> restored pristine %s from examples/ before re-breaking"
                   % DEMO_CHAPTER)
    else:
        for fn in rule_files(EXAMPLES):
            shutil.copyfile(os.path.join(EXAMPLES, fn), os.path.join(RULES, fn))
            injected.append(fn)
        safe_print("injected %d chapter file(s) examples/ -> rules/: %s"
                   % (len(injected), ", ".join(injected)))

    rc, out = run("render.py", "write")
    safe_print("render.py write rc=%d :: %s" % (rc, out.strip()))

    rc, out = check_strict()
    if rc != 0:
        safe_print("BASELINE NOT GREEN: check --strict rc=%d, red gates %s" % (rc, red_gates(out)))
        safe_print("Nothing was broken. Leaving the injected pack untouched for you to inspect;")
        safe_print("run fix_it.py --uninject to return to the shipped state.")
        return 3
    safe_print("baseline measured: check --strict rc=0, ALL PASS with %d chapter file(s) live"
               % len(injected))

    path = os.path.join(RULES, DEMO_CHAPTER)
    z = json.loads(text_of(path))
    target = z["clauses"][DEMO_CLAUSE]
    assert target["id"] == "2.5", "unexpected clause at index %d: %r" % (DEMO_CLAUSE, target.get("id"))
    target["id"] = "2.4"                                  # duplicate of clause 2.4
    target["title"] = target["title"] + "  " + MARK
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(z, ensure_ascii=False, indent=1) + "\n")
    safe_print("broke rules/%s: clause 2.5 id->'2.4' (dup), title tagged %s" % (DEMO_CHAPTER, MARK))
    safe_print("views/ intentionally NOT re-rendered (drift expected)")

    rc, out = check_strict()
    red = red_gates(out)
    safe_print("RED GATES: %s" % (", ".join(red) if red else "(none -- unexpected!)"))

    if rc != 0 and red:
        safe_print("break OK: check --strict rc=%d (expected non-zero). Fix it with fix_it.py." % rc)
        return 0
    safe_print("break FAILED: check --strict rc=%d, red gates %s" % (rc, red))
    return 4


if __name__ == "__main__":
    sys.exit(main())
