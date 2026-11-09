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

"""Bumao Core · Unified Kernel CLI
一核三端——同一份 engine.py，通过注入 rules_db 适配不同产品。
子命令：whoami [--full] / check [--strict] [--quick] / audit / bump <L1|L2|L3> /
        show <id> / selftest [--kernel] / refresh
"""

import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time


class Out(object):
    """检查输出——与所有端原 engine.py 完全兼容"""
    def __init__(self):
        self.rows = []
    def add(self, sec, cid, ok, name, msg=""):
        self.rows.append((sec, cid, ok, name, str(msg)))
    def count(self, sec):
        return len([r for r in self.rows if r[0] == sec])
    def fails(self):
        return [r for r in self.rows if not r[2]]

    def fail_count(self):
        return sum(1 for r in self.rows if not r[2])

    def emit(self):
        lmap = {"A": "[A] 真身结构", "B": "[B] 视图、实物与去私人化", "Z": "[Z] 重大错误册"}
        for sk in ["A", "B", "Z"]:
            rows = [r for r in self.rows if r[0] == sk]
            if not rows: continue
            print(lmap.get(sk, sk))
            for _, cid, ok, name, msg in rows:
                print("  %s  %-4s %s" % ("PASS" if ok else "FAIL", cid, name) + ("  :: %s" % msg if msg else ""))


def _safe(fn, label="gate"):
    try:
        result = fn()
        if isinstance(result, tuple) and len(result) >= 2: return bool(result[0]), str(result[1])
        return bool(result), ""
    except Exception as e:
        return False, "%s raised %r" % (label, e)


# ========== Command implementations ==========

def _power_line():
    """11.54（1）电量行：直读 Win32 GetSystemPowerStatus，读不到就如实说读不到。
    修正读数口径：SYSTEM_POWER_STATUS 的字节序是
    ACLineStatus／BatteryFlag／BatteryLifePercent／SystemStatusFlag，原声明把第 2 字节当百分数，
    于是打印出来的是 BatteryFlag 位掩码（插电满电＝1，看着像 1%）；
    未插电时 ACLineStatus＝0 而非 2，原写法会退成「电源状态未知」。
    BatteryLifePercent 仍可能是 255（未知），>100 一律打「未知」不猜数。"""
    try:
        import ctypes

        class _PS(ctypes.Structure):
            _fields_ = [("ACLineStatus", ctypes.c_ubyte),
                        ("BatteryFlag", ctypes.c_ubyte),
                        ("BatteryLifePercent", ctypes.c_ubyte),
                        ("SystemStatusFlag", ctypes.c_ubyte),
                        ("BatteryLifeTime", ctypes.c_int),
                        ("BatteryFullLifeTime", ctypes.c_int)]

        ps = _PS()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(ps)):
            return "电量：GetSystemPowerStatus 调用失败，未读到"
        src = "插电" if ps.ACLineStatus == 1 else ("电池" if ps.ACLineStatus == 0 else "电源状态未知")
        pct = "未知" if ps.BatteryLifePercent > 100 else "%d%%" % ps.BatteryLifePercent
        tail = "" if ps.BatteryLifeTime >= 0 else "，剩余寿命不可读"
        return "电量：%s（%s%s）" % (pct, src, tail)
    except Exception as e:
        return "电量：读取失败（%r）——11.54（1）须手动核" % e


def _daiban_line():
    """11.54（4）周期待办行：口径与宿主经 rules_db 注入的 daiban 成员同源（宿主注入时即 daiban.parse），
    但比 B30 多报「今日到期」——B30 判逾期才 FAIL，当日到期不红；
    11.54（4）要的是当轮看见它，所以这里两类都列。"""
    import time
    today = (time.localtime().tm_year, time.localtime().tm_mon, time.localtime().tm_mday)
    _db = getattr(_get_rules_db(), "daiban", None)  # 内核不再按全局名 import daiban
    _dt = getattr(_db, "_date", None)
    if _db is None or _dt is None or not hasattr(_db, "parse"):
        return "周期待办：宿主 rules_db 未注入 daiban 成员（须含 parse／_date）——须手读宿主规程目录下 daiban_zongbiao.txt"
    try:
        _h, rows = _db.parse()
    except Exception as e:
        return "周期待办：读总表失败（%r）" % e
    over, due = [], []
    for r in rows:
        if len(r) < 8:
            continue
        if (r[6] or "").strip() in ("已闭环", "已停用", "已完成"):
            continue
        dd = _dt(r[5])
        if dd is None or not hasattr(dd, "year"):
            continue
        ymd = (dd.year, dd.month, dd.day)
        tag = "%s %s（到期 %s）" % (r[0], (r[1] or "")[:14], r[5])
        if ymd < today:
            over.append(tag)
        elif ymd == today:
            due.append(tag)
    parts = []
    if over:
        parts.append("逾期 %d 项：%s" % (len(over), "；".join(over[:3])))
    if due:
        parts.append("今日到期 %d 项：%s" % (len(due), "；".join(due[:3])))
    return "周期待办：" + ("、".join(parts) if parts else "无逾期、无今日到期")


def _import_gate_registry(kdir=None):
    """导入同目录 gate_registry：既支持包内相对导入，也支持 sys.path.insert 的扁平导入。

    2026-11-09：内核新增 pyproject/__init__.py 后，`import bumao_core.engine` 与
    `sys.path.insert(...); import engine` 两种加载方式都必须可用，故统一从这里取模块。
    """
    try:
        from . import gate_registry as _gr
        return _gr
    except ImportError:
        pass
    try:
        import gate_registry as _gr
        return _gr
    except ImportError:
        if kdir:
            sys.path.insert(0, kdir)
        import gate_registry as _gr
        return _gr


