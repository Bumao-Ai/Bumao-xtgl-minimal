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

"""xtgl_clean.py —— 把「已完成」的任务搬进归档文件（默认演练，--apply 才真动）。

为什么需要它：
    看板只负责「不显示」，文件会一直变长。这个脚本是唯一允许把条目从看板搬走的入口。

什么时候搬：
    ~/.xtgl/health_rules.json 里的 task_archive_days 说了算（默认 0 = 下一次定时任务就搬）。
    状态含「已完成/已归档/已关闭」算完成；人工在界面勾过的（manual.json 里 task_<编号>=true）也算完成。
    完成日期取「完成于」，没有就退回「复核」。

搬去哪：
    与看板同目录的 <看板名>.archive.txt，格式原样保留，追加在末尾，只迁不删。

用法：
    python xtgl_clean.py                # 演练：列出会搬走的条目
    python xtgl_clean.py --apply        # 真搬（先 .bak，再原子替换）
    python xtgl_clean.py --days 0       # 临时覆盖阈值
    python xtgl_clean.py --board short  # 只处理短期任务（goals / short / all）
"""
import argparse
import datetime
import io
import json
import os
import re
import shutil
import sys
import time

import xtgl_core as core

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCK = re.compile(r"^\[([A-Za-z])(\d+)\]$")
HOME = os.path.expanduser("~")
RULES = os.path.join(HOME, ".xtgl", "health_rules.json")
MANUAL = os.path.join(HOME, ".xtgl", "manual.json")


def load_rules():
    """读共享设置；读不到就用默认（0 天、80GB）。"""
    days, disk = 0, 80.0
    try:
        with io.open(RULES, encoding="utf-8-sig") as f:
            d = json.load(f)
        if isinstance(d.get("task_archive_days"), (int, float)):
            days = int(d["task_archive_days"])
        if isinstance(d.get("disk_min_free_gb"), (int, float)):
            disk = float(d["disk_min_free_gb"])
    except Exception:
        pass
    return days, disk


def manual_done():
    """人工勾过的任务：{S1: '2026-11-03'}。勾完就该归档，不用等状态字段被改。"""
    out = {}
    try:
        with io.open(MANUAL, encoding="utf-8-sig") as f:
            d = json.load(f)
        for it in (d.get("items") or []):
            k = str(it.get("key") or "")
            if not k.startswith("task_") or not it.get("ok"):
                continue
            at = str(it.get("at") or "")[:10] or time.strftime("%Y-%m-%d")
            out[k[5:]] = at
    except Exception:
        pass
    return out


def split_blocks(text):
    """按 [X编号] 切块；返回 (头部行, [{'id':..,'lines':[..]}])"""
    head, blocks, cur = [], [], None
    for line in text.split("\n"):
        m = BLOCK.match(line.strip())
        if m:
            if cur:
                blocks.append(cur)
            cur = {"id": m.group(1).upper() + m.group(2), "lines": [line]}
        elif cur:
            cur["lines"].append(line)
        else:
            head.append(line)
    if cur:
        blocks.append(cur)
    return head, blocks


def plan(path, days):
    """返回 (待搬块, 保留块, 头部行)；读不到文件返回 None。"""
    if not os.path.isfile(path):
        return None
    text = io.open(path, encoding="utf-8-sig").read()
    head, blocks = split_blocks(text)
    items = {g["id"]: g for g in core.parse_goals(text)}
    manual = manual_done()
    today = datetime.date.today()
    keep, move = [], []
    for b in blocks:
        g = dict(items.get(b["id"], {}))
        if b["id"] in manual:                      # 人工勾过完成：按勾选时间算
            g["状态"] = "已完成"
            g.setdefault("完成于", manual[b["id"]])
        lc = core.task_lifecycle(g, today)
        age = lc["days_since"] if lc["days_since"] is not None else 0
        if lc["done"] and age >= days:
            move.append({"id": b["id"], "days": age,
                         "done_at": lc["done_at"], "lines": b["lines"]})
        else:
            keep.append(b)
    return move, keep, head


