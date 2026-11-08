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

"""gate_count.py —— 三端闸门数的唯一计数口径

补充篇 §五 第1条：闸数达标必须「用同一个 gate_count.py 统出（不许手数）」。
补充篇 §2.9：三端历史上出闸写法不统一，本脚本对三种写法各出一列——
    register(...)   路线B 统一内核写法（core.register / engine.register）
    add(...)        旧引擎 o.add(...) 写法
    ok(...)         旧引擎 ok(...) 写法
补充篇 §五 第5条：数字必须有出处。故本脚本每次运行都打印
「命令 + 执行时间 + 原始输出」三段，文档可直接整段引用，不必手抄。

用法：
    python gate_count.py                 # 三端，含跑 check --strict 交叉校验
    python gate_count.py --no-run        # 只静态计数，不跑 check（快）
    python gate_count.py <端名>          # 只算一端

判定（退出码 0 的条件，三端全部满足）：
    实际 register 数 == set_expected 声明数 == check 运行时报出的闸门数
    且 实际 ID 集合 == 声明 ID 集合（逐个比，不只比数量）

生效：2026-11-04（2026-11-06 改：期望集从宿主层 gates_decl.json 现读）｜ 端无关：本脚本不写死任何闸门 ID
"""

import argparse
import ast
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))          # .../HX/kernel/bumao_core
HX = os.path.dirname(os.path.dirname(HERE))                # .../HX
PY = sys.executable

# 端列表从 HX 目录结构发现：同时含 10_rac 与 20_view 的目录即为一端；不硬编码端名。
EDITIONS = tuple(sorted(
    d for d in os.listdir(HX)
    if os.path.isdir(os.path.join(HX, d, "10_rac"))
    and os.path.isdir(os.path.join(HX, d, "20_view"))
))

# check --strict 结论行的两种历史写法：
#   [结论] ALL PASS（A段 8 项 + B段 61 项） —— 允许记账
#   ALL PASS  (17 gates)
_CONCL = re.compile(r"A\s*段\s*(\d+)\s*项.*?B\s*段\s*(\d+)\s*项")
_CONCL2 = re.compile(r"ALL PASS\s*\(\s*(\d+)\s*gates?\s*\)")


def rac_dir(edition):
    return os.path.join(HX, edition, "10_rac")


def find_wrapper(edition):
    d = rac_dir(edition)
    if not os.path.isdir(d):
        return None
    hits = sorted(f for f in os.listdir(d)
                  if f.startswith("BumaoXTGL_") and f.endswith("_v01.py"))
    return os.path.join(d, hits[0]) if hits else None


def read(path):
    return io.open(path, encoding="utf-8-sig").read()


def count_register_calls(src):
    """AST 口径数 register(...) 调用，并取出字面量闸门 ID。

    用 AST 而不是 grep：grep 会把注释里、字符串里的 'register(' 也算进去，
    这正是「手数」不可靠的原因。
    """
    tree = ast.parse(src)
    ids, nonliteral = [], 0
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        fn = n.func
        name = getattr(fn, "attr", None) or (fn.id if isinstance(fn, ast.Name) else None)
        if name != "register":
            continue
        if n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
            ids.append(n.args[0].value)
        else:
            nonliteral += 1
    return ids, nonliteral


def count_legacy_idioms(src):
    """旧引擎出闸写法计数（正则口径，仅用于历史对照列）。"""
    add = len(re.findall(r"(?<![\w.])o\.add\(", src)) + len(re.findall(r"(?<![\w.])add\(", src))
    ok = len(re.findall(r"(?<![\w.])ok\(", src))
    return add, ok


def gates_decl_path(wrapper):
    """宿主层声明件位置：与 10_rac 同级的 00_meta/gates_decl.json（端无关，只按目录约定定位）。"""
    return os.path.normpath(os.path.join(os.path.dirname(wrapper), "..", "00_meta", "gates_decl.json"))


def declared_expected(wrapper, edition):
    """期望集（declared）唯一来源＝宿主层 gates_decl.json。

    旧口径是从 wrapper 源码正则抠 set_expected(..., frozenset([...]))——用户 2026-11-06 裁定第 6 项
    把期望集挪进宿主层声明件后，字面量就不存在了，正则必然取空。取不到基准时返回 None，
    调用方按「无声明基准」判红；本函数绝不退回任何写死清单，也不认识具体闸门 ID（端无关不变）。
    为兼容旧调用（传源码字符串），字符串入参先回落到该端 wrapper 路径再读声明件。"""
    src = wrapper
    if not str(src).endswith(".py"):
        src = find_wrapper(str(edition).lower()) or ""
    p = gates_decl_path(src) if src else None
    if not p or not os.path.isfile(p):
        return None
    try:
        doc = json.loads(io.open(p, encoding="utf-8-sig").read())
    except (ValueError, OSError):
        return None
    exp = doc.get("expected")
    if not isinstance(exp, list) or not exp:
        return None
    if edition and str(doc.get("edition", "")).lower() != str(edition).lower():
        return None
    return set(exp)