def cmd_whoami(full=False):
    try:
        dbm = _get_rules_db()
        meta = dbm.load_meta()
        db = dbm.index(dbm.load())
        name = meta.get("name", "")
        ver = meta.get("version", "0.0")
        effective = meta.get("effective", "?")
        clauses = db["clauses"]
        chapters = db["chapters"]
        # Determine root from the injected rules_db module (it sets ROOT/META_PATH etc)
        here = os.path.dirname(os.path.abspath(__file__))
        product_root = ""
        try:
            if hasattr(dbm, 'ROOT'):
                product_root = dbm.ROOT
            elif hasattr(dbm, '_inner') and hasattr(dbm._inner, 'ROOT'):
                product_root = dbm._inner.ROOT
            elif hasattr(dbm, 'HERE'):
                product_root = dbm.HERE
            else:
                product_root = os.path.dirname(here)
        except Exception:
            pass
        if not product_root:
            product_root = os.path.dirname(here)
        print("%s v%s (effective %s)" % (name, ver, effective))
        print("root : %s" % product_root)
        print("rules: %d clauses across %d chapters" % (len(clauses), len(chapters)))
        # 11.54(3) 接入凭据两行（用户 2026-11-05 裁定03）。
        # 内核不持有渲染器，漂移只能向宿主取：先看注入的 rules_db 有没有 check_drift，
        # 再退回宿主已导入的 render 模块（三端 wrapper 都 `import render as ...`）。
        # 取不到就如实说取不到，绝不打假数 —— 裁定03 约束「漂移必须真算」。
        drift_fn = getattr(dbm, "check_drift", None)
        if not callable(drift_fn):
            for _mod_name in ("render", "rules_render"):
                _mod = sys.modules.get(_mod_name)
                if _mod is not None and callable(getattr(_mod, "check_drift", None)):
                    drift_fn = _mod.check_drift
                    break
        drift = None
        if callable(drift_fn):
            try:
                drift = list(drift_fn() or [])
            except Exception as e:
                print("视图漂移：计算失败（%r）" % e)
        else:
            print("视图漂移：宿主未提供 check_drift，无法计算")
        if drift is not None:
            print("视图漂移：%d 处" % len(drift))
            print("接入状态：%s" % ("已接入（可开工）" if not drift
                                    else "未接入（先 render.py write）"))
        else:
            print("接入状态：未就绪（漂移未算出）")
        print(_power_line())
        print(_daiban_line())
        # 入口名从 sys.argv[0] 取，不写死 engine.py。
        # 原写法 print("gates: run `python engine.py check --strict`") 在统一内核落地后
        # 指向一个三端 10_rac 下都不存在的文件（旧引擎已归档 90_lishi），
        # 等于内核自己制造第二个入口口径（单一入口原则）。
        # 端无关：内核不知道端身份，只能报实际被调用的那个脚本名。
        _entry_name = os.path.basename(sys.argv[0]) if (sys.argv and sys.argv[0]) else "<wrapper>.py"
        print("gates: run `python %s check --strict`" % _entry_name)
        if full:
            # --full 只追加诊断行；不带 --full 时输出与历史版本逐字一致。
            _rules_dir = getattr(dbm, "RULES_DIR", "") or getattr(dbm, "ZH", "")
            print("[full] 内核路径：%s" % here)
            print("[full] Python：%s" % sys.version.split()[0])
            print("[full] 规则目录：%s" % (_rules_dir or "<宿主未暴露>"))
            print("[full] 子命令：whoami / check / audit / bump / show / selftest / refresh")
    except Exception as e:
        import traceback; traceback.print_exc()
        print("[ERROR] whoami failed: %s" % e)
        return 1
    return 0


def cmd_audit():
    try:
        dbm = _get_rules_db()
        db = dbm.index(dbm.load())
        clauses = db["clauses"]; meta = db["meta"]; chapters = db["chapters"]
        n_body = sum(1 for c in clauses if c.get("nbody", 0) > 0)
        print("[审计] %s %s" % (meta.get("name",""), meta.get("version","")))
        print("  条款 %d / 分章 %d / 有正文 %d" % (len(clauses), len(chapters), n_body))
        dups = dbm.dup_ids(db)
        bb = dbm.block_broken(clauses)
        sc = dbm.shell_clauses(db)
        print("  重复 id   %d %s" % (len(dups), str(dups[:5])))
        print("  块断裂    %d %s" % (len(bb), str(bb[:5])))
        br = [c["id"] for c in clauses if c.get("broken_refs")]
        print("  断链      %d %s" % (len(br), str(br[:5])))
        print("  空壳      %d %s" % (len(sc), str(sc[:5])))
        for ch in chapters:
            print("  第%-2d章 %-32s %d 条" % (ch.get("ch",""), ch.get("chapter_title","")[:32], ch.get("n",0)))
    except Exception as e:
        import traceback; traceback.print_exc()
        print("[ERROR] audit failed: %s" % e)
        return 1
    return 0


