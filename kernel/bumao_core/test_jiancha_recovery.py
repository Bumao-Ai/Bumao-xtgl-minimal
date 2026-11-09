# -*- coding: utf-8 -*-
"""supervisor 恢复测试：进程意外退出后恢复、恢复失败、回滚失败。"""

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bumao_core.jiancha import scope
from bumao_core.jiancha.ledger import ActionLedger, digest, sha_file
from bumao_core.jiancha.supervisor import HaltSignal, Supervisor

RESULTS = []


def check(label, ok, detail=""):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + label + (("  :: %s" % detail) if detail else ""))


def order_for(ws_rel="ws", oid="t-recovery"):
    return {
        "schema": "intent/1",
        "order_id": oid,
        "workspace": ws_rel,
        "approved_at": "2026-11-09 10:00:00",
        "approved_by": "user",
        "approved_roots": ["ok"],
        "approved_files": [],
        "denied_zones": ["secret"],
        "allowed_actions": ["file_write"],
        "expires_at": "",
        "demo_only": True,
    }


CFG = {"ledger": "actions.ledger", "chain_seed": "t-recovery-seed",
       "baseline_dir": "baseline", "watch_scope": ".", "force_ticket": False}

WORKER = r"""
import json, os, sys
sys.path.insert(0, os.environ["T_REC_REPO"])
from bumao_core.jiancha.supervisor import Supervisor
root = os.environ["T_REC_ROOT"]; run = os.environ["T_REC_RUN"]
cfg = json.loads(os.environ["T_REC_CFG"]); order = json.loads(os.environ["T_REC_ORDER"])
sup = Supervisor(root, cfg, run, order, source="demo", entry="test:crash")
sup.begin()
ws = os.path.join(root, order["workspace"])
leak = os.path.join(ws, "secret", "leak.txt")
os.makedirs(os.path.dirname(leak), exist_ok=True)
with open(leak, "w", encoding="utf-8") as f:
    f.write("leaked")
print("WROTE_LEAK")
sys.stdout.flush()
os._exit(7)
"""


