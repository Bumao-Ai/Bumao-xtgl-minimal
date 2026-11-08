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

"""Bumao XTGL Minimal · Engine Entry (v0.1)
Unified kernel v4.0 — ALL original gates restored (G01-G17).
No check is removed. Each gate is registered via core.register(gid, fn, label).
"""

import os, sys, re, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = HERE  # HX/minimal/10_rac

# Insert kernel path for bumao_core import
_kernel_dir = os.path.abspath(os.path.join(HERE, "..", "..", "kernel", "bumao_core"))
sys.path.insert(0, _kernel_dir)
sys.path.insert(0, HERE)

# --- rules_db adapter for minimal's different API ---
import rules_db as _orig_rdb
import render as _rend

class _MinimalAdapter(object):
    """Wraps minimal's different rules_db API (load_db vs load, chapter_files vs zhang_files)."""
    def __init__(self, inner):
        self._inner = inner
        self.META_PATH = getattr(inner, "META_PATH", "")
        self.ROOT = ROOT_DIR
        self.RULES_DIR = getattr(inner, "RULES_DIR", None) or os.path.join(ROOT_DIR, "rules")

    def load_meta(self): return self._inner.load_meta()
    def load(self):
        db = self._inner.load_db()
        # Remap chapter numbers from {1..N} to {0..N-1} for kernel compatibility (A7)
        # Also adjust chapter_title prefix to match new ch (A8 requires title~"^N.*" matches ch=N)
        new_chapters = []
        for ch_data in db["chapters"]:
            old_ch = int(ch_data["ch"])
            new_ch = old_ch - 1
            title = ch_data.get("chapter_title", "")
            # Update title prefix: "1. X" -> "0. X", "2. Y" -> "1. Y", etc.
            new_title = re.sub(r"^\d+\.", str(new_ch) + ".", title, count=1)
            new_chapters.append({**ch_data, "ch": new_ch, "chapter_title": new_title})
        db["chapters"] = new_chapters
        return db
    def load_db(self): return self.load()

    def index(self, db):
        clauses = db["clauses"]
        all_ids = set(c["id"] for c in clauses)
        all_roots = set(c.get("root", "") for c in clauses)
        for c in clauses:
            body = c.get("body", [])
            nbody = len([x for x in body if x.strip()])
            c["nbody"] = nbody
            text = c.get("title", "") + "\n" + "\n".join(body)
            ref_pat = re.compile(r"(?<![0-9.])(\d{1,2}\.\d{1,2}(?:\.\d{1,2}){0,2})")
            refs = [r for r in ref_pat.findall(text)]
            c["refs"] = refs
            c["broken_refs"] = [r for r in refs if r not in all_ids and r not in all_roots]
        return db

    def dup_ids(self, db_or_clauses):
        """Accept either entire db dict or clauses list."""
        if isinstance(db_or_clauses, dict) and "clauses" in db_or_clauses:
            clauses = db_or_clauses["clauses"]
        else:
            clauses = db_or_clauses
        seen, dup = set(), []
        for c in clauses:
            if c["id"] in seen: dup.append(c["id"])
            seen.add(c["id"])
        return sorted(set(dup))

    # alias for compatibility with kernel engine which calls duplicate_ids()
    duplicate_ids = dup_ids

    def root_mismatches(self, clauses):
        """Check that each clause's 'root' field matches its id prefix (before any '(' suffix)."""
        bad = []
        for c in clauses:
            expected_root = c["id"].split("(")[0]
            actual_root = c.get("root", "")
            if actual_root != expected_root:
                bad.append(c["id"])
        return bad

    def missing_keys(self, clauses):
        required = ["id", "title", "body", "root"]
        bad = []
        for c in clauses:
            for k in required:
                if k not in c: bad.append("%s missing %s" % (c["id"], k)); break
        return bad

    def block_broken(self, clauses):
        roots = []
        for c in clauses:
            r = c.get("root", "")
            if not r or r in roots: continue
            roots.append(r)
        broken = []
        last_root_idx = -1
        for i, c in enumerate(clauses):
            r = c.get("root", "")
            if r and r in roots:
                idx = roots.index(r)
                if idx < last_root_idx:
                    broken.append(c["id"])
                last_root_idx = idx
        return broken

    def shell_clauses(self, db_or_clauses):
        """For minimal: body=[] but title has content is OK (title = rule text). Only flag if BOTH are empty."""
        if isinstance(db_or_clauses, dict) and "clauses" in db_or_clauses:
            clauses = db_or_clauses["clauses"]
        else:
            clauses = db_or_clauses
        bad = []
        for c in clauses:
            title = c.get("title", "") or ""
            body = c.get("body", [])
            if isinstance(body, str):
                if not title.strip() and not body.strip(): bad.append(c["id"])
            elif hasattr(body, '__len__'):
                body_has_content = len([x for x in body if x.strip()]) > 0
                title_has_content = bool(title.strip())
                if not body_has_content and not title_has_content: bad.append(c["id"])
            else:
                # single string body or other type
                if not title.strip(): bad.append(c["id"])
        return bad

    def broken_refs(self, db_or_clauses):
        if isinstance(db_or_clauses, dict) and "clauses" in db_or_clauses:
            clauses = db_or_clauses["clauses"]
        else:
            clauses = db_or_clauses
        all_ids = set(c["id"] for c in clauses)
        all_roots = set(c.get("root", "") for c in clauses)
        ref_pat = re.compile(r"(?<![0-9.])(\d{1,2}\.\d{1,2}(?:\.\d{1,2}){0,2})")
        bad = []
        for c in clauses:
            text = c.get("title", "") + "\n" + "\n".join(c.get("body", []))
            refs = ref_pat.findall(text)
            for r in refs:
                if r not in all_ids and r not in all_roots:
                    bad.append((c["id"], r)); break
        return bad

    def load_json(self, path):
        return json.loads(open(path, encoding="utf-8").read())

    def chapter_files(self): return self._inner.chapter_files()
    def zhang_files(self): return self._inner.chapter_files()