def round_auth_verdict(baseline_files, current, ledger_text, today, auth_words=None):
    """A13 纯判据：本轮核心件改动是否引到当日用户授权原话。

    baseline_files: {relpath: {"sha":..., "entry": 授权条目号}}；首次见到的件按
    entry=0 纳入基线（无法追溯首见之前的改动，如实记 0，不假装已授权）。
    current: {relpath: sha}。返回 (ok, detail, new_files, seeded)。
    判据刻意要求：文件 basename 必须与授权词同属当日的同一条【第 N 号】条目，
    且条目号必须大于基线锁定的条目号——同一张旧授权不能永久给同一件续命。
    """
    base = dict(baseline_files or {})
    new = dict(base)
    changed = []
    seeded = 0
    for _rel, _sha in sorted((current or {}).items()):
        _old = new.get(_rel)
        if _old is None:
            new[_rel] = {"sha": _sha, "entry": 0}
            seeded += 1
        elif str(_old.get("sha") or "") != str(_sha):
            changed.append((_rel, _sha, _old))
    if not changed:
        return (True, "本轮无核心件改动（比对 %d 件，新纳入基线 %d 件）" % (
            len(current or {}), seeded), new, seeded)
    if not (ledger_text or "").strip():
        return (False, "有 %d 件核心件改动，但审批册为空，无从引授权原话" % len(changed),
                new, seeded)
    try:
        _gr = _import_gate_registry(kdir=os.path.dirname(os.path.abspath(__file__)))
    except ImportError as _e:
        return (False, "gate_registry 不可导入，授权闸无法判定：%r" % _e, new, seeded)
    bad = []
    for _rel, _sha, _old in changed:
        _hits = _gr.approval_covers_file(ledger_text, today, _rel, words=auth_words)
        _best = max([int(e.get("no") or 0) for e in _hits] or [0])
        _need = int(_old.get("entry") or 0)
        if not _hits:
            bad.append("%s：当日无点名授权" % _rel)
        elif _best <= _need:
            bad.append("%s：授权条目未推进（已锁 %d，当日最新 %d）" % (_rel, _need, _best))
        else:
            new[_rel] = {"sha": _sha, "entry": _best}
    if bad:
        return (False, "改而未授权 %d 件：%s" % (len(bad), "；".join(bad[:4])),
                new, seeded)
    return (True, "%d 件核心件改动均有当日点名授权原话（条目号已推进）" % len(changed),
            new, seeded)


def _sha256_file(path):
    _h = hashlib.sha256()
    with open(path, "rb") as _f:
        for _chunk in iter(lambda: _f.read(65536), b""):
            _h.update(_chunk)
    return _h.hexdigest()


def _round_scope(kdir, entry):
    """A13 判定范围：内核代码/契约/文档＋入口 wrapper＋本端 10_rac 与 20_view/web 核心件。"""
    kroot = os.path.dirname(kdir)
    hx = os.path.dirname(kroot)
    # 2026-11-09 修：单仓 clone 下本仓根即「区根」，再上一级会跳到仓外，
    # 于是 A10／A13 永远读不到本仓 30_taizhang 里的审批册结构，理由变成「无审批册」。
    # 若 kroot 自身带 30_taizhang，就以 kroot 为区根；三端布局（kernel 在上、区根在下）不受影响。
    if os.path.isdir(os.path.join(kroot, "30_taizhang")):
        hx = kroot
    scope = []
    for _d in (kdir, kroot):
        if not os.path.isdir(_d):
            continue
        for _f in sorted(os.listdir(_d)):
            _p = os.path.join(_d, _f)
            if os.path.isfile(_p) and _f.endswith((".py", ".json", ".md")):
                scope.append(_p)
    if entry and os.path.isfile(entry):
        scope.append(os.path.abspath(entry))
        _ent_dir = os.path.dirname(os.path.abspath(entry))
        _prod = os.path.dirname(_ent_dir)
        for _d in (_ent_dir, os.path.join(_prod, "20_view", "web")):
            if not os.path.isdir(_d):
                continue
            for _f in sorted(os.listdir(_d)):
                _p = os.path.join(_d, _f)
                if not os.path.isfile(_p):
                    continue
                if _f.endswith((".py", ".json", ".js")) or _f in (
                        "index.html", "setup.html", "tutorial.html"):
                    scope.append(_p)
    return sorted(set(scope)), hx


