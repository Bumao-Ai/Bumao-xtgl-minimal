#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bumao Core 契约测试（可移植脱敏版，随 core 仓发布）。

只依赖 Python 标准库；在 core 仓根目录运行，默认读取同目录的
kernel_contract.json 与 bumao_core/。

与原内部版差别（仅去本机化，不放宽断言）：
  1. 只测仓内实物：bumao_core/*.py、kernel_contract.json、本文件；
     发行端 web 实现（xtgl_core.py 等）不在本仓，相关的 A/B/C/C2/D/G 组
     在原版中依赖发行端，这里改为仓内题目可跑通的等价断言。
  2. 版本值以契约自身为准，不钉字面量；contract_version 形态与日期形态照查。
  3. 隔离扫描只查通用本机形态（盘符绝对路径、用户主目录、UNC），
     不再携带任何本机用户名、盘内根目录或私有目录名字面量。
  4. 用法不再接受「端 web 目录」参数。
  5. 内部专用件（facts.py／facts_check.py／portability_probe.py）**不属于契约范围**，
     已写进 HOST_CONTRACT.md §十。缺失时打印 N/A 与范围理由，既不计 FAIL 也不计 SKIP；
     若使用者自备同名文件，仍参与编译与隔离扫描。

用法：
    python contract_test.py            # 在 core 仓根目录
    python contract_test.py --selftest # 临时目录造假文件，逐组验证正反两向

退出码：0 = 全绿；1 = 有 FAIL。
"""
import argparse
import json
import os
import py_compile
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT_PATH = HERE / "kernel_contract.json"
CORE_DIR = HERE / "bumao_core"

CORE_FILES = (
    "bumao_core_gates.py",
    "bumao_core_rules.py",
    "engine.py",
    "gate_count.py",
    "gate_registry.py",
    "host_reference.py",
    "test_a10_policy.py",
    "test_check_rc.py",
    "test_equivalence.py",
    "test_gate_registry.py",
)

# 契约范围外（HOST_CONTRACT.md §十）：不是可选依赖，不靠「跳过」糊过去。
# 这些件按定义不参与契约判定，缺件判 N/A（不适用）；若自备同名文件，仍参与编译与隔离扫描。
CONTRACT_EXCLUDED = {
    "facts.py": "内部文档事实源生成器：依赖内部多端目录树（台账/视图/规则层），"
                "不属于宿主契约面，故不随包、不参与判定。",
    "facts_check.py": "facts.py 的配套校验器：输入为内部 facts.json，"
                      "不属于宿主契约面，故不随包、不参与判定。",
    "portability_probe.py": "内部可迁移性探针：按内部目录树与本机临时区布局编写，"
                            "不属于宿主契约面，故不随包、不参与判定。",
}

RE_VERSION = re.compile(r"^\d+\.\d+(?:\.\d+)?$")
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# 只认「真的像路径」的形态：盘符后至少一段目录、UNC 至少两级、Users 后有名字。
RE_DRIVE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:\\[A-Za-z0-9_.-]+")
RE_HOME = re.compile(r"(?:\\|/)Users(?:\\|/)[A-Za-z0-9_.<>-]+")
RE_UNC = re.compile(r"\\\\[A-Za-z0-9_][A-Za-z0-9_.-]*\\[A-Za-z0-9_][A-Za-z0-9_.-]*")
ABS_PATTERNS = (RE_DRIVE, RE_HOME, RE_UNC)


class Report:
    def __init__(self):
        self.lines = []
        self.fail = 0
        self.checks = 0
        self.na_count = 0

    def ok(self, group, name, detail=""):
        self.checks += 1
        self.lines.append("[PASS][%s] %s%s" % (group, name, ("：" + detail) if detail else ""))

    def bad(self, group, name, detail=""):
        self.checks += 1
        self.fail += 1
        self.lines.append("[FAIL][%s] %s%s" % (group, name, ("：" + detail) if detail else ""))

    def na(self, group, name, reason=""):
        self.na_count += 1
        self.lines.append("[N/A][%s] %s%s" % (group, name, ("：" + reason) if reason else ""))

    def expect(self, group, name, cond, detail=""):
        if cond:
            self.ok(group, name, detail)
        else:
            self.bad(group, name, detail)
        return bool(cond)


def read_text_lossy(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def group_a(report, contract_path=CONTRACT_PATH):
    """契约载入与元信息形态。"""
    try:
        doc = load_json(contract_path)
    except (OSError, ValueError) as e:
        report.bad("A", "kernel_contract.json 可解析", str(e))
        return None
    report.ok("A", "kernel_contract.json 可解析")
    meta = doc.get("meta") if isinstance(doc, dict) else None
    if not isinstance(meta, dict):
        report.bad("A", "meta 存在且为对象")
        return doc
    report.expect("A", "meta.status=frozen", meta.get("status") == "frozen", str(meta.get("status")))
    cv = str(meta.get("contract_version") or "")
    report.expect("A", "contract_version 形态", bool(RE_VERSION.match(cv)), cv)
    for key in ("frozen_at", "updated_at"):
        v = str(meta.get(key) or "")
        report.expect("A", "%s 为 ISO 日期" % key, bool(RE_DATE.match(v)), v)
    report.expect("A", "principles 非空", bool(meta.get("principles")))
    return doc


def group_b(report, core_dir=CORE_DIR):
    """仓内核心文件在位且非空。"""
    missing = []
    empty = []
    for name in CORE_FILES:
        p = Path(core_dir) / name
        if not p.is_file():
            missing.append(name)
        elif p.stat().st_size <= 0:
            empty.append(name)
    report.expect("B", "核心文件 %d 件在位" % len(CORE_FILES), not missing, str(missing))
    report.expect("B", "核心文件非空", not empty, str(empty))
    for name, reason in CONTRACT_EXCLUDED.items():
        if not (Path(core_dir) / name).is_file():
            report.na("B", "契约范围外 " + name, reason)


def group_c(report, core_dir=CORE_DIR):
    """仓内核心文件可编译（编译产物落临时目录，不写仓）。"""
    bad = []
    names = list(CORE_FILES)
    names += [n for n in CONTRACT_EXCLUDED if (Path(core_dir) / n).is_file()]
    with tempfile.TemporaryDirectory(prefix="core_contract_") as td:
        for name in names:
            src = Path(core_dir) / name
            if not src.is_file():
                bad.append(name + ":缺件")
                continue
            try:
                py_compile.compile(str(src), cfile=os.path.join(td, name + "c"), doraise=True)
            except py_compile.PyCompileError as e:
                bad.append(name + ":" + str(e).splitlines()[0][:80])
    report.expect("C", "核心文件全部可编译", not bad, str(bad))


def _evidence_paths(node):
    if isinstance(node, dict):
        if isinstance(node.get("path"), str):
            yield node["path"]
        for v in node.values():
            for x in _evidence_paths(v):
                yield x
    elif isinstance(node, list):
        for v in node:
            for x in _evidence_paths(v):
                yield x


def group_d(report, contract_path=CONTRACT_PATH, here=HERE):
    """契约里的仓内证据路径必须真实存在（非仓内角色引用不计）。"""
    try:
        doc = load_json(contract_path)
    except (OSError, ValueError) as e:
        report.bad("D", "契约可解析以校验证据路径", str(e))
        return
    checked, missing = 0, []
    for raw in _evidence_paths(doc):
        p = raw.split(" + ")[0].strip()
        if not p.startswith("bumao_core/"):
            continue
        checked += 1
        if not (Path(here) / p).is_file():
            missing.append(p)
    report.expect("D", "仓内证据路径存在", not missing and checked > 0,
                  "校验 %d 条；缺 %s" % (checked, missing))


def _scan_text(text):
    hits = []
    for pat in ABS_PATTERNS:
        m = pat.search(text)
        if m:
            hits.append(m.group(0))
    return hits


def group_f(report, contract_path=CONTRACT_PATH):
    """契约内不得出现本机绝对路径形态。"""
    try:
        doc = load_json(contract_path)
    except (OSError, ValueError) as e:
        report.bad("F", "契约可解析以做隔离扫描", str(e))
        return
    hits = []
    for v in _all_strings(doc):
        hits.extend(_scan_text(v))
    report.expect("F", "契约无本机绝对路径", not hits, str(hits[:5]))


def _all_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for v in node:
            for x in _all_strings(v):
                yield x
    elif isinstance(node, dict):
        for k, v in node.items():
            yield str(k)
            for x in _all_strings(v):
                yield x


def group_e(report, paths):
    """仓内发布件不得出现本机绝对路径形态。"""
    hits = []
    for p in paths:
        if not Path(p).is_file():
            continue
        text = read_text_lossy(p)
        for h in _scan_text(text):
            hits.append("%s:%s" % (Path(p).name, h))
    report.expect("E", "发布件无本机绝对路径", not hits, str(hits[:5]))


def run_target() -> int:
    report = Report()
    group_a(report)
    group_b(report)
    group_c(report)
    group_d(report)
    group_f(report)
    scope = [CONTRACT_PATH, Path(__file__)] + [CORE_DIR / n for n in CORE_FILES]
    scope += [CORE_DIR / n for n in CONTRACT_EXCLUDED if (CORE_DIR / n).is_file()]
    scope += [HERE / n for n in ("README.md", "LICENSE", "NOTICE") if (HERE / n).is_file()]
    group_e(report, scope)
    for line in report.lines:
        print(line)
    print("\n[%s] %d 项，%d FAIL，0 SKIP，%d N/A" % (
        "ALL PASS" if report.fail == 0 else "FAIL",
        report.checks, report.fail, report.na_count))
    return 0 if report.fail == 0 else 1


def _fake_contract(path, *, bad_json=False, status="frozen", version="1.0",
                   evidence="bumao_core/engine.py", abs_path=None):
    doc = {"meta": {"status": status, "contract_version": version,
                    "frozen_at": "2026-01-01", "updated_at": "2026-01-01",
                    "principles": ["小内核"]},
           "evidence": [{"path": evidence}]}
    if abs_path:
        doc["leak"] = abs_path
    text = "{" if bad_json else json.dumps(doc, ensure_ascii=False)
    Path(path).write_text(text, encoding="utf-8")


def _fake_core(root):
    d = Path(root) / "bumao_core"
    d.mkdir(parents=True, exist_ok=True)
    for n in CORE_FILES:
        (d / n).write_text("x = 1\n", encoding="utf-8")
    return d


def selftest() -> int:
    fails = []

    def check(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        if not cond:
            fails.append(name)

    with tempfile.TemporaryDirectory(prefix="core_selftest_") as td:
        root = Path(td)
        core = _fake_core(root)
        good = root / "good.json"
        _fake_contract(good)
        r = Report()
        group_a(r, good)
        check("A 正例全绿", r.fail == 0)
        bad = root / "bad.json"
        _fake_contract(bad, bad_json=True)
        r = Report()
        group_a(r, bad)
        check("A 反例：坏 JSON 报红", r.fail == 1)
        r = Report()
        _fake_contract(good, status="draft")
        group_a(r, good)
        check("A 反例：status 非 frozen 报红", r.fail == 1)

        r = Report()
        group_b(r, core)
        check("B 正例全绿", r.fail == 0)
        (core / "engine.py").unlink()
        r = Report()
        group_b(r, core)
        check("B 反例：缺件报红", r.fail == 1)
        (core / "engine.py").write_text("x = 1\n", encoding="utf-8")

        r = Report()
        group_c(r, core)
        check("C 正例全绿", r.fail == 0)
        (core / "engine.py").write_text("def (\n", encoding="utf-8")
        r = Report()
        group_c(r, core)
        check("C 反例：语法错报红", r.fail == 1)
        (core / "engine.py").write_text("x = 1\n", encoding="utf-8")

        r = Report()
        group_d(r, good, root)
        check("D 正例全绿", r.fail == 0)
        _fake_contract(good, evidence="bumao_core/no_such.py")
        r = Report()
        group_d(r, good, root)
        check("D 反例：证据缺件报红", r.fail == 1)

        leak = "D:" + chr(92) + "secret" + chr(92) + "x.txt"
        leak_file = root / "leak.txt"
        leak_file.write_text("path = " + leak + "\n", encoding="utf-8")
        r = Report()
        group_e(r, [leak_file])
        check("E 反例：盘符绝对路径报红", r.fail == 1)
        clean_file = root / "clean.txt"
        clean_file.write_text("path = bumao_core/engine.py\n", encoding="utf-8")
        r = Report()
        group_e(r, [clean_file])
        check("E 正例全绿", r.fail == 0)

    print("\nALL PASS" if not fails else "\nFAILED: " + str(fails))
    return 0 if not fails else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    return run_target()


if __name__ == "__main__":
    sys.exit(main())
