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

"""Bumao XTGL · 三端等价性用例

判据是三件可复算实物，全绿才叫等价：
  C1 真实 import 解析 —— 三端 wrapper 各自在独立子进程里被装载后，
     回读 sys.modules["engine"].__file__，必须都指向本目录的 engine.py。
     解析结论由 Python 自己的 import 给出，不由本件复述 wrapper 源码得出。
  C2 同一份字节 —— 该内核文件由三端各自打开、各自 sha256，三值相同，
     并与本件读到的值相同。
  C3 wrapper 不含条款语义 —— 三端 wrapper 源码与内核 engine.py 里，
     不得出现任何一端条款的正文（标题与逐行 body 归一后原样命中）；
     同一行同时带该条款号即视为引用，按既定判据「只引用条款号不算违规」放行。

本件不再做什么（降级说明，勿回退成旧口径）：
  · 旧引擎端点已摘。归档件在源码里以字面名 engine.py 自读自身，而备份后缀
    importlib 不认作源文件（spec_from_file_location 返回 loader=None）——
    「新旧同判」在本仓库结构上跑不出来，本件不再声称能证它。
  · 旧引擎比对退到 --old-engine-audit，输出只作参考，一律不进结论。
    历史教训：90_lishi 归档件的 HERE/HX 锚点上移一级，它扫的是另一套磁盘状态，
    文件扫描类闸门会在空目标上轻松全绿——那是假绿。

反向用例每轮必跑，任何一条没被拦住，整体判 FAIL：
  R1 故意让一端指向旧引擎：沙盒里复制该端 wrapper、把 _kernel_dir 改成一份
     旧引擎字节（拷成 poison\\fake_kernel\\engine.py），真跑一次解析；
     判据必须给 FAIL，不许给「不可判定」。全程不在 10_rac 下写任何文件。
  R2 证明 C3 不是空洞绿：真条款正文裸写进源码必须被抓到，
     同一行带上条款号必须放行。
  R3 判据自测：路径分歧／字节分歧／正文命中／压根没 import engine／语料为空／完好，
     前四种必须 FAIL，语料为空不许判 pass。

设计约束（每条对应一个已发生过的缺陷，勿回退）：
  · 路径一律由 __file__ 运行时溯源，不写死盘符——内核文件写死绝对路径
    本身就违反它自己要检的去私人化规则。
  · PY 用 sys.executable，不写死解释器路径。
  · 装载 wrapper 要注入 PYTHONPATH=该端 10_rac：wrapper 里 import rules_db，
    R1 的沙盒件更甚——它的 __file__ 不在 10_rac，HERE 指不到规则包。
  · 探针没产出（超时／起不来）＝不可判定；解析到别处＝实物不等价。
    两者分开记，前者绝不写进 pass。
  · 语料为空时 C3 无从判定，不判通过（防空洞绿）。

退出码：0 = 实物判据全绿且反向用例全部被拦住；1 = 其余任何情况。

生效：2026-11-04 ｜ 判据改写：2026-11-06
      原版失效项与结论行解析回归另行留档。
"""

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))          # .../HX/kernel/bumao_core
KERNEL = os.path.dirname(HERE)                             # .../HX/kernel
HX = os.path.dirname(KERNEL)                               # .../HX
PY = sys.executable

# 端列表从 HX 目录结构发现：同时含 10_rac 与 20_view 的目录即为一端；不硬编码端名。
EDITIONS = tuple(sorted(
    d for d in os.listdir(HX)
    if os.path.isdir(os.path.join(HX, d, "10_rac"))
    and os.path.isdir(os.path.join(HX, d, "20_view"))
))

# C3 的比对粒度：条款行归一后至少这么长才纳入判据。
# 12 是实测选的——三端 wrapper 与内核 engine.py 在 12／20／28 三档都是 0 命中，
# 再放宽只会让短条款行从判据里漏掉。
_MIN_CLAUSE_TEXT_LEN = 12

