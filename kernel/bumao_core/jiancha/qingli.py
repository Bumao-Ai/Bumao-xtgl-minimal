# -*- coding: utf-8 -*-
"""监管轮次产物清理：只清 run_dir 下它自己生成的东西。

用户约束（2026-11-08）：
1. 只清 jiancha_run 下自己生成的轮次产物；票本、账本、_frozen、live 树一律不进。
2. 正在用／未结束的轮次必须跳过。
3. 先出保留策略，再给 dry-run；默认不删，只有显式 --apply 才删。

保留策略（参数在 jiancha_canshu.json 的 qingli 段）：
- baseline：工作区快照副本。**该轮有 halt_*／quarantine 证据束时，基线与证据束同寿命**
  （证据束在保留窗口内，基线就不清）——它是「拦截时 live 树长什么样」的唯一副本；
  没拦过事的轮次才只留当前一份（新一轮 begin 会重拍）。
- evidence：halt_* 与 quarantine/* 证据束，各保留最近 keep_evidence 份（默认 10），更早的清。
- 账本 actions（JSON Lines）、state.json 永远保留：不参与任何删除，只用于审计与追溯。
- 总量上限 max_total_mb（默认 400）：清完仍超，只报告，不越界删账本。
- 触发时机：启动时（Supervisor.begin 之前）。理由：失败轮走不到收尾钩子；
  begin 是新旧轮切换点，此时旧轮必然已不被进程使用；收尾清理只能覆盖正常结束的少数情况。

跳过规则：
- run_dir 不存在 → 无可清理。
- state.status == "running" → 本轮在用，跳过（任何情况下都不清）。
- state.status 为其他未结束态（如 halted）：
  * 自动钩子（新一轮 begin）允许清，因为 begin 会覆盖 state，旧轮已被放弃；
  * 手工 CLI 默认跳过（严格按「未结束必须跳过」），确需清理时加 --allow-halted。
- 最近一次轮次开始不足 min_age_hours（默认 1 小时）→ 跳过，防并发误清。
"""

import io
import json
import os
import shutil
import time

DEFAULTS = {
    "enabled": True,
    "min_age_hours": 1,
    "keep_evidence": 10,
    "max_total_mb": 400,
}

# run_dir 根下永远不删的件（票本在别处，这里只列本目录内账本/状态/指纹）
PROTECTED = ("actions." + "jsonl", "state.json", "state.json.tmp",
             "gate_ref.json", "jiancha_canshu.json", "qingli.log")


def settings(cfg):
    s = dict(DEFAULTS)
    s.update((cfg or {}).get("qingli") or {})
    return s


def _state(run_dir):
    p = os.path.join(run_dir, "state.json")
    if not os.path.isfile(p):
        return None
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _started_at(st):
    s = str((st or {}).get("started_at") or "")
    try:
        return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return None


def _dir_bytes(path):
    total = 0
    for base, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            p = os.path.join(base, name)
            try:
                total += os.path.getsize(p)
            except OSError:
                pass
    return total


def _inside(base, path):
    try:
        return os.path.commonpath([os.path.abspath(base), os.path.abspath(path)]) == os.path.abspath(base)
    except ValueError:
        return False


def _evidence_all(run_dir):
    """返回 (halt, quarantine) 全部证据束路径，按名排序。"""
    root = os.path.join(run_dir, "evidence")
    halt, quar = [], []
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            p = os.path.join(root, name)
            if not os.path.isdir(p):
                continue
            if name.startswith("halt_"):
                halt.append(p)
            elif name == "quarantine":
                for sub in sorted(os.listdir(p)):
                    sp = os.path.join(p, sub)
                    if os.path.isdir(sp):
                        quar.append(sp)
    return halt, quar


def _evidence_bundles(run_dir, keep):
    """evidence 下可清的证据束：halt_* 与 quarantine/*，各留最近 keep 份（按名排序）。"""
    halt, quar = _evidence_all(run_dir)
    drop = halt[:-keep] if keep > 0 else list(halt)
    drop += quar[:-keep] if keep > 0 else list(quar)
    return drop


