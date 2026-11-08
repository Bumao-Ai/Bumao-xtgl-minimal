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

"""snapshot.py —— 能力快照：按本端 web_config.json 的 capabilities 开关吐字段。

口径（用户 2026-11-06 交接单 §2.2／§2.4）：
- 所有端认识所有能力（modules.json 三端字节一致），只有本端打开的才采数、才显示；
- 未启用的能力：不采数、不联网、不报错，快照里干脆不出现该键；
- 缺字段／未挂载／实物取不到：一律给 {"state": "状态未知"} 或「宿主未挂载能力」，不白屏、不猜测；
- 隐私：只吐计数／状态／相对文件名／哈希前缀，绝不吐绝对路径、执行者真名、条款正文，
  也不直连 yinsi/ 与真身目录；
- 写死必漂：本件不写死任何条数、天数、版本号，需要数字一律现场读。

三端同一份代码、字节一致，进 core_manifest 哈希清单。
用法：
    python snapshot.py                 人读摘要
    python snapshot.py --json          机器可读
    python snapshot.py --json --out x.json
"""
import hashlib
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = HERE
UNKNOWN = u"状态未知"
UNMOUNTED = u"宿主未挂载能力"


def _load_json(path):
    if not path or not os.path.isfile(path):
        return None
    try:
        with io.open(path, "rb") as f:
            return json.loads(f.read().decode("utf-8-sig"))
    except Exception:
        return None


def conf():
    """本端发行配置 ＋ 本机覆盖层，口径与 `xtgl_core.load_config` 逐字一致。

    原来这里只读 web_config.json，而覆盖件里配好的 daiban／defects／check_log_dir
    快照根本看不见——同一台机器上服务端看得见、快照看不见，面板就一律报「未配置」。
    两份覆盖件都是「第一份存在即用、不叠加」，XTGL_NO_LOCAL_OVERLAY=1 时全关（夹具用）。
    """
    c = _load_json(os.path.join(WEB, "web_config.json"))
    c = dict(c) if isinstance(c, dict) else {}
    if os.environ.get("XTGL_NO_LOCAL_OVERLAY") != "1":
        for local in (os.path.join(os.path.expanduser("~"), ".xtgl", "web_config.local.json"),
                      os.path.join(WEB, "web_config.local.json")):
            over = _load_json(local)
            if isinstance(over, dict):
                c.update(over)
                break
    return c


def root_dir(c):
    """项目根＝服务端同一个尺子：配置 project_root 优先，否则 web 的上级（20_view）再上一级。

    xtgl_core.resolve_root 的默认值是 `HERE.parent.parent`（HERE＝本目录），服务端与各采集器
    必须解成同一个地方，否则同一句相对路径两端各读一份东西——那正是「配了还说未配置」的老根。
    """
    pr = os.path.expanduser(str(c.get("project_root") or "").strip())
    if pr and os.path.isabs(pr):
        return pr
    if pr:
        return os.path.normpath(os.path.join(WEB, pr))
    return os.path.normpath(os.path.join(WEB, "..", ".."))


def conf_path(c, *keys):
    """配置里的路径 → 绝对路径（相对一律按 root_dir 解，各段采集器共用这一把尺子）。

    旧写法在 gates／ledger／backup／tasks／legislation 五处各抄一遍
    `os.path.join(os.path.dirname(WEB), …)`，基准既不是项目根也不是服务端的 web，
    三套口径谁也对不上；现在只留这一处。
    """
    v = c
    for k in keys:
        v = (v or {}).get(k) if isinstance(v, dict) else None
    p = os.path.expanduser(str(v or "").strip())
    if not p:
        return ""
    if not os.path.isabs(p):
        p = os.path.normpath(os.path.join(root_dir(c), p))
    return p


def modules():
    m = _load_json(os.path.join(WEB, "modules.json"))
    return m if isinstance(m, dict) else {}


def capability_map(mod=None):
    out = {}
    for it in (mod or modules()).get("modules") or []:
        if isinstance(it, dict) and it.get("id"):
            out[str(it["id"])] = it
    return out


def enabled(conf_=None):
    """本端打开的能力 ID。开关缺失＝按清单里 status=active 的全开（空库三端不崩）。"""
    c = conf_ or conf()
    lst = c.get("capabilities")
    if isinstance(lst, list) and lst:
        return [str(x) for x in lst]
    return None