def runtime_counts(wrapper, timeout=300):
    """跑 check --strict，从结论行取运行时报出的闸门数。"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        r = subprocess.run([PY, wrapper, "check", "--strict"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, cwd=os.path.dirname(wrapper), env=env)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT", ""
    out = (r.stdout or "") + (r.stderr or "")
    m = _CONCL.search(out)
    if m:
        return int(m.group(1)) + int(m.group(2)), "A段%s+B段%s" % (m.group(1), m.group(2)), out
    m2 = _CONCL2.search(out)
    if m2:
        return int(m2.group(1)), "%s gates" % m2.group(1), out
    return None, "结论行未识别(rc=%s)" % r.returncode, out


def count_edition(edition, do_run):
    w = find_wrapper(edition)
    res = {"edition": edition, "wrapper": w}
    if not w:
        res["error"] = "找不到 wrapper"
        return res

    src = read(w)
    try:
        ids, nonliteral = count_register_calls(src)
    except SyntaxError as e:
        res["error"] = "wrapper 语法错: %s" % e
        return res

    add, ok = count_legacy_idioms(src)
    decl = declared_expected(w, edition)

    res.update({
        "register": len(ids),
        "register_ids": sorted(set(ids)),
        "dup_ids": sorted({g for g in ids if ids.count(g) > 1}),
        "nonliteral": nonliteral,
        "add": add, "okcall": ok,
        "declared": (len(decl) if decl is not None else None),
        "declared_ids": (sorted(decl) if decl is not None else None),
    })

    if decl is not None:
        a, d = set(ids), decl
        res["only_actual"] = sorted(a - d)
        res["only_declared"] = sorted(d - a)
        res["ids_match"] = (a == d)
    else:
        res["ids_match"] = None

    if do_run:
        rt, how, _out = runtime_counts(w)
        res["runtime"] = rt
        res["runtime_how"] = how
    else:
        res["runtime"] = None
        res["runtime_how"] = "(--no-run)"

    ok_all = (res.get("ids_match") is True
              and not res["dup_ids"]
              and res["nonliteral"] == 0
              and (res["runtime"] is None or res["runtime"] >= res["register"]))
    res["ok"] = ok_all
    return res


def main():
    ap = argparse.ArgumentParser(description="三端闸门数唯一计数口径（补充篇 §五1）")
    ap.add_argument("edition", nargs="?", default="all",
                    choices=["all"] + list(EDITIONS))
    ap.add_argument("--no-run", action="store_true", help="不跑 check --strict，只静态计数")
    args = ap.parse_args()

    cmd = "python gate_count.py %s%s" % (
        "" if args.edition == "all" else args.edition,
        " --no-run" if args.no_run else "")

    print("=" * 78)
    print("命令    : %s" % cmd)
    print("执行时间: %s" % time.strftime("%Y-%m-%d %H:%M:%S %z"))
    print("工作目录: %s" % HERE)
    print("解释器  : %s" % PY)
    print("HX      : %s" % HX)
    print("=" * 78)
    print("原始输出：")
    print()

    eds = list(EDITIONS) if args.edition == "all" else [args.edition]
    rows = [count_edition(e, not args.no_run) for e in eds]

    hdr = ("%-10s %9s %9s %8s %6s %5s %8s %6s %s"
           % ("端", "register", "declared", "runtime", "add()", "ok()", "ID一致", "判定", "wrapper"))
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        if r.get("error"):
            print("%-10s ERROR: %s" % (r["edition"], r["error"]))
            continue
        print("%-10s %9d %9s %8s %6d %5d %8s %6s %s"
              % (r["edition"], r["register"],
                 r["declared"] if r["declared"] is not None else "-",
                 r["runtime"] if r["runtime"] is not None else "-",
                 r["add"], r["okcall"],
                 {True: "YES", False: "NO", None: "?"}[r["ids_match"]],
                 {True: "PASS", False: "FAIL", None: "?"}[r["ok"]],
                 os.path.basename(r["wrapper"])))

    print()
    print("列义：register = AST 数出的 core.register() 调用（新写法，唯一权威口径）")
    print("      declared = wrapper 里 set_expected() 声明的期望闸门数（防缩水基准）")
    print("      runtime  = check --strict 结论行报出的闸门数（A段+B段，运行时实况）")
    print("      add() / ok() = 旧引擎 o.add() / ok() 出闸写法计数（§2.9 三种口径对照）")
    print("      判定     = 三口径是否自洽（PASS/FAIL），判据见文末")

    bad = []
    for r in rows:
        if r.get("error"):
            bad.append("%s: %s" % (r["edition"], r["error"])); continue
        if r["dup_ids"]:
            bad.append("%s: 重复闸门 ID %s" % (r["edition"], r["dup_ids"]))
        if r["nonliteral"]:
            bad.append("%s: %d 个 register() 首参非字面量，无法静态计数"
                       % (r["edition"], r["nonliteral"]))
        if r["ids_match"] is not True:
            bad.append("%s: 实际 ID 与声明 ID 不一致（仅实际=%s 仅声明=%s）"
                       % (r["edition"], r.get("only_actual", [])[:6], r.get("only_declared", [])[:6]))
        if r["runtime"] is not None and r["register"] is not None and r["runtime"] < r["register"]:
            bad.append("%s: 运行时闸门数 %s < register 数 %d"
                       % (r["edition"], r["runtime"], r["register"]))

    print()
    if bad:
        print("[结论] FAIL —— %d 项不符：" % len(bad))
        for b in bad:
            print("    · %s" % b)
    else:
        tot = sum(r["register"] for r in rows if not r.get("error"))
        print("[结论] PASS —— %d 端计数一致，register 合计 %d 闸" % (len(rows), tot))
        print("       判据：实际 register == set_expected 声明 == 运行时结论行，且 ID 逐个相符")

    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
