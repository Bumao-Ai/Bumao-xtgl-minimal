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

"""rules_db.py -- load the single source of truth and structurally validate it.

The rules/r*.json files are the ONLY authority. This module reads them, derives
an index (clause refs, counts), and exposes structural checks used by the gates.
It never defines rules and never keeps a second copy of the text.

Root anchoring: the repository root is the nearest ancestor directory that
contains BOTH a `rules/` folder and a `meta.json` file. There is no hardcoded
drive letter or absolute path; the project is fully relocatable.
"""
import io
import json
import os
import re
import sys


def find_root(start):
    """Walk upward until we find a dir that has rules/ AND meta.json."""
    q = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(q, "rules")) and os.path.isfile(os.path.join(q, "meta.json")):
            return q
        n = os.path.dirname(q)
        if n == q:
            break
        q = n
    raise RuntimeError("Could not locate project root (expected rules/ + meta.json above %s)" % start)


ROOT = find_root(os.path.dirname(os.path.abspath(__file__)))
RULES_DIR = os.path.join(ROOT, "rules")
META_PATH = os.path.join(ROOT, "meta.json")
VIEWS_DIR = os.path.join(ROOT, "views")
LOGS_DIR = os.path.join(ROOT, "logs")


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def load_json(path):
    return json.loads(read(path))


def chapter_files():
    if not os.path.isdir(RULES_DIR):
        return []
    return sorted(f for f in os.listdir(RULES_DIR) if re.match(r"^r\d{2}.*\.json$", f))


def load_meta():
    return load_json(META_PATH)


def load_db():
    """Return {'meta':..., 'chapters':[...], 'clauses':[...]}."""
    meta = load_meta()
    chapters, clauses = [], []
    for fn in chapter_files():
        z = load_json(os.path.join(RULES_DIR, fn))
        chapters.append({"ch": z["ch"], "file": z["file"],
                         "chapter_title": z["chapter_title"], "n": len(z["clauses"])})
        for c in z["clauses"]:
            c2 = dict(c)
            c2["ch"] = z["ch"]
            c2["_file"] = fn
            clauses.append(c2)
    return {"meta": meta, "chapters": chapters, "clauses": clauses}


# --- structural checks (return list of problem ids / messages) ---------------

ID_PREFIX = re.compile(r"^\s*\d+(?:\.\d+)*(?:\(\d+(?:\.\d+)?\))*\s*")
REF = re.compile(r"(?<![0-9.])(\d{1,2}\.\d{1,2}(?:\.\d{1,2}){0,2})")


def duplicate_ids(clauses):
    seen, dup = set(), []
    for c in clauses:
        if c["id"] in seen:
            dup.append(c["id"])
        seen.add(c["id"])
    return sorted(set(dup))


def root_mismatches(clauses):
    bad = []
    for c in clauses:
        expected = c["id"].split("(")[0]
        if c.get("root") != expected:
            bad.append(c["id"])
    return bad


def missing_keys(clauses):
    bad = []
    for c in clauses:
        for k in ("id", "root", "title", "body"):
            if k not in c:
                bad.append("%s:missing-%s" % (c.get("id", "?"), k))
    return bad


def block_broken(clauses):
    """Children of a root must be contiguous and the parent must come first."""
    pos, bad = {}, []
    for i, c in enumerate(clauses):
        pos.setdefault(c["root"], []).append(i)
    for r, ps in pos.items():
        if ps != list(range(ps[0], ps[0] + len(ps))) or clauses[ps[0]]["id"] != r:
            bad.append(r)
    return sorted(set(bad))


def content_of(c):
    """The substantive text of a clause (after stripping the clause number)."""
    t = (c.get("title") or "").strip()
    for _ in range(2):
        t = ID_PREFIX.sub("", t, count=1).strip()
    body = " ".join(x.strip() for x in (c.get("body") or []) if x.strip())
    if body:
        return body
    parts = re.split(r"[::]", t, 1)
    if len(parts) == 2:
        return parts[1].strip()
    return t


def shell_clauses(clauses):
    """Clauses that say nothing: empty title+body, or a titled grouping with no body and no children."""
    ids = [c["id"] for c in clauses]
    out = []
    for c in clauses:
        title = (c.get("title") or "").strip()
        nbody = len([x for x in (c.get("body") or []) if x.strip()])
        if not title and nbody == 0:
            out.append(c["id"] + "(empty)")
            continue
        if nbody > 0:
            continue
        if any(k.startswith(c["id"] + "(") or k.startswith(c["id"] + ".") for k in ids):
            continue
        if not content_of(c):
            out.append(c["id"])
    return out


def broken_refs(clauses):
    """Inline references like 'see 2.3' that point at no existing id/root."""
    ids = set(c["id"] for c in clauses)
    roots = set(c["root"] for c in clauses)
    bad = set()
    for c in clauses:
        text = c.get("title", "") + "\n" + "\n".join(c.get("body", []))
        for r in REF.findall(text):
            if r not in ids and r not in roots:
                bad.add("%s->%s" % (c["id"], r))
    return sorted(bad)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    db = load_db()
    print("Loaded %s %s: %d clauses across %d chapters" % (
        db["meta"]["name"], db["meta"]["version"], len(db["clauses"]), len(db["chapters"])))
    print("  duplicate ids:", duplicate_ids(db["clauses"]))
    print("  root mismatches:", root_mismatches(db["clauses"]))
    print("  missing keys:", missing_keys(db["clauses"]))
    print("  broken blocks:", block_broken(db["clauses"]))
    print("  shell clauses:", shell_clauses(db["clauses"]))
    print("  broken refs:", broken_refs(db["clauses"]))