def write(path, head, keeping, moved, apply=False):
    archived = os.path.splitext(path)[0] + ".archive.txt"
    body = "\n".join(head).rstrip("\n") + "\n"
    for b in keeping:
        chunk = "\n".join(b["lines"]).rstrip("\n")
        if chunk:
            body += "\n" + chunk + "\n"
    if not apply:
        return archived, body
    if os.path.isfile(path):
        shutil.copy2(path, path + "." + time.strftime("%Y%m%d-%H%M%S") + ".bak")
    if moved:
        stamp = time.strftime("%Y-%m-%d %H:%M")
        with io.open(archived, "a", encoding="utf-8", newline="\n") as f:
            f.write("\n# ---- 归档于 %s ----\n" % stamp)
            for b in moved:
                lines = list(b["lines"])
                # 每块自己带批次：多批归档出现同名编号时，靠这一行区分，不靠上下文
                lines.insert(1, "归档：%s ｜ 原编号 %s" % (stamp, b["id"]))
                f.write("\n" + "\n".join(lines).rstrip("\n") + "\n")
    tmp = path + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(body)
    io.open(tmp, encoding="utf-8").read()
    os.replace(tmp, path)
    return archived, body


def _detail_path(board_path):
    return os.path.splitext(board_path)[0] + ".detail.json"


def _read_json(path):
    with io.open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def _write_json(path, data, backup=True):
    """原子写 JSON：先 .bak，再临时文件 → 回读校验 → 替换。"""
    if backup and os.path.isfile(path):
        shutil.copy2(path, path + "." + time.strftime("%Y%m%d-%H%M%S") + ".bak")
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    _read_json(tmp)                      # 写盘没落对就当场炸，不留半截 JSON
    os.replace(tmp, path)


def _remap_detail(board_path, changed, archived_ids=()):
    path = _detail_path(board_path)
    if not os.path.isfile(path):
        return
    data = _read_json(path)
    items = data.get("items")
    if not isinstance(items, dict):
        return
    hit = False
    for old in set(archived_ids):        # 已归档条目：明细一并清掉，别留下永远看不到的长文
        if old in items:
            items.pop(old)
            hit = True
    for old, new in changed.items():
        if old in items:
            items[new] = items.pop(old)
            hit = True
    if hit:
        _write_json(path, data)


def _remap_manual(changed, valid_ids, archived_ids=()):
    """task_<旧号> → task_<新号>；刚归档 / 早已归档的 task_* 残留顺手清掉。

    先清「本次归档」，再改名：否则旧 S1 的勾选会被新 S1 继承，变成假完成。
    """
    if not os.path.isfile(MANUAL):
        return
    archived = set(archived_ids)
    data = _read_json(MANUAL)
    items = data.get("items") or []
    out, hit = [], False
    for it in items:
        k = str(it.get("key") or "")
        # 电脑健康已整块移出：A 段与 A/B 分区残留一并清掉
        if k.startswith("a_") or k in ("review_a", "review_b"):
            hit = True
            continue
        # 旧标签里的「A · / B ·」前缀剥掉（显示层统一，不再分层）
        lbl = re.sub(r"^[AB]\s*·\s*", "", str(it.get("label") or ""))
        if lbl != (it.get("label") or ""):
            it = dict(it)
            it["label"] = lbl
            hit = True
        if k.startswith("task_"):
            tid = k[5:]
            # 从没勾过的空记录：没有任何信息，清掉（旧号撞新号就是这么来的）
            if not it.get("ok") and str(it.get("verdict") or "auto") == "auto":
                hit = True
                continue
            if tid in archived:          # 本次刚搬走：勾选记录一并清掉
                hit = True
                continue
            if tid in changed:
                new = changed[tid]
                it = dict(it)
                it["key"] = "task_" + new
                lbl = str(it.get("label") or "")
                if lbl.startswith(tid):
                    it["label"] = new + lbl[len(tid):]
                hit = True
            elif tid not in valid_ids:   # 早已归档任务的人工勾选：清掉，别留孤儿
                hit = True
                continue
        out.append(it)
    if hit:
        data["items"] = out
        _write_json(MANUAL, data)