def plan(run_dir, cfg=None, now=None, allow_halted=False):
    """只算不删。返回字典：skip / items / freed_bytes / total_bytes / remaining_bytes。"""
    s = settings(cfg)
    now = time.time() if now is None else now
    out = {"run_dir": run_dir or "", "skip": "", "items": [], "freed_bytes": 0,
           "total_bytes": 0, "remaining_bytes": 0, "warnings": [], "policy": s}
    if not run_dir or not os.path.isdir(run_dir):
        out["skip"] = "run_dir 不存在，无可清理"
        return out
    out["total_bytes"] = _dir_bytes(run_dir)

    st = _state(run_dir)
    status = str((st or {}).get("status") or "")
    if status == "running":
        out["skip"] = "本轮状态 running（正在用），跳过"
        return out
    if status == "halted" and not allow_halted:
        out["skip"] = "本轮状态 halted（未结束，需先 recover/done），跳过（确需清理加 --allow-halted）"
        return out
    started = _started_at(st)
    if started is not None:
        age_h = (now - started) / 3600.0
        if age_h < float(s["min_age_hours"]):
            out["skip"] = "本轮开始仅 %.1f 小时（< min_age_hours=%s），跳过" % (age_h, s["min_age_hours"])
            return out

    items = []
    base = os.path.join(run_dir, "baseline")
    halt_all, quar_all = _evidence_all(run_dir)
    if os.path.isdir(base):
        if halt_all or quar_all:
            # 用户 2026-11-08 审核口径：基线是「拦截时 live 树长什么样」的唯一副本，
            # 该轮有 halt/quarantine 证据束时，基线与其同寿命（留在证据束保留窗口内）。
            out["warnings"].append(
                "baseline 保留：本目录有 halt %d 束／quarantine %d 束，基线与其同寿命"
                % (len(halt_all), len(quar_all)))
        elif st is None and (now - _mtime(base)) / 3600.0 < float(s["min_age_hours"]):
            out["warnings"].append("baseline 无 state 且新鲜（< min_age_hours），本轮跳过它")
        else:
            items.append(base)
    items.extend(_evidence_bundles(run_dir, int(s["keep_evidence"])))

    for p in items:
        name = os.path.basename(p)
        if name in PROTECTED or "_frozen" in name.lower():
            out["warnings"].append("受保护件拒删：%s" % p)
            continue
        if not _inside(run_dir, p):
            out["warnings"].append("越界拒删：%s" % p)
            continue
        size = _dir_bytes(p)
        out["items"].append({
            "path": p,
            "rel": os.path.relpath(p, run_dir).replace("\\", "/"),
            "kind": "baseline" if p == base else "evidence",
            "bytes": size,
        })
        out["freed_bytes"] += size

    out["remaining_bytes"] = max(0, out["total_bytes"] - out["freed_bytes"])
    cap = int(float(s["max_total_mb"]) * 1024 * 1024)
    if out["remaining_bytes"] > cap:
        out["warnings"].append("清完仍剩 %.1f MB，超过上限 %.0f MB（账本/票本不动，需人工处理）"
                               % (out["remaining_bytes"] / 1048576.0, float(s["max_total_mb"])))
    return out


def apply(rep):
    """执行 plan 结果。逐项再校验一次归属，失败项不阻断其余。"""
    done, failed = [], []
    base = rep.get("run_dir") or ""
    for it in rep.get("items") or []:
        p = it["path"]
        if os.path.basename(p) in PROTECTED or not _inside(base, p):
            failed.append({"path": p, "why": "受保护或越界"})
            continue
        try:
            shutil.rmtree(p)
            done.append(it)
        except OSError as e:
            failed.append({"path": p, "why": "%s: %s" % (type(e).__name__, e)})
    rep["deleted"] = done
    rep["failed"] = failed
    rep["freed_bytes"] = sum(x["bytes"] for x in done)
    rep["remaining_bytes"] = max(0, rep.get("remaining_bytes", 0) + (rep.get("freed_bytes", 0) - rep["freed_bytes"]))
    return rep


