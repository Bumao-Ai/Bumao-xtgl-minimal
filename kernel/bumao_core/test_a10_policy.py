# -*- coding: utf-8 -*-
# Copyright 2026 Bumao
#
# Licensed under the Apache License, Version 2.0.
#
# SPDX-License-Identifier: Apache-2.0

"""A10 授权闸的三态用例（随包件，无外部依赖）。

三态与四条覆盖：
  1. 未变更（契约 updated_at 早于最近授权日）→ PASS
  2. 有变更、变更当日无授权 → DENY
  3. 有变更、变更当日有授权 → PASS
  4. 判不了（缺字段／日期非法／无审批册／无可解析授权条目）→ DENY
另核 version_approval_check() 走真实文件路径时的 detail 前缀与三态标记。

运行：python test_a10_policy.py
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gate_registry as gr  # noqa: E402

LEDGER_1107 = """【第 1 号】 2026-11-07
用户批准原文：「授权」

"""

LEDGER_1108 = """【第 2 号】 2026-11-08
用户批准原文：「授权 0.09」

"""

LEDGER_NONAUTH = """【第 1 号】 2026-11-08
用户批准原文：「驳回」

"""

LEDGER_UNPARSEABLE = """本册暂无条目。

"""


def _case(name, declared, changed_on, text, want_verdict, want_word):
    r = gr.version_approval(declared, changed_on, text)
    ok = r["verdict"] == want_verdict and want_word in (r["l2_detail"] + r["l3_detail"])
    print("[%s] %s verdict=%s state=%s" % ("PASS" if ok else "FAIL", name,
                                           r["verdict"], r["state"]))
    if not ok:
        print("        L2=%s" % r["l2_detail"])
        print("        L3=%s" % r["l3_detail"])
    return ok


def main():
    good = []

    # 三态一：未变更 → PASS
    good.append(_case("unchanged(contract 11-07, auth 11-08)", "0.10",
                      "2026-11-07", LEDGER_1108, "PASS", "未变更"))

    # 三态二：有变更、当日无授权 → DENY
    good.append(_case("changed-unauthorized", "0.10",
                      "2026-11-08", LEDGER_1107, "DENY", "无授权条目"))

    # 三态二：有变更、当日有授权 → PASS（不再比较版本号，跨轴问题消失）
    good.append(_case("changed-authorized", "0.10",
                      "2026-11-08", LEDGER_1108, "PASS", "有变更"))

    # 三态三：判不了 → DENY
    good.append(_case("unjudged-missing-field", "", "2026-11-08",
                      LEDGER_1108, "DENY", "判不了"))
    good.append(_case("unjudged-bad-date", "0.10", "2026-11-31",
                      LEDGER_1108, "DENY", "判不了"))
    good.append(_case("unjudged-no-ledger", "0.10", "2026-11-08",
                      "", "DENY", "判不了"))
    good.append(_case("unjudged-unparseable", "0.10", "2026-11-08",
                      LEDGER_UNPARSEABLE, "DENY", "判不了"))
    good.append(_case("unjudged-no-auth-entry", "0.10", "2026-11-08",
                      LEDGER_NONAUTH, "DENY", "判不了"))

    # 真实文件路径：有当日授权 → PASS
    tmp = tempfile.mkdtemp(prefix="a10_")
    p = os.path.join(tmp, "shenpi_jilu.txt")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(LEDGER_1108)
    os.environ["XTGL_SHENPI"] = p
    ok, detail, _ = gr.version_approval_check("0.10", "2026-11-08", tmp)
    ok_file = ok and detail.startswith("A10 判定=PASS") and "三态=changed" in detail
    print("[%s] check-file authorized → %s" % ("PASS" if ok_file else "FAIL", detail))
    good.append(ok_file)

    # 真实文件路径：无审批册 → 判不了 DENY
    os.environ.pop("XTGL_SHENPI", None)
    tmp2 = tempfile.mkdtemp(prefix="a10_none_")
    ok2, detail2, _ = gr.version_approval_check("0.10", "2026-11-08", tmp2)
    ok_none = (not ok2) and detail2.startswith("A10 判定=DENY") and "判不了" in detail2
    print("[%s] check-file no-ledger → %s" % ("PASS" if ok_none else "FAIL", detail2))
    good.append(ok_none)

    n = len(good)
    print("A10_TRISTATE=%d/%d" % (sum(1 for g in good if g), n))
    return 0 if all(good) else 1


if __name__ == "__main__":
    sys.exit(main())