_CLAUSE_HEAD_MARK = re.compile(u"^(（\\d+）|\\d+[.、)]|[a-z]\\.|[-*|｜>#＃]+)\\s*")
_MEANINGFUL = re.compile(u"[\\u4e00-\\u9fff]{4}|[A-Za-z]{10}")
_CLAUSE_ROOT = re.compile(u"^\\d+(?:\\.\\d+)*")

# 闸门行统一解析：状态可选方括号，其后为闸门 ID（B35a / G07 / A1 等）
_GATE_LINE = re.compile(r"^\s*\[?(PASS|FAIL|OK|ERROR|WARN)\]?\s+([A-Z]\d+[a-z]?)\b")
_STATUS_NORM = {"PASS": "PASS", "OK": "PASS", "FAIL": "FAIL", "ERROR": "FAIL", "WARN": "FAIL"}

NO_VERDICT = "NO VERDICT LINE"
# "FAIL (" 之前实测存在两个空格的真实形态（minimal 旧引擎末行 "FAIL  (2/16 gates red)"），
# 只认一个空格会把整轮 FAIL 读成「无结论行」，把可判的比对降级为不可判。
_VERDICT_RE = re.compile(r"^(\[结论\]|(NOT )?ALL PASS\b|FAIL\s+\()")

# wrapper 里那行内核路径声明——R1 改的就是它，改不到说明 wrapper 换了形状
_KERNEL_DIR_ANCHOR = ('_kernel_dir = os.path.abspath('
                      'os.path.join(HERE, "..", "..", "kernel", "bumao_core"))')

# 探针源码。写成临时文件而不是 python -c：让 sys.path[0] 落在探针目录，
# 与被测 wrapper 的解析路径互不干扰。
_PROBE_SRC = r'''# -*- coding: utf-8 -*-
import hashlib, json, sys, time
import importlib.util as u

wp, outp = sys.argv[1], sys.argv[2]
t0 = time.time()
rec = {"wrapper": wp, "exec_err": None, "corpus_err": None,
       "engine_file": None, "engine_sha": None, "rules_db": None,
       "n_clauses": None, "corpus": []}


def dump():
    rec["elapsed"] = round(time.time() - t0, 2)
    with open(outp, "w", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False))


try:
    spec = u.spec_from_file_location("_eq_probe_wrap", wp)
    mod = u.module_from_spec(spec)
    spec.loader.exec_module(mod)
except BaseException as e:              # 崩之前也可能已经拿到解析结果
    rec["exec_err"] = "%s: %s" % (type(e).__name__, e)

eng = sys.modules.get("engine")
if eng is not None and getattr(eng, "__file__", None):
    rec["engine_file"] = eng.__file__
    try:
        h = hashlib.sha256()
        with open(eng.__file__, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        rec["engine_sha"] = h.hexdigest()
    except Exception as e:
        rec["exec_err"] = (rec["exec_err"] or "") + " | sha %s: %s" % (type(e).__name__, e)
    try:
        dbm = eng._get_rules_db()
        db = dbm.index(dbm.load())
        rec["rules_db"] = (getattr(dbm, "__file__", None)
                           or "%s.%s" % (type(dbm).__module__, type(dbm).__name__)
                           + "\uff08\u52a8\u6001\u9002\u914d\u5668\uff0c\u65e0 __file__\uff09")
        rec["n_clauses"] = len(db["clauses"])
        rec["corpus"] = [[c["id"], c.get("title", "")] + list(c.get("body", []))
                         for c in db["clauses"]]
    except Exception as e:
        rec["corpus_err"] = "%s: %s" % (type(e).__name__, e)

dump()
'''


def parse_args():
    ap = argparse.ArgumentParser(description="三端等价性用例（口径：三件可复算实物）")
    ap.add_argument("edition", nargs="?", default="all",
                    choices=["all"] + list(EDITIONS),
                    help="测哪一端（默认 all；单端只核该端的 C1／C2，C3 语料取已探端并集）")
    ap.add_argument("--timeout", type=int, default=120,
                    help="单次探针超时秒数（默认 120；实测约 0.1s/端）")
    ap.add_argument("--old-engine-audit", action="store_true",
                    help="附带跑新旧引擎比对，结果只作参考、不进结论")
    ap.add_argument("--allow-archived", action="store_true",
                    help="审计模式下允许用 90_lishi 归档件（锚点上移一级，只报不判）")
    return ap.parse_args()