def _log_renumber(board_path, changed):
    path = os.path.splitext(board_path)[0] + ".renumber.json"
    rec = {"at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "board": os.path.basename(board_path), "map": changed}
    with io.open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def renumber(blocks, apply=False, board_path=None, archived_ids=()):
    """断号致密化：S2,S3,S6 → S1,S2,S3。

    - 顺序不变，只改块头；归档文件保持原编号（历史不改）。
    - apply 时同步 .detail.json 的键与 manual.json 的 task_<id>，并写 .renumber.json 留痕。
    返回 (新块列表, 旧→新映射, 是否发生重排)。
    """
    mapping, seq = {}, {}
    for b in blocks:
        letter = b["id"][0]
        seq[letter] = seq.get(letter, 0) + 1
        mapping[b["id"]] = "%s%d" % (letter, seq[letter])
    changed = {o: n for o, n in mapping.items() if o != n}
    if not changed:
        # 号已连续也可能有残留（旧 task_* 勾选），顺手清一次
        if apply and board_path and blocks:
            try:
                _remap_manual({}, set(mapping.values()), archived_ids)
            except Exception as e:  # noqa: BLE001
                print("   ！人工判定清理失败：%s" % e)
            try:
                _remap_detail(board_path, {}, archived_ids)
            except Exception as e:  # noqa: BLE001
                print("   ！明细清理失败：%s" % e)
        return blocks, mapping, False

    out = []
    for b in blocks:
        new = mapping[b["id"]]
        lines = list(b["lines"])
        if new != b["id"]:
            lines[0] = re.sub(r"^\[[A-Za-z]\d+\]\s*$", "[%s]" % new, lines[0].strip())
        out.append({"id": new, "lines": lines})
    if apply and board_path:
        try:
            _remap_detail(board_path, changed, archived_ids)
        except Exception as e:  # noqa: BLE001
            print("   ！明细键重排失败（看板已改，明细未动）：%s" % e)
        try:
            _remap_manual(changed, set(mapping.values()), archived_ids)
        except Exception as e:  # noqa: BLE001
            print("   ！人工判定键重排失败：%s" % e)
        _log_renumber(board_path, changed)
    return out, mapping, True


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="把已完成的任务搬进归档文件")
    ap.add_argument("--apply", action="store_true", help="真写盘（默认只演练）")
    ap.add_argument("--days", type=int, default=None,
                    help="覆盖阈值；不填就读 health_rules.json 的 task_archive_days")
    ap.add_argument("--board", choices=("all", "goals", "short"), default="all")
    ap.add_argument("--no-renumber", action="store_true",
                    help="不重排断号（默认归档后自动压成连续编号）")
    args = ap.parse_args(argv)

    cfg_days, _disk = load_rules()
    days = cfg_days if args.days is None else args.days
    cfg, err = core.load_config()
    if err:
        print("配置读取失败：%s" % err)
        return 1

    targets = []
    if args.board in ("all", "short"):
        targets.append(("短期任务", cfg.get("short_tasks")))
    if args.board in ("all", "goals"):
        targets.append(("长期任务", cfg.get("goals")))

    total = 0
    renamed = 0
    for label, spec in targets:
        if not spec:
            print("[%s] 未配置，跳过" % label)
            continue
        path = str(core._as_path(spec, core.HERE))
        res = plan(path, days)
        if res is None:
            print("[%s] 文件不存在：%s" % (label, path))
            continue
        move, keep, head = res
        print("[%s] %s ｜ 保留 %d 块，待归档 %d 块（阈值 %d 天）"
              % (label, path, len(keep), len(move), days))
        for b in move:
            print("   → %-4s 完成于 %s（%d 天）" % (b["id"], b["done_at"] or "-", b["days"]))

        # 归档后立刻把断号压连续：S1、S7 搬走后，S2 就该显示成 S1
        changed = False
        if not args.no_renumber:
            keep, _mapping, changed = renumber(
                keep, apply=args.apply, board_path=path,
                archived_ids={b["id"] for b in move})
            if changed:
                moved = ["%s→%s" % (o, n) for o, n in _mapping.items() if o != n]
                print("   ↻ 序号重排 %d 项：%s" % (len(moved), "，".join(moved)))
                renamed += len(moved)

        if move or changed:
            arch, _ = write(path, head, keep, move, apply=args.apply)
            if move:
                print("   %s：%s" % ("已搬入" if args.apply else "演练（未写盘），将追加到", arch))
            elif changed:
                print("   %s看板（仅序号变化）" % ("已写回" if args.apply else "演练（未写盘），将写回"))
        total += len(move)
    print("\n合计 %d 块%s；序号重排 %d 项%s。"
          % (total, "已归档" if args.apply else "待归档（加 --apply 才真搬）",
             renamed, "" if args.apply else "（演练未写盘）"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