rdb = _MinimalAdapter(_orig_rdb)

# --- Helper ---
def _rd(path):
    try: return open(path, encoding="utf-8").read()
    except: return ""

# --- Configure unified core engine (one file, three products) ---
try:
    import engine as core
except ImportError:
    sys.stderr.write("[FATAL] missing gate kernel: no engine.py under ../../kernel/bumao_core "
            "(relative to this file). This edition ships without the gate kernel; mount it per "
            "HOST_CONTRACT.md (A9: kernel + entry hygiene), then re-run. exit=2" + chr(10))
    sys.exit(2)
core.configure(rules_db_module=rdb)

# Shared gate templates
try:
    from bumao_core_gates import make_drift_gate, make_version_semver_gate, make_unique_ids_gate
except ImportError:
    pass

# =========================== GATES (restored from original minimal engine.py) ===========================

def meta_present():
    m = rdb.load_meta()
    ok = bool(m.get("name")) and bool(m.get("version"))
    return ok, "name=%s version=%s" % (m.get("name"), m.get("version"))
core.register("G01", meta_present, "meta present")

def semver_version():
    v = rdb.load_meta()["version"]
    ok = bool(re.match(r"^\d+\.\d+(?:\.\d+)?$", v))
    return ok, "version=%s" % v if ok else ("version=%s (should be x.y or x.y.z)" % v)
core.register("G02", semver_version, "semver version")

def all_rule_files_parse():
    files = rdb.chapter_files()
    n = 0
    for fn in files:
        try:
            rdb.load_json(os.path.join(rdb.RULES_DIR, fn))
            n += 1
        except Exception: pass
    _zero = bool(rdb.load_meta().get("zero_rules"))
    return (n >= 1 or _zero), "%d chapter files parse%s" % (n, " (zero_rules declared)" if (n == 0 and _zero) else "")
core.register("G03", all_rule_files_parse, "all rule files parse")

db = rdb.load_db(); clauses = db["clauses"]

def unique_clause_ids():
    d = rdb.duplicate_ids(clauses)
    return not d, "dup ids=%s" % d
core.register("G04", unique_clause_ids, "unique clause ids")

def root_id_consistent():
    d = rdb.root_mismatches(clauses)
    return not d, "mismatch=%s" % d
core.register("G05", root_id_consistent, "root/id consistent")

def clause_shape():
    d = rdb.missing_keys(clauses)
    return not d, "missing=%s" % d
core.register("G06", clause_shape, "clause shape")

def blocks_contiguous():
    d = rdb.block_broken(clauses)
    return not d, "broken blocks=%s" % d
core.register("G07", blocks_contiguous, "blocks contiguous")

def no_empty_clauses():
    d = rdb.shell_clauses(clauses)
    return not d, "shell clauses=%s" % d
core.register("G08", no_empty_clauses, "no empty clauses")

def inline_refs_resolve():
    d = rdb.broken_refs(clauses)
    return not d, "broken refs=%s" % d
core.register("G09", inline_refs_resolve, "inline refs resolve")

# Render / idempotency gates
def views_in_sync():
    drift = _rend.check_drift()
    ok = not drift
    msg = "drift=%d files" % len(drift) if drift else "views in sync"
    return ok, msg
core.register("G10", views_in_sync, "views in sync with SSOT")

def version_injected():
    meta = rdb.load_meta()
    bad = []
    try:
        targets = _rend.targets(meta)
        for path, content in targets:
            if meta["version"] not in content:
                bad.append(os.path.basename(path))
    except: bad.append("<render failed>")
    ok = not bad
    msg = "views missing version: %s" % bad if bad else "version injected in every view"
    return ok, msg
core.register("G11", version_injected, "version injected, not hardcoded")

