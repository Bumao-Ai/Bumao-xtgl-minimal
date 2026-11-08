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

"""Bumao Core · Shared Gate Templates

将三端共有的闸逻辑提取到此处，由宿主注入取数函数，生成产品特定的闸函数。
实现'一处编写、三端复用'——修改此文件即可影响所有产品。

注入契约（2026-11-07 修订）：
    1. 内核不 import 任何端上私有模块，可脱离端目录树单独 import。
    2. 该路注入没给 → 判 FAIL 并写明缺哪个注入名，不再返回 True。
       旧写法「no rules_db available」把「没接线」伪装成「检查通过」，是假绿。
    3. 取数口径一律由宿主传函数进来；模板内不再猜 rules_db 的属性名
       （旧写法调的 duplicate_ids／chapter_files／missing_keys／broken_refs 在端上根本不存在，
        shell_clauses 的入参也是 db 整体而非 clauses）。

用法（在 wrapper 中）：
    from bumao_core_gates import make_drift_gate
    b1_drift = make_drift_gate(lambda: render.check_drift(), hint_func=_hint)
    core.register("B1", b1_drift, "视图漂移为 0")

生效：2026-11-04 ｜ 修订：2026-11-07 ｜ 适用：三端共用
"""

import os
import re
import hashlib


def _missing(*names):
    """统一的「没接线就是红」出口。"""
    return False, "缺注入：%s —— 模板不猜端上取数口径，也不 import 端上私有模块" % "、".join(names)


def _run(fn, what):
    """调用注入函数；异常按红处理并带出异常文本（红票可查，不留「静默通过」）。"""
    try:
        return True, fn()
    except Exception as e:
        return False, "%s 实跑异常：%s" % (what, str(e)[:100])


def make_drift_gate(drift_func=None, hint_func=None):
    """视图漂移检测模板 —— 对应 B1/B12/G10。

    drift_func() -> 漂移文件路径列表（空列表＝视图与真身一致）。
    hint_func(drift_list) -> 一句附加说明，可选（如并发中间态提示）。
    """
    def drift_check():
        if drift_func is None:
            return _missing("drift_func")
        ok, drift = _run(drift_func, "drift_func")
        if not ok:
            return False, drift
        drift = list(drift or [])
        if not drift:
            return True, ""
        detail = [os.path.basename(str(p)) for p in drift[:5]]
        if hint_func is not None:
            hok, hint = _run(lambda: hint_func(drift), "hint_func")
            if hok and hint:
                detail.append(hint)
        return False, detail
    return drift_check


def make_render_idempotent_gate(targets_func=None):
    """渲染幂等模板 —— 对应 G12/B2。

    targets_func() -> [(路径, 正文), ...]，同一口径调两次，逐路径比哈希。
    旧写法在模板里连调两次 render_module.targets(meta) 再自己比自己，
    没把渲染交给宿主，等于永远返回 0 差异。
    """
    def idempotent_check():
        if targets_func is None:
            return _missing("targets_func")
        ok, first = _run(targets_func, "targets_func")
        if not ok:
            return False, first
        ok, second = _run(targets_func, "targets_func")
        if not ok:
            return False, second
        h1 = dict((p, hashlib.sha256(str(c).encode("utf-8")).hexdigest()) for p, c in first)
        h2 = dict((p, hashlib.sha256(str(c).encode("utf-8")).hexdigest()) for p, c in second)
        diff = [p for p in sorted(set(h1) | set(h2)) if h1.get(p) != h2.get(p)]
        return (not diff), "两次渲染差异 %d%s" % (len(diff), "" if not diff else "：%s" % str(diff[:3]))
    return idempotent_check


def make_version_semver_gate(version_func=None, pattern=r"^\d+\.\d+\.\d+$"):
    """共享版本号格式检查模板 —— 对应 G02。"""
    def semver_check():
        if version_func is None:
            return _missing("version_func")
        ok, v = _run(version_func, "version_func")
        if not ok:
            return False, v
        v = str(v or "")
        good = bool(re.match(pattern, v))
        return good, ("version=%s" % v) if good else ("version=%s 不符 %s" % (v, pattern))
    return semver_check


