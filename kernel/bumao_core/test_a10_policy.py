# -*- coding: utf-8 -*-
# Copyright 2026 Bumao
#
# Licensed under the Apache License, Version 2.0.
#
# SPDX-License-Identifier: Apache-2.0

"""A10 授权闸的可判性用例（随包件，无外部依赖）。

验证四件事：
  1. 无审批册 → 显式判拒（DENY），detail 带「判拒」而非“缺文件”提示；
  2. 有册但无可解析条目 → 判拒（DENY）；
  3. 有册、无当日授权行 → 判拒（DENY）；
  4. 有册、当日授权且版本一致 → PASS；
  5. version_approval_check() 走真实文件路径，detail 以「A10 判定=」开头。

运行：python test_a10_policy.py
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gate_registry as gr  # noqa: E402

LEDGER_OK = """【第 1 号】 2026-11-08
用户批准原文：「同意 0.10 版本上线」
说明：契约 1.23 升 0.10。

"""

LEDGER_OTHER_DAY = """【第 1 号】 2026-11-07
用户批准原文：「同意 0.10 版本上线」

"""

LEDGER_WRONG_VERSION = """【第 1 号】 2026-11-08
用户批准原文：「同意 0.09 版本上线」

"""

LEDGER_UNPARSEABLE = """本册暂无条目。

"""


def _case(name, declared, changed_on, text, want_verdict, want_word):
    r = gr.version_approval(declared, changed_on, text)
    ok = r["verdict"] == want_verdict and want_word in (r["l2_detail"] + r["l3_detail"])
    print("[%s] %s verdict=%s" % ("PASS" if ok else "FAIL", name, r["verdict"]))
    if not ok:
        print("        L2=%s" % r["l2_detail"])
        print("        L3=%s" % r["l3_detail"])
    return ok


def main():
    good = []
    good.append(_case("no-ledger", "0.10", "2026-11-08", "", "DENY", "判拒"))
    good.append(_case("unparseable", "0.10", "2026-11-08", LEDGER_UNPARSEABLE, "DENY", "判拒"))
    good.append(_case("other-day", "0.10", "2026-11-08", LEDGER_OTHER_DAY, "DENY", "无当日"))
    good.append(_case("wrong-version", "0.10", "2026-11-08", LEDGER_WRONG_VERSION, "DENY", "不一致"))
    r = gr.version_approval("0.10", "2026-11-08", LEDGER_OK)
    ok_pass = r["verdict"] == "PASS" and "一致" in r["l3_detail"]
    print("[%s] authorized verdict=%s" % ("PASS" if ok_pass else "FAIL", r["verdict"]))
    good.append(ok_pass)

    tmp = tempfile.mkdtemp(prefix="a10_")
    p = os.path.join(tmp, "shenpi_jilu.txt")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(LEDGER_OK)
    os.environ["XTGL_SHENPI"] = p
    ok, detail, _ = gr.version_approval_check("0.10", "2026-11-08", tmp)
    ok_file = ok and detail.startswith("A10 判定=PASS")
    print("[%s] check-file authorized → %s" % ("PASS" if ok_file else "FAIL", detail))
    good.append(ok_file)

    os.environ.pop("XTGL_SHENPI", None)
    tmp2 = tempfile.mkdtemp(prefix="a10_none_")
    ok2, detail2, _ = gr.version_approval_check("0.10", "2026-11-08", tmp2)
    ok_none = (not ok2) and detail2.startswith("A10 判定=DENY") and "判拒" in detail2
    print("[%s] check-file no-ledger → %s" % ("PASS" if ok_none else "FAIL", detail2))
    good.append(ok_none)

    n = len(good)
    print("A10_POLICY=%d/%d" % (sum(1 for g in good if g), n))
    return 0 if all(good) else 1


if __name__ == "__main__":
    sys.exit(main())
