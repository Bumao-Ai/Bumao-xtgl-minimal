# -*- coding: utf-8 -*-
"""reasons.py —— 拒绝理由码的唯一入口（码表本体在 schema/reason_codes.json）。

为什么单独成模块：码要同时被三处引用——票面 error_code、动作记录 error_code、导出函数。
写在文档里只能给人看，写在这里才能被代码 import、被 schema enum 引用、被导出件遍历。

用法：
    import reasons
    reasons.text("OUT_OF_SCOPE")          # 一句话中文说明
    reasons.has("INVALID_SCHEMA")         # 是否登记
    reasons.assert_known(code)            # 未登记即抛（防手写错码进票面）
    reasons.export()                      # 结构化全表（给导出件/票面参考）
    reasons.codes()                       # 全部码（给 schema enum 对齐校验）
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = (
    os.path.join(os.path.dirname(HERE), "schema", "reason_codes.json"),   # 沙盒布局
    os.path.join(HERE, "schema", "reason_codes.json"),                    # 随包落地
    os.path.join(HERE, "reason_codes.json"),
)
PATH = next((p for p in CANDIDATES if os.path.isfile(p)), "")


def _load():
    with io.open(PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {c["code"]: c for c in data["codes"]}


CODES = _load()
TEXTS = {k: v["zh"] for k, v in CODES.items()}
LOAD_CODES = frozenset(k for k, v in CODES.items() if v["stage"] == "load")
ACTION_CODES = frozenset(k for k, v in CODES.items() if v["stage"] == "action")
INTEGRATION_CODES = frozenset(k for k, v in CODES.items() if v["stage"] == "integration")


def has(code):
    return str(code or "") in CODES


def text(code, default=""):
    return TEXTS.get(str(code or ""), default)


def assert_known(*codes):
    bad = [c for c in codes if not has(c)]
    if bad:
        raise ValueError("未登记的拒绝理由码：%s" % ", ".join(bad))
    return True


def codes():
    return sorted(CODES)


def export(stage=None):
    rows = [dict(CODES[k]) for k in codes()]
    if stage:
        rows = [r for r in rows if r["stage"] == stage]
    return {"schema": "reason_codes/1", "codes": rows}