def _log(run_dir, line):
    try:
        with io.open(os.path.join(run_dir, "qingli.log"), "a", encoding="utf-8") as f:
            f.write("%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), line))
    except OSError:
        pass


def before_begin(run_dir, cfg):
    """Supervisor.begin 前置钩子：清旧轮快照与超龄证据束。静默，不写 stdout。"""
    s = settings(cfg)
    if not s.get("enabled") or not run_dir or not os.path.isdir(run_dir):
        return None
    rep = plan(run_dir, cfg, allow_halted=True)
    if rep["skip"]:
        _log(run_dir, "[qingli] skip: %s" % rep["skip"])
        return rep
    apply(rep)
    _log(run_dir, "[qingli] 删除 %d 项 / 释放 %.1f MB / 清后剩 %.1f MB%s"
         % (len(rep.get("deleted") or []), rep["freed_bytes"] / 1048576.0,
            rep["remaining_bytes"] / 1048576.0,
            (" ｜ " + "；".join(rep["warnings"])) if rep.get("warnings") else ""))
    return rep


def _fmt(rep):
    lines = []
    tag = "dry-run" if rep.get("_dry") else "APPLY"
    lines.append("[清理·%s] run_dir=%s" % (tag, rep.get("run_dir") or ""))
    if rep["skip"]:
        lines.append("  跳过：%s" % rep["skip"])
        return lines
    st = "未知"
    try:
        st = str((_state(rep["run_dir"]) or {}).get("status") or "无 state")
    except Exception:
        pass
    lines.append("  轮次状态=%s ｜ 总量 %.1f MB ｜ 策略：留 %s 份证据束、上限 %s MB、min_age %s h"
                 % (st, rep["total_bytes"] / 1048576.0, rep["policy"]["keep_evidence"],
                    rep["policy"]["max_total_mb"], rep["policy"]["min_age_hours"]))
    if not rep["items"]:
        lines.append("  无可清理项（账本/状态/票本一律不动）")
    else:
        lines.append("  将删 %d 项 / 共 %.1f MB：" % (len(rep["items"]), rep["freed_bytes"] / 1048576.0))
        for it in rep["items"]:
            lines.append("    - %s（%s，%.1f MB）" % (it["rel"], it["kind"], it["bytes"] / 1048576.0))
    lines.append("  清后剩余 %.1f MB / 上限 %s MB" % (rep["remaining_bytes"] / 1048576.0,
                                                     rep["policy"]["max_total_mb"]))
    for w in rep.get("warnings") or []:
        lines.append("  [提醒] %s" % w)
    return lines


def main(argv):
    run_dir = ""
    do_apply = "--apply" in argv
    allow_halted = "--allow-halted" in argv
    as_json = "--json" in argv
    if "--run-dir" in argv:
        i = argv.index("--run-dir")
        if i + 1 < len(argv):
            run_dir = argv[i + 1]
    if not run_dir:
        print("用法：python -m jiancha.qingli --run-dir <run_dir> [--apply] [--allow-halted] [--json]")
        return 2
    cfg = {}
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jiancha_canshu.json")
    if os.path.isfile(p):
        with io.open(p, encoding="utf-8") as f:
            cfg = json.load(f)
    rep = plan(run_dir, cfg, allow_halted=allow_halted)
    if do_apply and not rep["skip"]:
        apply(rep)
        _log(run_dir, "[qingli] 手工 APPLY 删除 %d 项 / 释放 %.1f MB"
             % (len(rep.get("deleted") or []), rep["freed_bytes"] / 1048576.0))
    else:
        rep["_dry"] = True
    if as_json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        for ln in _fmt(rep):
            print(ln)
    return 0 if (not rep["skip"] or not do_apply) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