def make_root_flat_gate(base_dir=None, allowed=("README-HX.txt",)):
    """项目域根下平铺文件白名单模板 —— 对应 B5a。"""
    def root_flat_check():
        if not base_dir or not os.path.isdir(base_dir):
            return _missing("base_dir（项目域根目录）")
        files_top = [f for f in sorted(os.listdir(base_dir))
                     if os.path.isfile(os.path.join(base_dir, f)) and not f.startswith(".git")]
        return files_top in ([], list(allowed)), str(files_top[:6])
    return root_flat_check


def make_subdir_names_gate(base_dir=None, pattern=r"^\d{2}_[a-z]+$"):
    """子目录命名模板 —— 对应 B5b。"""
    def subdir_check():
        if not base_dir or not os.path.isdir(base_dir):
            return _missing("base_dir（项目域根目录）")
        dirs_top = [f for f in sorted(os.listdir(base_dir))
                    if os.path.isdir(os.path.join(base_dir, f)) and not f.startswith(".")]
        bad = [f for f in dirs_top if not re.match(pattern, f)]
        return (not bad), ("bad dirs: %s" % str(bad[:3])) if bad else "%d 个子目录名合规" % len(dirs_top)
    return subdir_check


def make_stale_lock_gate(lock_current_func=None, stale_reason_func=None):
    """运行锁残留模板 —— 对应 B9。

    lock_current_func() -> 当前锁描述（空＝无锁）。
    stale_reason_func() -> 可接管原因（空＝锁主进程仍在，是真并发）。
    """
    def stale_lock_check():
        if lock_current_func is None:
            return _missing("lock_current_func")
        ok, cur = _run(lock_current_func, "lock_current_func")
        if not ok:
            return False, cur
        if not cur:
            return True, ""
        if stale_reason_func is None:
            return _missing("stale_reason_func（否则锁主不明时无人判定可否接管）")
        ok, why = _run(stale_reason_func, "stale_reason_func")
        if not ok:
            return False, why
        if why:
            return True, "陈旧锁可接管（%s）：%s" % (why, cur)
        return False, "%s（进程仍在，视为真并发）" % cur
    return stale_lock_check