def rel_name(path):
    """相对 WEB 的文件名（绝不吐绝对路径）。

    跨盘符（本机件放在 C 盘、项目在 D 盘）relpath 会抛异常——这不等于「不知道是哪个件」，
    文件名本身不涉密，退到 basename 比报「状态未知」更接近事实。
    """
    try:
        return os.path.relpath(path, WEB).replace("\\", "/")
    except Exception:
        try:
            return os.path.basename(str(path).rstrip("\\/")) or UNKNOWN
        except Exception:
            return UNKNOWN


def sha8(path):
    try:
        with io.open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:8]
    except Exception:
        return UNKNOWN


def _newest(d, exts=(".txt", ".log", ".json", ".md"), name_prefix=None):
    if not d or not os.path.isdir(d):
        return None
    try:
        cands = [os.path.join(d, f) for f in os.listdir(d)
                 if f.lower().endswith(exts) and ".bak" not in f
                 and (not name_prefix or f.startswith(name_prefix))
                 and os.path.isfile(os.path.join(d, f))]
    except Exception:
        return None
    return max(cands, key=os.path.getmtime) if cands else None


# ---------- 各能力的数据源（source 字段对应的采集器；未启用不调用） ----------
def sec_meta(c, mods):
    mani = _load_json(os.path.join(WEB, "core_manifest.json")) or {}
    en = enabled(c) or []
    return {
        "edition": c.get("product_edition") or UNKNOWN,
        "core_version": mani.get("core_version") or UNKNOWN,
        "manifest_generated": mani.get("generated") or UNKNOWN,
        "schema": mods.get("schema") or UNKNOWN,
        "defined": len(mods.get("modules") or []),
        "enabled": len(en),
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def sec_gates(c):
    """闸门结论＝读最近一份实跑输出件，不重跑引擎（快照必须便宜、可反复调）。"""
    d = conf_path(c, "check_log_dir")
    q = _newest(d, exts=(".log", ".txt"), name_prefix="check_") if d else None
    if not q:
        return {"state": UNKNOWN, "note": u"未配置检查日志目录（web_config.check_log_dir）或目录里没有 check_* 实跑件"}
    try:
        txt = io.open(q, "rb").read().decode("utf-8", "ignore")
    except Exception:
        return {"state": UNKNOWN}
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    concl = lines[-1] if lines else UNKNOWN
    red = sum(1 for l in lines if l.startswith("FAIL"))
    return {
        "state": u"绿" if concl.startswith(u"[结论] ALL PASS") or "ALL PASS" in concl else u"红",
        "conclusion": concl[:120],
        "red_count": red,
        "green_count": sum(1 for l in lines if l.startswith("PASS")),
        "gate_count": sum(1 for l in lines if l.startswith(("PASS ", "FAIL "))),
        "source_file": rel_name(q),
        "at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(q))),
        "age_seconds": int(time.time() - os.path.getmtime(q)),
    }


def sec_coverage(c, mods):
    caps = capability_map(mods)
    en = enabled(c) or sorted(caps)
    with_ev = [i for i, m in caps.items() if str(m.get("evidence") or "").strip()]
    read_only = [i for i, m in caps.items() if m.get("permission") == "read"]
    return {
        "defined": len(caps),
        "enabled": len([i for i in en if i in caps]),
        "unmounted_switches": [i for i in en if i not in caps],
        "with_evidence": len(with_ev),
        "read_only": len(read_only),
    }


def sec_ledger(c):
    p = conf_path(c, "defects")
    if not p or not os.path.isfile(p):
        return {"state": UNKNOWN, "note": u"未配置缺陷台账（web_config.defects）"}
    try:
        rows = [l for l in io.open(p, encoding="utf-8").read().splitlines()
                if l.strip().startswith("|") and "---" not in l]
    except Exception:
        return {"state": UNKNOWN}
    body = rows[1:] if rows else []
    st = [l.split("|") for l in body]
    # 台账九列：1 编号｜2 日期｜3 发现改｜4 问题｜5 位置｜6 严重度｜7 影响｜8 状态｜9 备注
    # 状态在第 8 列（split 后 parts[8]，口径同 wrapper 的 B15d）
    closed = sum(1 for parts in st
                 if len(parts) > 8 and u"闭环" in parts[8] and u"未闭环" not in parts[8])
    today = time.strftime("%Y-%m-%d")
    found = sum(1 for parts in st if len(parts) > 2 and parts[2].strip() == today)
    return {"rows": len(body), "closed": closed, "open": len(body) - closed,
            "found_today": found,
            "latest_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p))),
            "source_file": rel_name(p), "head_sha8": sha8(p)}


def sec_backup(c):
    d = conf_path(c, "backup", "plan_dir")
    if not d or not os.path.isdir(d):
        return {"state": UNKNOWN, "note": u"未配置备份计划目录（web_config.backup.plan_dir）"}
    q = _newest(d)
    names = [f for f in os.listdir(d) if ".bak" not in f and os.path.isfile(os.path.join(d, f))]
    plans = sorted([f for f in names if f.startswith("dai_shan_qingdan_")])
    out = {"files": len(names),
           "latest_file": rel_name(q) if q else UNKNOWN,
           "latest_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(q)))
           if q else UNKNOWN,
           "plan_files": len(plans)}
    if plans:
        pp = os.path.join(d, plans[-1])
        try:
            out["plan_items"] = len([l for l in io.open(pp, encoding="utf-8").read().splitlines()
                                     if l.strip()])
        except Exception:
            out["plan_items"] = UNKNOWN
        out["plan_at"] = plans[-1].replace("dai_shan_qingdan_", "").replace(".txt", "")
        out["plan_source"] = plans[-1]
    return out


def sec_evidence(c, mods):
    caps = capability_map(mods)
    en = enabled(c) or sorted(caps)
    return {i: str(caps[i].get("evidence") or UNKNOWN) for i in en if i in caps}


def board_rows(txt):
    """一块看板有多少条——与服务端同一把尺子，返回 (条数, 用的是什么形状)。

    看板有两种形状：`[S1]`／`[G1]` 块状（短期、长期）与 `|` 表状（待办总表）。
    旧写法只数 `|` 行，块状件一律报 0，于是「盘上 8 条目标、面板 0 条」被当成欠账。
    块状交给服务端的 parse_goals 解析，本件不另立第二套字段解析。
    """
    if re.search(r"^\[[A-Za-z]\d+\]\s*$", txt, re.M):
        try:
            from xtgl_core import parse_goals
        except Exception:
            return 0, u"块状 [编号] 节（内核解析器不可用）"
        return len(parse_goals(txt)), u"块状 [编号] 节"
    n = 0
    for line in txt.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        first = [x.strip() for x in s.strip("|").split("|")][0]
        if first == u"编号" or set(first) <= set("-: "):
            continue        # 表头与分隔行不是数据，判据与服务端 daiban() 逐字同
        n += 1
    return n, u"表状 | 数据行"


def sec_tasks(c):
    out = {}
    for key, name in (("daiban", u"待办总表"), ("goals", u"长期任务"), ("short_tasks", u"短期任务")):
        p = conf_path(c, key)
        if p and os.path.isfile(p):
            try:
                txt = io.open(p, encoding="utf-8").read()
                n, fmt = board_rows(txt)
                out[name] = {"rows": n, "fmt": fmt, "source_file": rel_name(p),
                             "at": time.strftime("%Y-%m-%d %H:%M:%S",
                                                 time.localtime(os.path.getmtime(p)))}
            except Exception:
                out[name] = {"state": UNKNOWN}
        else:
            out[name] = {"state": UNKNOWN, "note": u"未配置（web_config.%s）" % key}
    return out


def sec_legislation(c):
    p = conf_path(c, "legislation_ledger")
    if not p or not os.path.isfile(p):
        return {"state": UNKNOWN, "note": u"未配置准则变更记账件（web_config.legislation_ledger）"}
    try:
        rows = [l for l in io.open(p, encoding="utf-8").read().splitlines()
                if l.strip().startswith("|") and "---" not in l]
    except Exception:
        return {"state": UNKNOWN}
    body = rows[1:] if rows else []
    last = body[-1].split("|") if body else []
    today = time.strftime("%Y-%m-%d")
    return {"rows": len(body), "today_rows": sum(1 for l in body if today in l),
            "latest_id": last[1].strip() if len(last) > 1 else UNKNOWN,
            "at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p))),
            "source_file": rel_name(p)}


def sec_clients(c):
    e = c.get("engine") or {}
    cmd = e.get("cmd") or []
    return {"edition": c.get("product_edition") or UNKNOWN,
            "engine_entry": str(cmd[-1]) if cmd else UNKNOWN,
            "engine_cwd": str(e.get("cwd") or UNKNOWN),
            "port": c.get("port", UNKNOWN)}


def sec_drift(c):
    """核心文件漂移＝现场算 sha256 与 core_manifest 对账（件名＋哈希前缀，不吐路径）。"""
    mani = _load_json(os.path.join(WEB, "core_manifest.json")) or {}
    files = mani.get("files") or {}
    if not files:
        return {"state": UNKNOWN, "note": u"缺 core_manifest.json"}
    drift, ok = [], 0
    for name, want in sorted(files.items()):
        p = os.path.join(WEB, name)
        if not os.path.isfile(p):
            drift.append({"file": name, "state": u"缺失"})
            continue
        got = sha8(p)
        if str(want)[:8] == got:
            ok += 1
        else:
            drift.append({"file": name, "state": u"漂移", "manifest": str(want)[:8], "now": got})
    return {"checked": len(files), "same": ok, "drifted": drift}


def sec_rules_library(c):
    """规则库预留槽位现场算：复用 module_check 的同一份校验，只报计数，
    不读任何规则正文、不吐绝对路径（§3 红线①②＋§1 隐私红线）。"""
    from module_check import rules_library_scan
    errs, info = rules_library_scan()
    if not info.get("mounted"):
        return {"state": u"未建库（不影响启动）", "slots": 0, "preset_missing": [],
                "enabled_slots": 0, "rules_active": 0, "format_errors": 0}
    return {"state": u"已建库", "slots": len(info.get("slots") or []),
            "preset_missing": info.get("preset_missing") or [],
            "enabled_slots": len(info.get("counted") or []),
            "rules_active": sum(s["rules"] for s in info.get("slots") or []
                                if s["id"] in (info.get("counted") or [])),
            "examples": info.get("examples"), "format_errors": len(errs)}


def build():
    c, mods = conf(), modules()
    caps, en = capability_map(mods), enabled(c)
    open_set = set(en) if en is not None else set(caps)
    out = {}
    collectors = {
        "meta": lambda: sec_meta(c, mods),
        "gates": lambda: sec_gates(c),
        "coverage": lambda: sec_coverage(c, mods),
        "ledger": lambda: sec_ledger(c),
        "backup": lambda: sec_backup(c),
        "evidence": lambda: sec_evidence(c, mods),
        "tasks": lambda: sec_tasks(c),
        "legislation": lambda: sec_legislation(c),
        "clients": lambda: sec_clients(c),
        "drift": lambda: sec_drift(c),
        "rules_library": lambda: sec_rules_library(c),
    }
    src2sec = {}
    for cid, m in caps.items():
        s = str(m.get("source") or "")
        if s.startswith("snapshot."):
            src2sec.setdefault(s.split(".", 1)[1], []).append(cid)
    for sec, fn in collectors.items():
        if sec == "meta" or sec == "coverage" or sec == "drift":
            keep = True                        # 元信息与覆盖率／漂移是骨架自身，任何端都要有
        else:
            keep = any(cid in open_set for cid in src2sec.get(sec, [])) or sec in open_set
        if not keep:
            continue                            # 未启用 → 不采数、不出键
        owners = src2sec.get(sec, [])
        if owners and not [x for x in owners if x in caps]:
            out[sec] = {"state": UNMOUNTED}
            continue
        try:
            out[sec] = fn()
        except Exception as e:                  # 采不到就明说，绝不 fallback 成「全部已接入」
            out[sec] = {"state": UNKNOWN, "note": repr(e)[:80]}
    out["_capabilities"] = {"defined": sorted(caps), "enabled": sorted(open_set),
                            "unmounted": sorted(x for x in open_set if x not in caps)}
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    doc = build()
    if "--json" in argv:
        txt = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        if "--out" in argv:
            p = argv[argv.index("--out") + 1]
            with io.open(p, "wb") as f:
                f.write(txt.encode("utf-8"))
            print(u"[快照] %s（%d B）" % (rel_name(p), os.path.getsize(p)))
        else:
            print(txt)
        return 0
    print(u"=== 能力快照（现场算，未启用的能力不出键）")
    for k, v in doc.items():
        if k == "_capabilities":
            print(u"  定义 %d ｜ 本端启用 %d ｜ 开关有但定义无 %s"
                  % (len(v["defined"]), len(v["enabled"]), v["unmounted"] or u"（无）"))
            continue
        if isinstance(v, dict) and v.get("state") in (UNKNOWN, UNMOUNTED):
            print(u"  %-12s %s ｜ %s" % (k, v.get("state"), v.get("note", "")))
        else:
            print(u"  %-12s %s" % (k, json.dumps(v, ensure_ascii=False)[:150]))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main())