def edition_dir(edition):
    return os.path.join(HX, edition)


def rac_dir(edition):
    return os.path.join(edition_dir(edition), "10_rac")


def get_new_wrapper(edition):
    """新 wrapper 路径 —— 由目录实探，不写死文件名。"""
    d = rac_dir(edition)
    if not os.path.isdir(d):
        return None
    hits = sorted(f for f in os.listdir(d)
                  if f.startswith("BumaoXTGL_") and f.endswith("_v01.py")
                  and ".bak" not in f.lower())
    return os.path.join(d, hits[0]) if hits else None


def find_old_engine(edition):
    """旧引擎定位。返回 (path, kind, anchors_ok)。只读，不写。

    锚点判据留着，因为它决定归档件能不能当参考：旧引擎开头三行是
        HERE = dirname(abspath(__file__));  HX = dirname(HERE);  ROOTDIR = dirname(HX)
    只有脚本就在 10_rac 下时这三个锚点才指向正确产品目录；
    90_lishi 归档件整体上移一级，扫的是另一套磁盘状态。
    文件名必须含 ".bak"：10_rac 下还躺着 engine_shared.py 与 engine_wrapper_v2.py
    两个活体死文件，只按前缀 "engine" 匹配会把它们当旧引擎选中。
    """
    d = rac_dir(edition)
    cands = []
    if os.path.isdir(d):
        for f in os.listdir(d):
            if not f.startswith("engine") or ".bak" not in f.lower():
                continue
            full = os.path.join(d, f)
            if os.path.isfile(full):
                cands.append((os.path.getmtime(full), full))
    if cands:
        cands.sort(reverse=True)
        return cands[0][1], "10_rac 内 .bak（%s）· 锚点正确" % os.path.basename(cands[0][1]), True

    archived = os.path.join(edition_dir(edition), "90_lishi",
                            "old_engine_bumago_xtgl_%s_v01.py" % edition)
    if os.path.isfile(archived):
        return archived, "90_lishi 归档件 · 锚点上移一级（HERE=90_lishi）", False

    return None, None, False


def canonical_engine():
    """判据 C1 的唯一靶子：本件所在的内核正身，由 __file__ 溯源。"""
    return os.path.abspath(os.path.join(HERE, "engine.py"))


def _norm(p):
    return os.path.normcase(os.path.abspath(p)) if p else None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_text(path):
    return io.open(path, encoding="utf-8", errors="replace").read()


def _write_text(path, text):
    io.open(path, "w", encoding="utf-8", newline="\n").write(text)


def _workdir():
    return tempfile.mkdtemp(prefix="bumao_eq_")


def _probe_script(workdir):
    p = os.path.join(workdir, "_eq_probe.py")
    _write_text(p, _PROBE_SRC)
    return p