def make_pii_scan_gate(pii_words_func=None, scan_targets_func=None, exclude_set=frozenset()):
    """共享PII扫描模板 —— 对应 B6/B13 的扫描内核。

    pii_words_func() -> 需扫的环境标识词列表。
    scan_targets_func() -> [(基目录, 文件名), ...]，也接受纯文件名字符串。
    """
    def pii_check():
        if pii_words_func is None or scan_targets_func is None:
            return _missing("pii_words_func", "scan_targets_func")
        ok, words = _run(pii_words_func, "pii_words_func")
        if not ok:
            return False, words
        ok, units = _run(scan_targets_func, "scan_targets_func")
        if not ok:
            return False, units
        bad_pii, n = [], 0
        for item in units or []:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                base, fname = item[0], item[1]
            elif isinstance(item, str):
                base, fname = "", item
            else:
                continue
            if fname in exclude_set:
                continue
            fpath = os.path.join(base, fname) if base else fname
            try:
                with open(fpath, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception:
                continue
            n += 1
            hits = _pii_hits(text, words or [])
            if hits:
                bad_pii.append("%s:%s" % (os.path.basename(fpath), "/".join(hits)))
        if not n:
            return False, "扫描 0 个文件（目标清单为空即红，不许当成通过）"
        return (not bad_pii), str(bad_pii[:5]) if bad_pii else "扫 %d 个文件无命中" % n
    return pii_check


def _pii_hits(text, extra_words=(), skip_unc=False):
    """PII命中检测核心函数。"""
    P_DRIVE = re.compile(r"[A-Za-z]:[\\/]")
    P_UNC = re.compile(r"\\\\[A-Za-z]")
    P_KEYBEGIN = re.compile(r"-----BEGIN")
    P_SK = re.compile(r"\bsk-[A-Za-z0-9]{6,}")

    items = [("drive_path", P_DRIVE), ("privkey_header", P_KEYBEGIN), ("secret_key_pat", P_SK)]
    if not skip_unc:
        items.append(("unc_path", P_UNC))

    hits = []
    for tag, pat in items:
        if pat.search(text):
            hits.append(tag)
    for w in extra_words:
        if len(w) >= 4 and w in text:
            hits.append("env_id(%s)" % w)
    return hits


def make_chapter_count_gate(zh_files_func=None, chapter_count_func=None):
    """章节数一致性模板 —— 对应 B5c/G03：分章件数必须等于章数。"""
    def ch_count_check():
        if zh_files_func is None or chapter_count_func is None:
            return _missing("zh_files_func", "chapter_count_func")
        ok, zfs = _run(zh_files_func, "zh_files_func")
        if not ok:
            return False, zfs
        ok, nc = _run(chapter_count_func, "chapter_count_func")
        if not ok:
            return False, nc
        return len(zfs or []) == int(nc or 0), "%d zhunze files vs %d chapters" % (len(zfs or []), int(nc or 0))
    return ch_count_check


def make_unique_ids_gate(clauses_func=None, id_of=None):
    """条款ID唯一性模板 —— 对应 G04。"""
    def unique_ids_check():
        ok, cl = _clauses(clauses_func)
        if not ok:
            return False, cl
        key = id_of or (lambda c: c.get("id"))
        seen, dups = set(), []
        for c in cl:
            cid = key(c)
            if cid in seen:
                dups.append(cid)
            seen.add(cid)
        return (not dups), "dup ids=%s" % str(dups[:5])
    return unique_ids_check


def make_block_broken_gate(clauses_func=None, id_of=None):
    """块连续性模板 —— 对应 G07：主条与其子条之间不得被别条款插队。"""
    def block_check():
        ok, cl = _clauses(clauses_func)
        if not ok:
            return False, cl
        key = id_of or (lambda c: c.get("id"))
        roots, broken = [], []
        for c in cl:
            r = str(key(c) or "").split("(")[0]
            if not roots or roots[-1] != r:
                if r in roots:
                    broken.append(r)
                roots.append(r)
        return (not broken), "broken blocks=%s" % str(broken[:5])
    return block_check


def make_missing_keys_gate(clauses_func=None, required=("id", "title", "body")):
    """关键字段检查模板 —— 对应 G06：每条须带齐 required 里的字段。"""
    def missing_check():
        ok, cl = _clauses(clauses_func)
        if not ok:
            return False, cl
        bad = [c.get("id", "?") for c in cl if any(k not in c for k in required)]
        return (not bad), "missing=%s" % str(bad[:5])
    return missing_check


def make_shell_clauses_gate(clauses_func=None, body_of=None, min_body=1):
    """空壳条款检测模板 —— 对应 G08：正文行数不足 min_body 即空壳。"""
    def shell_check():
        ok, cl = _clauses(clauses_func)
        if not ok:
            return False, cl
        get = body_of or (lambda c: c.get("body") or [])
        shells = [c.get("id", "?") for c in cl if len(list(get(c) or [])) < int(min_body)]
        return (not shells), "shell clauses=%s" % str(shells[:5])
    return shell_check


def make_broken_refs_gate(clauses_func=None, id_of=None, refs_of=None):
    """断链检测模板 —— 对应 G09/A4：条款引用的 id 必须在同一集合里存在。"""
    def refs_check():
        ok, cl = _clauses(clauses_func)
        if not ok:
            return False, cl
        kid = id_of or (lambda c: c.get("id"))
        refs = refs_of or (lambda c: re.findall(r"\b\d+\.\d+(?:\(\d+\))?\b", "\n".join(c.get("body") or [])))
        have = set(str(kid(c)) for c in cl)
        br = ["%s->%s" % (kid(c), r) for c in cl for r in (refs(c) or [])
              if str(r) != str(kid(c)) and str(r) not in have]
        return (not br), "broken refs=%s" % str(br[:5])
    return refs_check


def _clauses(clauses_func):
    """条款集合的统一取数入口：没给就红；给了但返回不是列表也算红（不把空当通过）。"""
    if clauses_func is None:
        return False, _missing("clauses_func")[1]
    ok, cl = _run(clauses_func, "clauses_func")
    if not ok:
        return False, cl
    if cl is None or not isinstance(cl, (list, tuple)):
        return False, "clauses_func 返回的不是列表（拿到 %s）" % type(cl).__name__
    return True, list(cl)
