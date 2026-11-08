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

"""edit.py -- the ONLY supported way to change rules (block-level API).

Why this file exists: clauses live in contiguous clusters (a root clause plus all
its children). Hand-computing list indices twice broke a cluster in the past.
Callers may only operate on whole blocks; they never touch the clauses list by
index. After editing you must run: render, then check --strict.
"""
import io
import json
import os
import re
import sys

import rules_db as dbm

CL_NUM = re.compile(r"^(\d+(?:\.\d+)+)(\(\d+(?:\.\d+)?\))?")


def _path_for_chapter(ch):
    for fn in dbm.chapter_files():
        z = dbm.load_json(os.path.join(dbm.RULES_DIR, fn))
        if z["ch"] == int(ch):
            return os.path.join(dbm.RULES_DIR, fn), z
    raise KeyError("No chapter numbered %d" % int(ch))


def load(ch):
    path, z = _path_for_chapter(ch)
    return path, z


def save(path, z):
    _assert_shape(z)
    _assert_no_orphan(z)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(z, ensure_ascii=False, indent=1) + "\n")


def block_span(z, root):
    """Half-open [start,end) range covering root plus all its children."""
    ids = [c["id"] for c in z["clauses"]]
    if root not in ids:
        raise KeyError("Clause %s not found" % root)
    s = ids.index(root)
    e = s + 1
    while e < len(ids) and (ids[e].startswith(root + "(") or ids[e].startswith(root + ".")):
        e += 1
    return s, e


def _mk_clause(num, title, body=None):
    return {"id": num, "root": num.split("(")[0],
            "title": title, "body": list(body or [])}


def insert_after_block(ch, root, titles, body=None):
    """titles: list of strings starting with the clause number, e.g. ['3.6 New rule text.']."""
    path, z = load(ch)
    s, e = block_span(z, root)
    new = []
    for t in titles:
        m = CL_NUM.match(t.strip())
        if not m:
            raise ValueError("Title must start with a clause number: %r" % t[:30])
        new.append(_mk_clause(m.group(1), t, body))
    z["clauses"][e:e] = new
    save(path, z)
    return [c["id"] for c in new]


def append_body(ch, cid, text):
    """Append one line to a clause's body (does not touch block structure)."""
    path, z = load(ch)
    ids = [c["id"] for c in z["clauses"]]
    if cid not in ids:
        raise KeyError(cid)
    c = z["clauses"][ids.index(cid)]
    assert text not in c["body"], "Line already present; refusing duplicate"
    c["body"].append(text)
    save(path, z)
    return len(c["body"])


def replace_body(ch, cid, prefix, text):
    """Replace the single body line that starts with `prefix`."""
    path, z = load(ch)
    ids = [c["id"] for c in z["clauses"]]
    c = z["clauses"][ids.index(cid)]
    hit = [i for i, b in enumerate(c["body"]) if b.startswith(prefix)]
    assert len(hit) == 1, "prefix matched %d lines (need exactly 1)" % len(hit)
    c["body"][hit[0]] = text
    save(path, z)
    return hit[0]


def delete_clause(ch, cid):
    path, z = load(ch)
    ids = [c["id"] for c in z["clauses"]]
    if cid not in ids:
        raise KeyError(cid)
    i = ids.index(cid)
    del z["clauses"][i]
    save(path, z)
    return i


def _assert_shape(z):
    for c in z["clauses"]:
        for k in ("id", "root", "title", "body"):
            assert k in c, "Clause %s missing field %s" % (c.get("id", "?"), k)
        assert c["root"] == c["id"].split("(")[0], "root/id mismatch: %s" % c["id"]


def _assert_no_orphan(z):
    seen = []
    for c in z["clauses"]:
        root = c["id"].split("(")[0]
        if "(" in c["id"] and (not seen or seen[-1] != root):
            raise AssertionError("Block broken: %s is not directly under %s" % (
                c["id"], seen[-1] if seen else "nothing"))
        seen.append(root)


def selftest():
    """In-memory sanity check (no disk writes)."""
    z = dbm.load_db()
    clauses = z["clauses"]
    assert not dbm.duplicate_ids(clauses)
    assert not dbm.block_broken(clauses)
    print("edit selftest PASS: no dup ids, blocks contiguous")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        sys.exit(selftest())
    print(__doc__)