def probe_wrapper(wrapper, timeout, workdir, label=None, deps_dir=None):
    """子进程装载 wrapper，回读它自己解析到的内核与规则包。

    deps_dir 是给 wrapper 兜底找 rules_db 的目录：真端就是它自己的 10_rac；
    R1 的沙盒件必须显式传该端 10_rac，否则它在 import rules_db 就崩，
    拿不到「解析到了旧引擎」这条证据。
    """
    rac = deps_dir or os.path.dirname(os.path.abspath(wrapper))
    script = _probe_script(workdir)
    payload = os.path.join(workdir, "probe_%s.json" % hashlib.sha1(
        (_norm(wrapper) + "|" + (label or "")).encode("utf-8", "replace")).hexdigest()[:12])
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = rac + os.pathsep + env.get("PYTHONPATH", "")

    rec = {"label": label or os.path.basename(wrapper), "wrapper": wrapper,
           "deps_dir": rac, "engine_file": None, "engine_sha": None,
           "rules_db": None, "n_clauses": None, "corpus": [],
           "exec_err": None, "corpus_err": None, "probe_err": None, "elapsed": None}
    try:
        # -B：探针只读不动 10_rac，连 importlib 的字节码缓存也不落在别人目录里
        r = subprocess.run([PY, "-X", "utf8", "-B", script, wrapper, payload],
                           cwd=rac if os.path.isdir(rac) else workdir,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        rec["probe_err"] = "探针超时（%ds 内未返回）" % timeout
        return rec
    except Exception as e:
        rec["probe_err"] = "探针未能启动：%s: %s" % (type(e).__name__, e)
        return rec
    if not os.path.exists(payload):
        tail = [x for x in (r.stderr or "").splitlines() if x.strip()][-3:]
        rec["probe_err"] = "探针无产出 rc=%s ｜ %s" % (r.returncode, " / ".join(tail)[:220])
        return rec
    try:
        rec.update(json.loads(_read_text(payload)))
    except Exception as e:
        rec["probe_err"] = "探针产出不可读：%s: %s" % (type(e).__name__, e)
    return rec


def _compact(s):
    """条款行归一：去行首序号标记、去全部空白。只用于比对，不改原意。"""
    joined = u" ".join(str(s).split()).strip()
    return u"".join(_CLAUSE_HEAD_MARK.sub(u"", joined).split())


def clause_items(corpus, min_len=_MIN_CLAUSE_TEXT_LEN):
    """[(条款号, 归一正文)]，跨条去重。标题与 body 行同等纳入。"""
    out, seen = [], set()
    for row in corpus:
        cid = row[0]
        for raw in row[1:]:
            t = _compact(raw)
            if len(t) < min_len or t in seen:
                continue
            if not _MEANINGFUL.search(t):        # 纯数字／纯符号行不做判据
                continue
            seen.add(t)
            out.append((cid, t))
    return out


def scan_clause_semantics(source_text, items):
    """C3 判据本体：条款正文原样出现在源码里即违规；同行带条款号视为引用，放行。"""
    lines = source_text.splitlines()
    compact = [u"".join(l.split()) for l in lines]
    bad = []
    for cid, text in items:
        for i, cl in enumerate(compact):
            if text not in cl:
                continue
            m = _CLAUSE_ROOT.match(cid)
            root = m.group(0) if m else cid
            if root and root in lines[i]:        # 引用该条款号，不判违规
                break
            bad.append({"clause": cid, "line": i + 1, "text": text[:80],
                        "source": lines[i].strip()[:110]})
            break
    return bad


def judge_three_ends(records, items, engine_src):
    """三件实物的判据本体：给探针记录与语料，给结论。纯函数，反向用例走同一把尺子。

    hard = 实物偏离（解析到别处／没解析到 engine／字节不同／源码含条款正文）
    soft = 拿不出实物（探针不可用／语料为空）
    status = fail（有 hard）＞ inconclusive（只有 soft）＞ pass（两者都无）
    """
    hard, soft = [], []
    canon = _norm(canonical_engine())
    mine = sha256_file(canon)

    usable = []
    for r in records:
        if r.get("probe_err"):
            soft.append("探针不可用 · %s：%s" % (r["label"], r["probe_err"]))
            continue
        usable.append(r)

    for r in usable:
        got = _norm(r.get("engine_file"))
        if got is None:
            hard.append("C1 %s 未解析到任何 engine 模块（exec_err=%s）"
                        % (r["label"], (r.get("exec_err") or "-")[:140]))
        elif got != canon:
            hard.append("C1 %s 的内核解析到别处：%s（应为 %s）"
                        % (r["label"], r["engine_file"], canon))

    shas = [(r["label"], r["engine_sha"]) for r in usable if r["engine_sha"]]
    distinct = set(s for _l, s in shas)
    if distinct and distinct != {mine}:
        hard.append("C2 各端读到的 SHA256 与本件不一致：%s ｜ 本件=%s"
                    % (sorted(set("%s=%s" % kv for kv in shas)), mine[:16]))
    if len(distinct) > 1:
        hard.append("C2 端与端读到的 SHA256 互不相同：%s"
                    % sorted(x[:16] for x in distinct))

    if not items:
        soft.append("C3 语料为空（各端条款数 %s），无实物可检，不判通过"
                    % [(r["label"], r.get("n_clauses")) for r in usable])
    else:
        for r in usable:
            hits = scan_clause_semantics(_read_text(r["wrapper"]), items)
            if hits:
                hard.append("C3 %s 源码含条款正文 %d 处 ｜ 首处 %s@L%d：%s"
                            % (r["label"], len(hits), hits[0]["clause"],
                               hits[0]["line"], hits[0]["source"][:70]))
        hits = scan_clause_semantics(engine_src, items)
        if hits:
            hard.append("C3 内核 engine.py 含条款正文 %d 处 ｜ 首处 %s@L%d：%s"
                        % (len(hits), hits[0]["clause"], hits[0]["line"],
                           hits[0]["source"][:70]))

    status = "fail" if hard else ("inconclusive" if soft else "pass")
    return {"status": status, "hard": hard, "soft": soft,
            "corpus_items": len(items), "canonical": canonical_engine(), "sha": mine}


def run_three_ends(editions, timeout, workdir, cache):
    """逐端起独立探针——同进程装载三端会让 import 缓存污染解析证据。
    cache 里存 (端, 语料)，供 C3 取并集。"""
    del cache[:]
    records = []
    for ed in editions:
        w = get_new_wrapper(ed)
        if not w:
            records.append({"label": ed, "wrapper": None, "engine_file": None,
                            "engine_sha": None, "rules_db": None, "n_clauses": None,
                            "corpus": [], "exec_err": None,
                            "probe_err": "10_rac 下找不到 BumaoXTGL_*_v01.py"})
            continue
        rec = probe_wrapper(w, timeout, workdir, label=ed)
        rec["edition"] = ed
        records.append(rec)
        cache.append((ed, rec.get("corpus") or []))
    return records


def corpus_from_cache(cache):
    return [row for _ed, rows in cache for row in rows]


def _pick_donor(records):
    """自测用的供体记录：挑一条真正拿到语料的。"""
    for r in records:
        if not r.get("probe_err") and r.get("corpus"):
            return r
    return None


def selftest_judge(donor, items, engine_src, workdir):
    """R3：判据自测。合成记录只验尺子本身，不拿它充当三端实物证据。"""
    if donor is None:
        return ["R3 无可用供体记录（该端探针全部不可用），判据自测跑不成"]
    if not items:
        return ["R3 语料为空，判据自测跑不成"]
    poison_dir = os.path.join(workdir, "r3")
    os.makedirs(poison_dir)

    off = dict(donor)
    off["engine_file"] = os.path.join(poison_dir, "other_kernel.py")

    tsha = dict(donor)
    tsha["engine_sha"] = "0" * 64

    twrap = dict(donor)
    twrap["wrapper"] = os.path.join(poison_dir, "wrap_with_clause.py")
    _write_text(twrap["wrapper"], u"# 有人把条款正文抄进了代码\nX = u'%s'\n" % items[0][1])

    noeng = dict(donor)
    noeng["engine_file"] = None
    noeng["engine_sha"] = None

    cases = [
        ("内核解析指向别处", [off], items, "fail"),
        ("内核字节被篡改", [tsha], items, "fail"),
        ("源码含条款正文", [twrap], items, "fail"),
        ("压根没 import engine", [noeng], items, "fail"),
        ("语料为空", [dict(donor)], [], "inconclusive"),
        ("完好记录", [dict(donor)], items, "pass"),
    ]
    bad = []
    for name, recs, its, want in cases:
        got = judge_three_ends(recs, its, engine_src)
        if got["status"] != want:
            bad.append("R3 %s：期望 %s 实得 %s ｜ hard=%s soft=%s"
                       % (name, want, got["status"], got["hard"][:1], got["soft"][:1]))
    print("[自测] R3 判据自测 %d 例（路径／字节／正文／无内核／空语料／完好）%s"
          % (len(cases), "全过" if not bad else "有缺陷"))
    return bad


def selftest_c3(items):
    """R2：证明 C3 抓得住、也证明引用豁免不误伤。两行都来自真条款正文。"""
    if not items:
        return ["R2 语料为空，C3 无从自测"]
    cid, text = max(items, key=lambda kv: len(kv[1]))
    root = _CLAUSE_ROOT.match(cid).group(0)
    bad = []
    if not scan_clause_semantics(u"NOTE = u'%s'\n" % text, [(cid, text)]):
        bad.append("R2a 条款正文裸写进源码却未被 C3 抓到（判据是空的）")
    if scan_clause_semantics(u"NOTE = u'按 %s 执行：%s'\n" % (root, text), [(cid, text)]):
        bad.append("R2b 同行带条款号的引用被 C3 误判为违规（判据过严）")
    print("[自测] R2 C3 双向用例（条款 %s，正文 %d 字）%s"
          % (cid, len(text), "已验：抓得住裸抄、放得过引用" if not bad else "有缺陷"))
    return bad


def reverse_case_old_engine(timeout, workdir, items, engine_src):
    """R1：故意让一端指向旧引擎，判据必须给 FAIL（不许给不可判定）。

    三步全在沙盒：复制 wrapper → 改 _kernel_dir → 把旧引擎字节拷成
    fake_kernel\\engine.py。10_rac 下一个字节都不写。
    """
    # 不写死端名：在发现的端里挑第一个同时具备 wrapper 与旧引擎件的端。
    ed = ""
    for _cand in EDITIONS:
        _w = get_new_wrapper(_cand)
        _old, _kind, _anchors = find_old_engine(_cand)
        if _w and _old:
            ed, wrapper, rac = _cand, _w, rac_dir(_cand)
            old_engine, old_kind = _old, _kind
            break
    if not ed:
        return False, "各端都找不到 wrapper＋旧引擎，反向用例无法构造"
    src = _read_text(wrapper)
    if _KERNEL_DIR_ANCHOR not in src:
        return False, "wrapper 里找不到内核路径声明锚点（形状已变），反向用例无法构造"

    fak = os.path.join(workdir, "poison", "fake_kernel")
    os.makedirs(fak)
    shutil.copyfile(old_engine, os.path.join(fak, "engine.py"))
    poisoned = os.path.join(workdir, "poison", "wrap_poisoned.py")
    _write_text(poisoned, src.replace(_KERNEL_DIR_ANCHOR,
                                      '_kernel_dir = r"%s"' % fak, 1))

    rec = probe_wrapper(poisoned, timeout, workdir,
                        label="R1·%s 指向旧引擎" % ed, deps_dir=rac)
    if rec.get("probe_err"):
        return False, "反向用例探针自身不可用：%s" % rec["probe_err"]
    verdict = judge_three_ends([rec], items, engine_src)
    caught = (verdict["status"] == "fail"
              and _norm(rec.get("engine_file")) != _norm(canonical_engine()))
    why = ("解析落在 %s ｜ sha=%s ｜ exec_err=%s ｜ 判据=%s ｜ 偏离=%s ｜ 旧引擎=%s"
           % (rec.get("engine_file"), (rec.get("engine_sha") or "-")[:16],
              (rec.get("exec_err") or "-")[:60], verdict["status"],
              (verdict["hard"][:1] or ["-"])[0][:110], old_kind))
    return caught, why


def print_verdict(records, items, result, cache):
    print("\n  --- 三件实物 ---")
    print("    C1 内核正身（本件 __file__ 溯源）：%s" % result["canonical"])
    print("    C2 本件读到的内核 SHA256：%s" % result["sha"][:32])
    for r in records:
        print("    %-10s wrapper=%s" % (r["label"], r.get("wrapper") or "-"))
        if r.get("probe_err"):
            print("                 探针不可用：%s" % r["probe_err"][:200])
            continue
        print("             内核解析=%s" % (r.get("engine_file") or "（未解析到 engine）"))
        print("             该端读到 sha=%s ｜ 条款数=%s ｜ 规则包=%s%s"
              % ((r.get("engine_sha") or "-")[:32], r.get("n_clauses"),
                 r.get("rules_db") or "-",
                 "" if not r.get("exec_err") else " ｜ exec_err=%s" % r["exec_err"][:90]))
    print("    C3 语料：归一后纳入判据的条款正文 %d 行（各端条款数 %s）"
          % (len(items), ", ".join("%s=%d" % (e, len(c)) for e, c in cache)))
    if result["hard"]:
        print("\n  --- 实物偏离（判 FAIL）---")
        for p in result["hard"]:
            print("      · %s" % p[:300])
    if result["soft"]:
        print("\n  --- 拿不出实物（判不可判定）---")
        for p in result["soft"]:
            print("      · %s" % p[:300])


# ---------- 以下属已摘除端点的遗留比对：只在 --old-engine-audit 下运行，不进结论 ----------

def run_check(script, edition, timeout):
    """跑 check --strict。归档旧引擎 import rules_db 而自身在 90_lishi，
    故必须注入 PYTHONPATH 并把 cwd 设在 10_rac。"""
    rac = rac_dir(edition)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = rac + os.pathsep + env.get("PYTHONPATH", "")
    try:
        r = subprocess.run([PY, script, "check", "--strict"],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=timeout, cwd=rac, env=env)
        return r.stdout or "", r.stderr or "", r.returncode, False
    except subprocess.TimeoutExpired as e:
        return (e.stdout or "" if isinstance(e.stdout, str) else "",
                "TIMEOUT after %ds" % timeout, None, True)
    except Exception as e:
        return "", "EXC %s" % e, None, False


def parse_gates(stdout):
    """把 check 输出解析成 {闸门ID: (状态, 原始行)}。兼容两种格式。"""
    gates = {}
    for line in stdout.split("\n"):
        m = _GATE_LINE.match(line)
        if m:
            gates[m.group(2)] = (_STATUS_NORM[m.group(1)], line.strip())
    return gates


def overall_verdict(stdout):
    """整轮结论：只认结论行，从尾向前取第一条命中的。

    旧实装从头扫任意含「ALL PASS」的行，而闸门标签里也有这四字
    （B31 接入凭据强制（当日留档含 whoami + ALL PASS））
    → 给 rc=1、[结论] FAIL 3 项 的轮次贴了 ALL PASS。守「防空洞绿」的工具自己出洞。
    """
    for line in reversed(stdout.split("\n")):
        t = line.strip()
        if not _VERDICT_RE.match(t):
            continue
        if "ALL PASS" in t and "非" not in t and "NOT" not in t.upper():
            return "ALL PASS"
        return "NOT ALL PASS"
    return "NO OUTPUT" if not stdout.strip() else NO_VERDICT


def selftest_verdict():
    """回归用例：结论行之下还有 FAIL 项时绝不允许读成 ALL PASS。
    审计模式仍用这套解析，留着是别让已修的洞再开。"""
    trap = ("  PASS  B31 接入凭据强制（当日留档含 whoami + ALL PASS）  :: 当日无留档，跳过\n"
            "  FAIL  B21 迁移残留为 0\n"
            "  [结论] FAIL 3 项 —— 禁止记账\n")
    cases = [
        (trap, "NOT ALL PASS"),
        ("  PASS  B1 x\n\n[结论] ALL PASS（A段 9 项 + B段 17 项） —— 允许记账\n", "ALL PASS"),
        ("  PASS  B1 x\n\nFAIL (1/70 gates red)\n", "NOT ALL PASS"),
        # 真机取样：minimal 旧引擎 2026-11-05 17:0x 原样输出，FAIL 后两个空格
        ("  [PASS] G01  x\n  [FAIL] G03  x\n\nFAIL  (2/16 gates red)\n", "NOT ALL PASS"),
        ("  PASS  B1 x\n\n[结论] FAIL  (1/70 gates red)\n", "NOT ALL PASS"),
        ("  PASS  B1 x\n\nALL PASS (70/70)\n", "ALL PASS"),
        ("", "NO OUTPUT"),
        ("  PASS  B1 x\n", NO_VERDICT),
    ]
    for text, want in cases:
        got = overall_verdict(text)
        assert got == want, "结论行解析回归：期望 %s 实得 %s" % (want, got)
    print("[自测] 结论行解析 %d 例全过（防回归）" % len(cases))


def audit_old_engine(edition, timeout, allow_archived=False):
    """参考信息：新旧引擎在同一磁盘状态上的闸门差。返回值只印，不参与结论。"""
    old_engine, old_kind, anchors_ok = find_old_engine(edition)
    new_wrapper = get_new_wrapper(edition)
    if not old_engine or not new_wrapper:
        return "缺旧引擎或新 wrapper，无从参考"
    if not anchors_ok and not allow_archived:
        return "旧引擎锚点上移一级（%s），比对会得到假绿，未跑" % old_kind
    o_out, _o_err, _o_rc, o_to = run_check(old_engine, edition, timeout)
    n_out, _n_err, _n_rc, n_to = run_check(new_wrapper, edition, timeout)
    if o_to or n_to:
        return "超时（旧=%s 新=%s），未跑完" % (o_to, n_to)
    og, ng = parse_gates(o_out), parse_gates(n_out)
    if not og or not ng:
        return "有一侧解析到 0 闸（旧 %d／新 %d），参考值无意义" % (len(og), len(ng))
    return ("旧 %d 闸／新 %d 闸｜旧有新无 %s｜判定翻转 %s｜整轮 旧=%s 新=%s｜旧件=%s"
            % (len(og), len(ng), sorted(set(og) - set(ng))[:8],
               [g for g in sorted(set(og) & set(ng)) if og[g][0] != ng[g][0]][:8],
               overall_verdict(o_out), overall_verdict(n_out), old_kind))


def main():
    args = parse_args()
    selftest_verdict()

    editions = list(EDITIONS) if args.edition == "all" else [args.edition]
    workdir = _workdir()
    bad = []
    print("三端等价性用例 · 三件实物判据 · %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    print("HX = %s" % HX)
    print("PY = %s" % PY)
    print("被测端 = %s ｜ 沙盒 = %s（反向用例在此造件，不碰 10_rac）"
          % (", ".join(editions), workdir))

    try:
        cache = []
        records = run_three_ends(editions, args.timeout, workdir, cache)
        items = clause_items(corpus_from_cache(cache))
        engine_src = _read_text(canonical_engine())

        result = judge_three_ends(records, items, engine_src)
        print_verdict(records, items, result, cache)
        print("\n  三件实物判据：%s"
              % {"pass": "PASS 等价", "fail": "FAIL 不等价",
                 "inconclusive": "INCONCLUSIVE 不可判定"}[result["status"]])
        if result["status"] != "pass":
            bad.append("三件实物判据 = %s" % result["status"])

        for msg in (selftest_judge(_pick_donor(records), items, engine_src, workdir)
                    + selftest_c3(items)):
            print("  [自测红] %s" % msg)
            bad.append(msg)

        caught, why = reverse_case_old_engine(args.timeout, workdir, items, engine_src)
        print("\n  反向用例 R1（让宿主指向旧引擎）：%s"
              % ("已拦住 → 判 FAIL" if caught else "未拦住"))
        print("      %s" % why[:320])
        if not caught:
            bad.append("R1 未被拦住：%s" % why[:180])

        if args.old_engine_audit:
            print("\n  --- 旧引擎比对（仅参考，不进结论）---")
            for ed in editions:
                print("    %-10s %s" % (ed, audit_old_engine(ed, args.timeout,
                                                            args.allow_archived)))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    print("\n" + "=" * 66)
    print("  结论：%s" % ("三端等价（C1+C2+C3 全绿）且反向用例全部被拦住"
                          if not bad else "不等价／不可判定／反向用例失守"))
    for p in bad:
        print("      · %s" % p[:300])
    print("  口径：本件只证「三端共用同一内核且 wrapper 不含条款语义」，"
          "不再声称能证新旧同判。")
    return 0 if not bad else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