def main():
    os.environ["BUMO_JIANCHA_ENV"] = "sandbox"
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = tempfile.mkdtemp(prefix="t_rec_")
    run = os.path.join(root, "run")
    os.makedirs(os.path.join(root, "ws"))

    # ---- A. 进程意外退出（os._exit）后，新进程发现漂移→中断→恢复清理
    env = dict(os.environ)
    env.update({"T_REC_REPO": repo, "T_REC_ROOT": root, "T_REC_RUN": run,
                "T_REC_CFG": json.dumps(CFG, ensure_ascii=False),
                "T_REC_ORDER": json.dumps(order_for(), ensure_ascii=False)})
    p = subprocess.Popen([sys.executable, "-c", WORKER], env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _out, err = p.communicate()
    check("意外退出进程非 0 退出", p.returncode == 7, "rc=%d err=%s"
          % (p.returncode, err.decode("utf-8", "replace")[-160:]))
    leak = os.path.join(root, "ws", "secret", "leak.txt")
    check("退出时未授权文件已落盘", os.path.isfile(leak))

    sup = Supervisor(root, CFG, run, order_for(), source="demo", entry="test:recover")
    halted = False
    try:
        sup.guard({"action_type": "file_write", "target": "ok/a.txt", "content": "A"})
    except HaltSignal:
        halted = True
    check("新进程发现入口外改动并中断", halted, "status=%s" % sup.state.get("status"))
    admin = ActionLedger(os.path.join(run, "actions.ledger"), CFG["chain_seed"])
    check("意外退出后账本链仍完整", admin.verify()["break"] == "", admin.verify()["break"])

    rec = sup.recover_restore()
    check("恢复成功记账 ok", rec["result"] == "ok", "seq=%s" % rec.get("seq"))
    check("未授权文件被清理", not os.path.isfile(leak))
    check("状态置 recovered", sup.state.get("recovered") is True
          and sup.state.get("halt", {}).get("recovered") is True)
    check("账本链覆盖到恢复记录", admin.verify()["records"] >= 3
          and admin.verify()["anchor_ok"] is True)

    # ---- B. 恢复失败：基线副本缺失，整轮 fail，抛错，不置 recovered
    root2 = tempfile.mkdtemp(prefix="t_rec_fail_")
    run2 = os.path.join(root2, "run")
    os.makedirs(os.path.join(root2, "ws"))
    sup2 = Supervisor(root2, CFG, run2, order_for(oid="t-recovery-fail"),
                      source="demo", entry="test:recfail")
    sup2.begin()
    rel = "secret/leak2.txt"
    target = os.path.join(root2, "ws", "secret", "leak2.txt")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write("changed")
    sup2.state["baseline_manifest"][rel] = digest("baseline-bytes")
    sup2.state["status"] = "halted"
    sup2.state["halt"] = {"trigger": "test", "reason": "test", "seq": 0,
                          "bundle": "", "affected": [rel], "record": {},
                          "recovered": False}
    sup2._save_state()
    try:
        sup2.recover_restore()
        failed_raised = False
    except RuntimeError as e:
        failed_raised = "恢复失败" in str(e)
        print("EXPECTED_ERROR %s" % e)
    check("基线副本缺失时恢复报错", failed_raised)
    L2 = ActionLedger(os.path.join(run2, "actions.ledger"), CFG["chain_seed"])
    last = L2.records()[-1]
    check("恢复失败记 RESTORE_FAILED", last.get("error_code") == "RESTORE_FAILED"
          and last.get("result") == "fail", json.dumps(last.get("evidence", {}), ensure_ascii=False)[:120])
    check("恢复失败不置 recovered", sup2.state.get("recovered") is not True
          and sup2.state.get("halt", {}).get("recovered") is False)

    # ---- C. 回滚失败：基线副本哈希与动作前快照不符 → unrecoverable，不覆盖
    root3 = tempfile.mkdtemp(prefix="t_rec_rb_")
    run3 = os.path.join(root3, "run")
    os.makedirs(os.path.join(root3, "ws"))
    sup3 = Supervisor(root3, CFG, run3, order_for(oid="t-recovery-rb"),
                      source="demo", entry="test:rollback")
    sup3.begin()
    ws3 = sup3.workspace
    os.makedirs(os.path.join(ws3, "ok"), exist_ok=True)
    tgt = os.path.join(ws3, "ok", "a.txt")
    with open(tgt, "w", encoding="utf-8") as f:
        f.write("NEW-MAIN")
    sneaky = os.path.join(ws3, "secret", "b.txt")
    os.makedirs(os.path.dirname(sneaky), exist_ok=True)
    with open(sneaky, "w", encoding="utf-8") as f:
        f.write("NEW-SIDE")
    base_src = os.path.join(sup3.baseline_dir, "secret", "b.txt")
    os.makedirs(os.path.dirname(base_src), exist_ok=True)
    with open(base_src, "w", encoding="utf-8") as f:
        f.write("WRONG-BASELINE")
    before = {"secret/b.txt": digest("ORIGINAL-SIDE")}
    rows = sup3._rollback_post_fail("ok/a.txt", before, None, ["secret/b.txt"])
    row = next((r for r in rows if r["target"] == "secret/b.txt"), {})
    check("回滚失败记 unrecoverable", row.get("action") == "unrecoverable"
          and row.get("restored") is False, json.dumps(row, ensure_ascii=False))
    check("回滚失败不覆盖当前字节", open(sneaky, encoding="utf-8").read() == "NEW-SIDE")
    main_row = next((r for r in rows if r["target"] == "ok/a.txt"), {})
    check("主目标回滚按动作前状态处理", main_row.get("action") == "remove_added"
          and main_row.get("restored") is True, json.dumps(main_row, ensure_ascii=False))

    print("ALL PASS" if all(RESULTS) else "HAS FAIL")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
