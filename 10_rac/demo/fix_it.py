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

"""fix_it.py -- undo break_it.py and drive the SSOT back to ALL PASS.

  1. restore every rules/r*.json this demo injected, byte-for-byte from examples/ -- files
     that match no examples/ twin are left alone, because they are not demo output
  2. `python render.py write`, so views/ matches the SSOT again
  3. run this edition's entry point `python BumaoXTGL_Minimal_v01.py check --strict`
     and require ALL PASS (exit 0)

The gate engine is the shared kernel outside this directory, reached through the entry
point above; nothing here imports or calls a local engine.py.
`fix_it.py --uninject` goes one step further and returns the repository to the shipped
state: the restored chapter files are removed from rules/ again (which is what the
zero_rules declaration in meta.json asserts) and the chapter views rendered from them are
removed with them, so views/ keeps only what render.py still produces.
Idempotent: safe to run even when the repository is already green.
Exit code: 0 only when check --strict reports ALL PASS.
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
VIEWS = os.path.join(ROOT, "views")
ENTRY = "BumaoXTGL_Minimal_v01.py"

CHAPTER_FILE = re.compile(r"^r\d{2}.*\.json$")


def safe_print(*a):
    try:
        print(*a)
    except OSError:
        pass


def text_of(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def rule_files(d):
    return sorted(f for f in os.listdir(d) if CHAPTER_FILE.match(f)) if os.path.isdir(d) else []


def view_name_of(path):
    """The chapter view this rules file renders to, or None if the file is unreadable."""
    try:
        return json.loads(text_of(path)).get("file")
    except Exception:
        return None


def run(*args):
    p = subprocess.run([sys.executable] + list(args), cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def rendered_paths():
    """Paths render.py regenerates right now -- used to spare anything still derived."""
    try:
        sys.path.insert(0, ROOT)
        import render
        return [path for path, _content in render.targets()]
    except Exception:
        return []


def main():
    os.chdir(ROOT)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    uninject = "--uninject" in sys.argv[1:]
    print("=== FAIL -> ALL PASS  (demo fix%s) ===" % (" / uninject" if uninject else ""))

    restored, skipped = [], []
    for fn in rule_files(RULES):
        twin = os.path.join(EXAMPLES, fn)
        if not os.path.exists(twin):
            skipped.append(fn)
            continue
        if text_of(os.path.join(RULES, fn)) != text_of(twin):
            shutil.copyfile(twin, os.path.join(RULES, fn))
            restored.append(fn)

    injected_views = [view_name_of(os.path.join(RULES, fn)) for fn in rule_files(RULES)]
    kept = [v for v in injected_views if v]

    if restored:
        safe_print("restored from examples/: %s" % ", ".join(restored))
    if skipped:
        safe_print("left untouched (no examples/ twin): %s" % ", ".join(skipped))

    if uninject:
        for fn in rule_files(RULES):
            os.remove(os.path.join(RULES, fn))
        rendered = rendered_paths()
        for v in kept:
            vp = os.path.join(VIEWS, v)
            if os.path.exists(vp) and vp not in rendered:
                os.remove(vp)
                safe_print("removed orphan chapter view: views/%s" % v)
        safe_print("removed the injected chapter file(s) -- rules/ is empty again, "
                   "which is what meta.json declares")

    rc, out = run("render.py", "write")
    safe_print("--- render.py write rc=%d :: %s" % (rc, out.strip()))

    rc, out = run(ENTRY, "check", "--strict")
    tail = out.strip().splitlines()[-1][:80] if out.strip() else "(no output)"
    safe_print("--- %s check --strict rc=%d :: %s" % (ENTRY, rc, tail))

    if rc == 0:
        print("fix OK: FAIL -> ALL PASS restored")
        return 0
    print("fix FAILED: check --strict rc=%d" % rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