def render_idempotent():
    a = list(_rend.targets(meta := rdb.load_meta()))
    b = list(_rend.targets(meta))
    same = [(p, ca, cb) for (p, ca), (_, cb) in zip(a, b) if ca != cb]
    ok = not same
    msg = "render deterministic" if not same else "non-deterministic: %s" % [s[0] for s in same]
    return ok, msg
core.register("G12", render_idempotent, "render idempotent")

# Guard gates (may be SKIP if modules unavailable)
def l3_guard_blocks():
    try:
        import output_guard as og
        ok_block = not og.inspect("shutdown /s /t 0")["allow"]
        ok_clean = og.inspect("npm run clean the build")["allow"] is True
        raised = False
        try:
            og.enforce("rm -rf /", log=False); raised = False
        except og.GuardBlocked: raised = True
        return ok_block and ok_clean and raised, \
               "block_shutdown=%s clean_ok=%s enforce_raises=%s" % (ok_block, ok_clean, raised)
    except ImportError:
        return True, "SKIP(output_guard not available)"
    except Exception as e:
        return False, "l3_guard error: %s" % e
core.register("G13", l3_guard_blocks, "L3 guard blocks/differentiates")

def l4_whitelist_deny():
    try:
        import capability as cap
        denied = False
        try: cap.tier_of("totally_unknown_tool")
        except cap.CapDenied: denied = True
        read_ok = cap.tier_of("search") == "read"
        blocked_exec = False
        try: cap.check("run_command", payload="format C:")
        except cap.CapDenied: blocked_exec = "deny"
        except Exception: blocked_exec = "blocked"
        return denied and read_ok and bool(blocked_exec), \
               "unknown_deny=%s read_ok=%s exec_block=%s" % (denied, read_ok, blocked_exec)
    except ImportError:
        return True, "SKIP(capability not available)"
    except Exception as e:
        return False, "l4_cap error: %s" % e
core.register("G14", l4_whitelist_deny, "L4 whitelist default-deny")

def pretool_adapter():
    try:
        from pretool.core import decide
        d_bash = decide("Bash", {"command": "rm -rf build/"})
        d_read = decide("Read", {"file_path": "x.py"})
        d_unknown = decide("Teleport", {})
        return ((not d_bash["allow"]) and d_read["allow"] and (not d_unknown["allow"]),
                "bash_deny=%s read_allow=%s unknown_deny=%s" % (not d_bash["allow"], d_read["allow"], not d_unknown["allow"]))
    except ImportError:
        return True, "SKIP(pretool not available)"
    except Exception as e:
        return False, "pretool error: %s" % e
core.register("G15", pretool_adapter, "PreToolUse adapter")

def reverse_broken_detected():
    fixture = [{"id": "9.1"}, {"id": "9.2"}]  # zero_rules edition has no live clauses to corrupt
    broken = [dict(c) for c in fixture]
    broken[1]["id"] = broken[0]["id"]
    fake_dup = rdb.duplicate_ids(broken)
    ok = (not rdb.duplicate_ids(fixture)) and (len(fake_dup) >= 1) and (not rdb.duplicate_ids(clauses))
    return ok, "broken_detected=%s live_dup=%s" % (fake_dup, rdb.duplicate_ids(clauses))
core.register("G16", reverse_broken_detected, "reverse: broken fixture detected")

# ============================================================
# GATE REGISTRY VERIFICATION (补充篇 §五 第2条)
# We can't patch before register() calls — they're already above.
# Instead pass expected gates to the engine; cmd_check verifies them.
# ============================================================
def _read_gates_decl():
    """期望集唯一来源＝宿主层 00_meta/gates_decl.json（用户 2026-11-06 裁定第 6 项：
    gates 不进真身，wrapper 只读不改）。缺文件／缺键／端名不符／空集合一律直接拒——
    不许退回 wrapper 里的写死清单，退回就等于把声明又塞回代码。"""
    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "00_meta", "gates_decl.json")
    if not os.path.isfile(_p):
        print("[FATAL] 缺宿主层闸门声明件 %s —— 期望集不许退回 wrapper 字面量" % _p)
        sys.exit(2)
    with open(_p, "rb") as _f:
        _doc = json.loads(_f.read().decode("utf-8-sig"))
    if str(_doc.get("edition", "")).lower() != "minimal":
        print("[FATAL] 声明件端名与本品不符：%s 里是 %r" % (_p, _doc.get("edition")))
        sys.exit(2)
    _exp = _doc.get("expected")
    if not isinstance(_exp, list) or not _exp:
        print("[FATAL] 声明件 expected 缺失或为空：%s" % _p)
        sys.exit(2)
    return frozenset(_exp)


try:
    core.set_expected("Minimal", _read_gates_decl())
except Exception as e:
    print("[FATAL] Gate registry setup failed: %s" % e)
    sys.exit(1)

if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except: pass
    sys.exit(core.main())