def _round_auth_gate(kdir, entry):
    """A13 本轮改动授权闸：自上次检查以来改过的核心件，必须引当日用户授权原文。

    立闸原因：Q001——存量 A8（形态）＋B60（重大错误册）都只校验交付物形态，
    没有任何一项校验「本轮改动是否经用户授权」，2026-11-04 才出现越界改 11 处。
    状态基线落在审批册同端的 00_meta，不进 30_taizhang（台账白名单只管 .txt）。
    """
    try:
        _gr = _import_gate_registry(kdir)
        scope, hx = _round_scope(kdir, entry)
        if not scope:
            return False, "A13 判定范围为空，无法证明本轮改动"
        ledger = _gr.find_approval_ledger(hx)
        if not ledger:
            return False, "找不到审批册（shenpi_jilu.txt），本轮改动无授权来源"
        with open(ledger, encoding="utf-8-sig") as _f:
            text = _f.read()
        _meta = os.path.join(os.path.dirname(os.path.dirname(ledger)), "00_meta")
        bpath = os.path.join(_meta, "a13_benlun_jizhun.json")
        base = {}
        if os.path.isfile(bpath):
            try:
                with open(bpath, encoding="utf-8-sig") as _f:
                    base = (json.load(_f) or {}).get("files") or {}
            except Exception as _e:
                return False, "A13 基线读取失败：%r" % _e
        current = {}
        skipped_cross_drive = 0
        _hx_drive = os.path.splitdrive(hx)[0].lower()
        for _p in scope:
            # 跨盘符的入口不在区根下：os.path.relpath 在 Windows 会抛 ValueError。
            # 这类件按「区根外入口」跳过，不参与本轮比对，只在结论里点名件数。
            if os.path.splitdrive(_p)[0].lower() != _hx_drive:
                skipped_cross_drive += 1
                continue
            current[os.path.relpath(_p, hx).replace("\\", "/")] = _sha256_file(_p)
        today = time.strftime("%Y-%m-%d")
        ok, detail, files_new, seeded = round_auth_verdict(base, current, text, today)
        if skipped_cross_drive:
            detail = "%s；跳过区根外入口 %d 件（与区根不同盘符）" % (detail, skipped_cross_drive)
        if ok and files_new != base:
            try:
                os.makedirs(_meta, exist_ok=True)
                tmp = bpath + ".tmp"
                with open(tmp, "w", encoding="utf-8", newline="\n") as _f:
                    json.dump({"updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                               "files": files_new}, _f,
                              ensure_ascii=False, indent=2, sort_keys=True)
                os.replace(tmp, bpath)
            except Exception as _e:
                return False, "A13 基线写入失败：%r" % _e
        return ok, "%s；%d 件在判" % (detail, len(files_new))
    except Exception as _e:
        return False, "A13 授权闸自身跑不起来：%r" % _e


def _auth_gate(kdir=None):
    """A10 版本变更授权闸（L2＋L3）。

    判据取自独立的审批册，不取自被改的代码／契约两件：
      L2 当日审批行必须含该版本号且带授权词的「用户批准原文」；
      L3 该版本号必须等于审批册最新授权版本（同轮双改代码+契约不能自证）。
    立闸原因 2026-11-07：版本曾被无授权漂到 2.2.1；C2 只比字符串，双改必绿。
    """
    kdir = kdir or os.path.dirname(os.path.abspath(__file__))
    try:
        _gr = _import_gate_registry(kdir)
        kroot = os.path.dirname(kdir)
        cpath = os.path.join(kroot, "kernel_contract.json")
        with open(cpath, encoding="utf-8-sig") as _f:
            _c = json.load(_f)
        declared = str((( _c.get("frozen_interfaces") or {}).get("core_version") or {})
                       .get("current_value") or "")
        changed_on = str((_c.get("meta") or {}).get("updated_at") or "")
        if not declared or not changed_on:
            return False, "契约缺 current_value 或 updated_at（判不了），A10 按 DENY 处理"
        ok, detail, _r = _gr.version_approval_check(declared, changed_on,
                                                   kroot)
        return ok, detail
    except Exception as _e:
        return False, "授权闸自身跑不起来：%r" % _e


def cmd_check(strict=False, quick=False):
    """Run all gates with unified Out class.

    quick=True 只跑 A 段结构闸：跳过宿主注入的 B/Z 段、防缩水对账与检查凭据写入，
    因此它不能替代 `check --strict`（结论行会明说）。
    """
    out = Out()

    try:
        dbm = _get_rules_db()
        db = dbm.index(dbm.load())
        meta = db["meta"]; clauses = db["clauses"]; chapters = db["chapters"]

        # --- A 段：基础结构闸 ---
        # A1: 真身可装载
        n_ch = len(chapters); n_cls = len(clauses); _zr = bool(meta.get("zero_rules")); _rd = getattr(dbm, "RULES_DIR", ""); _rf = [f for f in os.listdir(_rd) if f.endswith(".json")] if os.path.isdir(_rd) else None
        out.add("A", "A1", (n_ch > 0 and n_cls > 0) or (_zr and _rf == []), "真身可装载", "%d ch / %d cls%s" % (n_ch, n_cls, (" (zero_rules declared; rules_dir=%s rules_json=%s)" % (_rd, len(_rf) if _rf is not None else "unverifiable")) if _zr else ""))

        # A2: 条款id唯一
        dups = dbm.dup_ids(db)
        out.add("A", "A2", not dups, "条款id唯一", str(dups[:3]))

        # A3: 条款块连续
        bb = dbm.block_broken(clauses)
        out.add("A", "A3", not bb, "条款块连续", str(bb[:5]))

        # A4: 引用无断链
        br_count = sum(1 for c in clauses if c.get("broken_refs"))
        out.add("A", "A4", br_count == 0, "引用无断链", "broken_refs=%d" % br_count)

        # A5: 无空壳条款
        shells = dbm.shell_clauses(db)
        out.add("A", "A5", not shells, "无空壳条款", "shells=%d" % len(shells))

        # A6: 版本语法
        ver = meta.get("version", "")
        out.add("A", "A6", bool(re.match(r"^\d+\.\d+(\.\d+)?$", ver)), "版本语法", "ver=%s" % ver)

        # A7: 章号自0连续
        ch_nums = sorted([c["ch"] for c in chapters])
        out.add("A", "A7", ch_nums == list(range(len(chapters))), "章号自0连续", "chs=%s" % str(ch_nums[:5]))

        # A8: 章标题编号与章号一致
        badtitle = []
        for c in chapters:
            title = c.get("chapter_title", "").strip()
            ch_num = c.get("ch", -1)
            m = re.match(r"^(\d+)\.", title)
            if not m or int(m.group(1)) != ch_num:
                badtitle.append(ch_num)
        out.add("A", "A8", not badtitle, "章标题编号与章号一致", str(badtitle))

        # A9: 内核与入口脚本可编译 / 无 BOM / JSON 可解析
        # 立此闸的直接原因：2026-11-04 两起缺陷都靠人工扫描才发现，check 全程绿——
        #   ① PowerShell Set-Content -Encoding UTF8 给两端 wrapper 引入 UTF-8 BOM，
        #      致补充篇 附录A A2/A3 的官方复核命令 ast.parse 报 U+FEFF；
        #   ② test_equivalence.py L156 f-string 语法错，整文件不可导入，存放数小时无人察觉。
        # 同一病因（BOM）此前已发作过一次：kernel_contract change_log 1.0勘误 记过
        # 「PowerShell 重写引入 BOM 致 contract_test A 闸 json.loads 解析失败」。
        # 二次发作说明未落闸，故落为端无关的 A 段闸。见缺陷记录。
        # 端无关性：内核不知道端身份，入口脚本只能从 sys.argv[0] 取。
        _a9_bad = []
        _kdir = os.path.dirname(os.path.abspath(__file__))
        _a9_py = [os.path.join(_kdir, _f) for _f in sorted(os.listdir(_kdir))
                  if _f.endswith(".py")]
        _entry = os.path.abspath(sys.argv[0]) if (sys.argv and sys.argv[0]) else ""
        if _entry.endswith(".py") and os.path.isfile(_entry) and _entry not in _a9_py:
            _a9_py.append(_entry)          # 各端 wrapper
        for _p in _a9_py:
            _bn = os.path.basename(_p)
            try:
                with open(_p, "rb") as _fh:
                    _head = _fh.read(3)
                    _body = _head + _fh.read()
            except OSError as _e:
                _a9_bad.append("%s:读失败" % _bn)
                continue
            if _head == b"\xef\xbb\xbf":
                _a9_bad.append("%s:含UTF-8 BOM" % _bn)
            try:
                compile(_body.decode("utf-8-sig"), _p, "exec")
            except SyntaxError as _e:
                _a9_bad.append("%s:语法错L%s %s" % (_bn, _e.lineno, _e.msg))
            except UnicodeDecodeError:
                _a9_bad.append("%s:非UTF-8编码" % _bn)
        # JSON 可解析：内核目录自身 + 上一层 kernel\（kernel_contract.json 在那里；
        # 首次 BOM 事故正是它 json.loads 失败，只扫 bumao_core\ 会漏掉）
        _a9_js = []
        for _jd in (_kdir, os.path.dirname(_kdir)):
            if not os.path.isdir(_jd):
                continue
            for _f in sorted(os.listdir(_jd)):
                if _f.endswith(".json"):
                    _a9_js.append(os.path.join(_jd, _f))
        for _jp in _a9_js:
            try:
                with open(_jp, encoding="utf-8-sig") as _fh:
                    json.loads(_fh.read())
            except Exception as _e:
                _a9_bad.append("%s:JSON解析失败 %s" % (os.path.basename(_jp), str(_e)[:30]))
        out.add("A", "A9", not _a9_bad, "内核与入口可编译/无BOM/JSON可解析",
                ("%d py + %d json 全过" % (len(_a9_py), len(_a9_js)))
                if not _a9_bad else str(_a9_bad[:4]))

        # A10: 版本变更授权闸（L2＋L3）—— 改版本必须有当日审批行／用户授权原话；
        # 同一轮同时改代码与契约声明也必须被拦（判据取自独立审批册，见 _auth_gate）。
        _a10_ok, _a10_detail = _auth_gate(_kdir)
        out.add("A", "A10", _a10_ok, "版本变更授权闸（当日审批行＋授权原话）", _a10_detail)

        # A11: 真身绝对路径可达 —— 真身是最高事实源，条款里写死的绝对路径必须真实存在。
        # 只查指令性/定义性路径；历史叙述（存在理由／演练／旧称／历史）与占位符（<>）跳过，
        # 因为「当时目录确实叫旧名」属史实，改成活路径反而是造假。
        _a11_bad = []
        _rf_dir = _rd if os.path.isdir(_rd) else getattr(dbm, "ZH", "")
        if not os.path.isdir(_rf_dir):
            _a11_bad.append("rules_dir 不可用")
        else:
            _a11_pat = re.compile(r"[A-Za-z]:\\[A-Za-z0-9_\\\.\-]+")
            _a11_skip = ("存在理由", "演练", "旧称", "历史", "若该目录存在")
            def _a11_scan(o, _fn):
                if isinstance(o, dict):
                    for _v in o.values():
                        _a11_scan(_v, _fn)
                elif isinstance(o, list):
                    for _v in o:
                        _a11_scan(_v, _fn)
                elif isinstance(o, str):
                    if any(_w in o for _w in _a11_skip) or "<" in o or ">" in o:
                        return
                    for _m in _a11_pat.finditer(o):
                        _s = _m.group(0).rstrip(" \\.")
                        if len(_s) < 8 or ".." in _s:
                            continue
                        if not os.path.exists(_s):
                            _a11_bad.append("%s:%s" % (_fn, _s[:80]))
            for _zf in sorted(glob.glob(os.path.join(_rf_dir, "z*.json"))):
                try:
                    with open(_zf, encoding="utf-8-sig") as _fh:
                        _a11_scan(json.load(_fh), os.path.basename(_zf))
                except Exception as _e:
                    _a11_bad.append("%s:解析失败 %s" % (os.path.basename(_zf), str(_e)[:40]))
        out.add("A", "A11", not _a11_bad, "真身绝对路径可达",
                ("全部可达" if not _a11_bad else "缺 %d 处：%s" % (len(_a11_bad), str(_a11_bad[:3]))))

        # A12: 强制/限制条款与闸位接线（仅端内声明了 enforce_decl 时出现）
        # 判据：z 系条款里写了 gate 字段的，条款 id 必须存在、闸位必须已 register。
        # 没有该声明的端不出现本项，输出口径保持原样。
        _decl = getattr(dbm, "enforce_decl", None)
        if callable(_decl):
            try:
                _items = _decl()
            except Exception as _e:
                _items = [{"clause": "<enforce_decl>", "gate": ""}]
                print("[WARN] enforce_decl 读取失败：%r" % _e)
            _ids = set(c.get("id") for c in clauses)
            _bad = [x for x in _items
                    if x.get("clause") not in _ids or x.get("gate") not in _registered_gate_ids]
            out.add("A", "A12", not _bad, "强制/限制条款与闸位接线",
                    ("%d 条已声明，全部接到已注册闸位" % len(_items) if not _bad
                     else "接线缺口 %d 条：%s" % (len(_bad), str(_bad[:3]))))

        # A13: 本轮改动授权闸 —— 补上 A8（形态）＋B60（重大错误册）之间缺失的一环：
        # 本轮改过的核心件必须引当日用户授权原话，改而未授权即红。
        _a13_ok, _a13_detail = _round_auth_gate(_kdir, _entry)
        out.add("A", "A13", _a13_ok, "本轮改动须引用户授权原话", _a13_detail)

        # --- B 段：各端注入的闸门（quick 模式跳过） ---
        b_gates = [] if quick else _get_b_gates()
        if b_gates:
            for gid, fn, label in b_gates:
                try:
                    result = fn()
                    ok, detail = _safe(lambda: result, label)
                except Exception as e:
                    ok, detail = False, "%s raised %r" % (label, e)
                out.add("B", gid, ok, label, detail)

        # --- Z 段：重大错误册（quick 模式跳过） ---
        z_gates = [] if quick else _get_z_gates()
        if z_gates:
            for gid, fn, label in z_gates:
                try:
                    result = fn()
                    ok, detail = _safe(lambda: result, label)
                except Exception as e:
                    ok, detail = False, "%s raised %r" % (label, e)
                out.add("Z", gid, ok, label, detail)

    except Exception as e:
        import traceback; traceback.print_exc()
        print("[ERROR] check failed: %s" % e)
        return 1

    # --- Gate registry verification (补充篇 §五 第2条) ---
    # quick 模式没跑 B 段，拿它做防缩水对账会得到假结论，故一并跳过。
    if _settable_expected and not quick:
        _, exp = _settable_expected
        passed = verify_registration(exp, "wrapper")
        if not passed:
            print("[FATAL] Gate registration integrity check failed. Aborting check.")
            return 1

    # Output
    if quick:
        print("[quick] 仅跑 A 段结构闸；B/Z 段、防缩水对账与检查凭据写入已跳过")
    out.emit()
    nfail = out.fail_count()
    n_a = out.count("A"); n_b = out.count("B")
    # 写检查凭据（社区版 rules_db 提供；未提供的端保持原样，不产生文件）
    # quick 是结构子集，不写凭据，避免把「没跑全」的结果记成一次正式检查。
    _rec = getattr(_get_rules_db(), "record_check_result", None)
    if callable(_rec) and not quick:
        try:
            _rec(nfail, n_a, n_b, len(out.rows))
        except Exception as _e:
            print("[WARN] 检查凭据写入失败：%r" % _e)
    print("")
    if nfail == 0:
        if quick:
            print("[结论] ALL PASS（quick：仅 A 段 %d 项，B/Z 段未跑）—— 不能替代 check --strict" % n_a)
        elif n_b > 0:
            print("[结论] ALL PASS（A段 %d 项 + B段 %d 项） —— 允许记账" % (n_a, n_b))
        else:
            print("ALL PASS (%d gates)" % len(out.rows))
        return 0
    else:
        print("FAIL (%d/%d gates red%s)" % (
            nfail, len(out.rows),
            "；quick 仅 A 段，B/Z 未跑 —— 不能替代 check --strict" if quick else ""))
        # 票面 rc 必须与结论一致：结论 FAIL 即 rc 非 0，不因缺 --strict 而报成功。
        return 1


def cmd_show(cid):
    try:
        dbm = _get_rules_db()
        db = dbm.index(dbm.load())
        for c in db["clauses"]:
            if c["id"] == cid:
                print("[%s] %s" % (c["id"], c.get("title", "")))
                for b in c.get("body", []):
                    print("  " + b)
                return
        print("clause %s not found" % cid)
        return 1
    except Exception as e:
        print("[ERROR] show failed: %s" % e)
        return 1


def cmd_bump(level):
    try:
        dbm = _get_rules_db()
        meta_path = getattr(dbm, "META_PATH", None)
        if not meta_path:
            # Try to find meta.json near the rules_dir
            HERE = os.path.dirname(os.path.abspath(__file__))
            candidates = [
                os.path.join(os.path.dirname(HERE), "00_meta", "meta.json"),
                os.path.join(HERE, "..", "00_meta", "meta.json"),
                os.path.join(HERE, "meta.json"),
            ]
            for cp in candidates:
                if os.path.exists(cp):
                    meta_path = cp
                    break

        if not meta_path or not os.path.exists(meta_path):
            print("[ERROR] meta.json not found")
            return 1

        with open(meta_path, "r", encoding="utf-8") as f:
            m = json.load(f)
        ver = m.get("version", "0.0")
        parts = [int(x) for x in ver.split(".")]
        while len(parts) < 2: parts.append(0)

        if level == "L3":
            new_ver = "%d.0" % (parts[0] + 1) if len(parts) >= 2 else "%d.0" % (parts[-1]+1)
        elif level == "L2":
            new_ver = "%d.%d" % (parts[0], parts[1]+1) if len(parts) >= 2 else "%d.%d" % (parts[-1], parts[-1]+1)
        elif level == "L1":
            new_ver = ver
        else:
            print("未知级别：%s" % level)
            return 1

        print("当前：%s ／ %s → 下一版本：%s" % (ver, level, new_ver))
        if level == "L1":
            print("（L1措辞修订不升版本号，只须记账一笔修订）")
        return 0
    except Exception as e:
        import traceback; traceback.print_exc()
        print("[ERROR] bump failed: %s" % e)
        return 1


def cmd_selftest(kernel=False):
    """自检入口——两条路径刻意分开，不互相冒充。

    selftest --kernel  内核自检：不依赖宿主 rules_db，验证内核可加载、CLI 可解析、
                       防缩水机制可用；可在任意目录独立运行。
    selftest           宿主集成自检：需要宿主先 configure(rules_db)，逐项检查规则库
                       契约成员是否可用。未注入时明确报「需宿主注入规则库」。
    """
    if kernel:
        return cmd_selftest_kernel()
    try:
        dbm = _get_rules_db()
    except RuntimeError:
        print("[ERROR] 内核自检需宿主注入规则库（rules_db）；独立运行请用："
              "python -m bumao_core.engine selftest --kernel")
        return 2

    rows = []
    try:
        db = dbm.index(dbm.load())
        meta = dbm.load_meta()
        clauses = db["clauses"]
        rows.append(("H1", isinstance(db, dict) and
                     all(k in db for k in ("meta", "clauses", "chapters")),
                     "load/index 返回 meta/clauses/chapters", ""))
        rows.append(("H2", dbm.dup_ids(db) == [], "dup_ids 无重复", ""))
        rows.append(("H3", dbm.block_broken(clauses) == [], "block_broken 无断裂", ""))
        rows.append(("H4", all(not c.get("broken_refs") for c in clauses), "broken_refs 全空", ""))
        rows.append(("H5", bool(meta.get("name")) and bool(meta.get("version")),
                     "load_meta 含 name/version",
                     "%s v%s" % (meta.get("name", ""), meta.get("version", ""))))
    except Exception as e:
        print("[ERROR] 宿主集成自检跑不起来：%r" % e)
        return 1

    for cid, ok, name, detail in rows:
        print("%s %s %s%s" % ("PASS" if ok else "FAIL", cid, name,
                             ("  :: %s" % detail) if detail else ""))
    n_pass = sum(1 for r in rows if r[1])
    print("宿主集成自检 %s（%d/%d）" % ("PASS" if n_pass == len(rows) else "FAIL",
                                       n_pass, len(rows)))
    return 0 if n_pass == len(rows) else 1


def cmd_selftest_kernel():
    """内核自检：不读任何宿主规则库、不写任何宿主账本。"""
    import contextlib
    import io

    rows = []

    def _run(cid, name, fn):
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, "%r" % e
        rows.append((cid, bool(ok), name, detail))

    def _cli():
        p = build_parser()
        choices = None
        for _a in p._actions:
            if isinstance(_a, argparse._SubParsersAction):
                choices = sorted(_a.choices.keys())
        want = sorted(["whoami", "check", "audit", "bump", "show", "selftest", "refresh"])
        if choices != want:
            return False, "子命令=%s" % choices
        p.parse_args(["check", "--quick"])
        p.parse_args(["whoami", "--full"])
        p.parse_args(["selftest", "--kernel"])
        return True, "%d 子命令，无重复注册" % len(choices)

    def _out():
        o = Out()
        o.add("A", "K1", True, "绿")
        o.add("B", "K2", False, "红")
        ok = (o.count("A") == 1 and o.fail_count() == 1 and len(o.fails()) == 1)
        return ok, "A=1 fail=1"

    def _anti_shrink():
        global _b_gates_list, _z_gates_list, _registered_gate_ids, _settable_expected
        snap = (list(_b_gates_list), list(_z_gates_list),
                set(_registered_gate_ids), _settable_expected)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                register("K1", lambda: True, "自检闸一")
                register("K2", lambda: True, "自检闸二")
                set_expected("kernel-selftest", frozenset(["K1", "K2"]))
                good = verify_registration({"K1", "K2"}, "kernel-selftest")
                bad = verify_registration({"K1", "K2", "K3"}, "kernel-selftest")
        finally:
            (_b_gates_list, _z_gates_list,
             _registered_gate_ids, _settable_expected) = snap
        return (good and not bad), "齐套=%s 缺一=%s" % (good, not bad)

    def _registry():
        gr = _import_gate_registry()
        r = gr.version_approval("0.10", "2020-01-01", "")
        ok = (r["verdict"] == "DENY" and "判拒" in r["l2_detail"])
        return ok, "A10 空审批册 → %s" % r["verdict"]

    def _guard():
        try:
            _get_rules_db()
        except RuntimeError as e:
            return ("rules_db not configured" in str(e)), "未注入时抛出明确错误"
        return False, "未注入时竟然取到了规则库"

    _run("K1", "engine 可导入",
         lambda: (True, "engine=%s Python=%s" % (__name__, sys.version.split()[0])))
    _run("K2", "CLI 解析器（7 子命令，无重复注册）", _cli)
    _run("K3", "Out 计数与失败收集", _out)
    _run("K4", "防缩水 register／set_expected／verify_registration", _anti_shrink)
    _run("K5", "gate_registry 可导入且 A10 判据可跑", _registry)
    _run("K6", "未注入 rules_db 时守卫明确报错", _guard)

    for cid, ok, name, detail in rows:
        print("%s %s %s%s" % ("PASS" if ok else "FAIL", cid, name,
                             ("  :: %s" % detail) if detail else ""))
    n_pass = sum(1 for r in rows if r[1])
    print("内核自检 %s（%d/%d）" % ("PASS" if n_pass == len(rows) else "FAIL",
                                   n_pass, len(rows)))
    return 0 if n_pass == len(rows) else 1


def cmd_refresh():
    """Re-render views (if render module available)"""
    try:
        dbm = _get_rules_db()
        meta = dbm.load_meta()
        db = dbm.index(dbm.load())
        # Check if render function exists on dbm
        if hasattr(dbm, "render_all"):
            n = dbm.render_all(meta, db)
            print("rendered %d views" % n)
        else:
            print("refresh placeholder (no render module)")
        return 0
    except Exception as e:
        print("[ERROR] refresh failed: %s" % e)
        return 1


# ========== Injection points for wrappers ==========
_rdb = None  # Injected rules_db module
_b_gates_list = []  # Registered B gates [(gid, fn, label)]
_z_gates_list = []  # Registered Z gates [(gid, fn, label)]
_registered_gate_ids = set()  # Tracks ALL gate IDs for silence-shrinkage detection (补充篇 §五 第2条)


def configure(rules_db_module=None):
    """Configure engine with external rules_db. Call first."""
    global _rdb
    if rules_db_module is not None:
        _rdb = rules_db_module


def register(gid, fn, label, section="B"):
    """Register a single gate. Wrapper calls this for each B-gate."""
    if section == "B":
        _b_gates_list.append((gid, fn, label))
    elif section == "Z":
        _z_gates_list.append((gid, fn, label))
    else:
        _b_gates_list.append((gid, fn, label))
    # Track ALL registered gate IDs for silence-shrinkage detection (补充篇 §五 第2条)
    _registered_gate_ids.add(gid)
    return fn


def register_all(category_fn_map, category="B"):
    """Batch register gates from {category_id: fn} dict. Returns list of registered gids."""
    for gid, fn in sorted(category_fn_map.items()):
        register(gid, fn, "(auto-discovered)", category)
    return list(sorted(category_fn_map.keys()))


# --- Gate registry verification (补充篇 §五 第2条) ---
# Tracks expected vs actual gate counts. Used by cmd_check to enforce
# 'commenting out any register() must make check --strict FAIL'.

_settable_expected = set()  # Edition-specific expected gate sets (populated via set_expected)


def set_expected(section, expected_set):
    """Set expected gates for this edition. Call from wrapper after all register() calls."""
    global _settable_expected
    _settable_expected = (section, frozenset(expected_set))


def verify_registration(expected_set, edition_name="unknown"):
    """Check no silent shrinkage. Returns True if all expected gates registered.

    期望集来自宿主层声明件（wrapper 只读），本函数不认任何具体闸名、不内置清单。"""
    missing = sorted(expected_set - _registered_gate_ids)
    extra = sorted(_registered_gate_ids - expected_set)
    
    errors = []
    if missing:
        errors.append("MISSING (%d): %s" % (len(missing), ", ".join(missing[:10])))
        if len(missing) > 10:
            errors[-1] += " (+%d more)" % (len(missing) - 10)
    if extra:
        if len(extra) > 3:
            errors.append("EXTRA (%d): %s" % (len(extra), ", ".join(extra[:5])))
        else:
            # ≤3 的容差是「wrapper 与声明件配对改」的过渡通道，不是漏登记的免检牌：
            # 过渡态必须把闸名印出来，票面与留档里看得见；gate_count 那侧仍逐个比、直接 FAIL。
            print("[wrapper]: WARN -- 已注册但未登记进声明件 %d 个：%s "
                  "-- 期望集唯一来源是 00_meta/gates_decl.json，配对改完必须补登记；"
                  "gate_count 对本项判 FAIL" % (len(extra), ", ".join(extra)))
    
    if errors:
        msg = "%s REGISTER FAILED\n" % edition_name
        msg += "  Expected: %d gates, Registered: %d\n" % (len(expected_set), len(_registered_gate_ids))
        for e in errors:
            msg += "  %s\n" % e
        msg += "\nPer supplement §五 第2条: uncomment any register() -> check --strict must FAIL"
        print(msg)
        return False
    
    print("[%s]: OK -- %d/%d gates confirmed via gate_registry" % (edition_name, len(_registered_gate_ids), len(expected_set)))
    return True


def _get_rules_db():
    if _rdb is not None:
        return _rdb
    raise RuntimeError("rules_db not configured. Call configure() first.")

def _get_b_gates():
    return list(_b_gates_list)

def _get_z_gates():
    return list(_z_gates_list)


# ========== Parser & dispatch ==========

def build_parser():
    parser = argparse.ArgumentParser(prog="bumao-core", description="Bumao Core — Unified Kernel CLI")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("whoami"); p.add_argument("--full", action="store_true")
    p = sub.add_parser("check"); p.add_argument("--strict", action="store_true"); p.add_argument("--quick", action="store_true")
    sub.add_parser("audit")
    p = sub.add_parser("bump"); p.add_argument("--level", default="L1")
    p = sub.add_parser("show"); p.add_argument("cid")
    p = sub.add_parser("selftest"); p.add_argument("--kernel", action="store_true")
    sub.add_parser("refresh")

    return parser


def main(argv=None):
    """Main entry point. Accepts argv or uses sys.argv.

    解析器只有 build_parser() 一处定义：2026-11-09 修复 build_parser() 重复注册 check
    的缺陷，同时把 main() 里那份重复的解析器删掉——两份解析器正是「文档声明的参数
    实际没注册」的根因。
    """
    if argv is None:
        argv = sys.argv[1:]

    ap = build_parser()
    # 始终用传入的 argv 解析；传空列表就是「无子命令」，不能回落到 sys.argv
    # （否则在 pytest 之类的宿主进程里会误解析别人的命令行参数）。
    a = ap.parse_args(argv)
    cmd = getattr(a, "command", None)

    if not cmd:
        ap.print_help(); return 2

    rc = 2
    if cmd == "whoami": rc = cmd_whoami(full=a.full)
    elif cmd == "check": rc = cmd_check(strict=a.strict, quick=a.quick)
    elif cmd == "audit": rc = cmd_audit()
    elif cmd == "bump": rc = cmd_bump(getattr(a, "level", "L1"))
    elif cmd == "show": rc = cmd_show(getattr(a, "cid", ""))
    elif cmd == "selftest": rc = cmd_selftest(kernel=a.kernel)
    elif cmd == "refresh": rc = cmd_refresh()

    return rc or 0


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except: pass
    sys.exit(main())
