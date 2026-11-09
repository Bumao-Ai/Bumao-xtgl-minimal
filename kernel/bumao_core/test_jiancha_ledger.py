# -*- coding: utf-8 -*-
"""ledger 测试：多进程并发写、锚点一致性、进程被强杀后继续写。"""

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bumao_core.jiancha.ledger import ActionLedger

RESULTS = []
WORKERS = 6
PER_WORKER = 12


def check(label, ok, detail=""):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + label + (("  :: %s" % detail) if detail else ""))


WORKER = r"""
import os, sys
sys.path.insert(0, os.environ["T_LEDGER_REPO"])
from bumao_core.jiancha.ledger import ActionLedger
L = ActionLedger(os.environ["T_LEDGER_PATH"], os.environ["T_LEDGER_SEED"])
w = int(os.environ["T_LEDGER_WID"])
for i in range(int(os.environ["T_LEDGER_N"])):
    L.append({"kind": "act", "worker": w, "i": i, "result": "ok"})
if os.environ.get("T_LEDGER_CRASH") == "1":
    os._exit(7)
"""


def main():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = tempfile.mkdtemp(prefix="t_ledger_")
    path = os.path.join(root, "actions.ledger")
    seed = "t-ledger-seed"

    env = dict(os.environ)
    env.update({"T_LEDGER_REPO": repo, "T_LEDGER_PATH": path,
                "T_LEDGER_SEED": seed, "T_LEDGER_N": str(PER_WORKER)})
    procs = []
    for w in range(WORKERS):
        e = dict(env)
        e["T_LEDGER_WID"] = str(w)
        procs.append(subprocess.Popen([sys.executable, "-c", WORKER], env=e,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE))
    rcs = []
    for p in procs:
        _out, err = p.communicate()
        rcs.append(p.returncode)
        if p.returncode != 0:
            print("WORKER_FAIL rc=%d %s" % (p.returncode, err.decode("utf-8", "replace")[-200:]))
    check("并发写各进程 rc=0", all(rc == 0 for rc in rcs), "%r" % rcs)

    L = ActionLedger(path, seed)
    v = L.verify()
    ok = (v["break"] == "" and v["anchor_ok"] is True
          and v["records"] == WORKERS * PER_WORKER and len(L.records()) == WORKERS * PER_WORKER)
    check("并发写后链完整、条数齐全、锚点一致", ok, json.dumps(v, ensure_ascii=False))

    # 锚点篡改必须验不过
    with open(L.anchor_path(), "w", encoding="utf-8") as f:
        f.write(json.dumps({"schema": "act_anchor/1", "lines": 1,
                            "line_sha256": "0" * 64}) + "\n")
    v2 = L.verify()
    check("锚点被篡改后验不过", v2["break"] != "" and v2["anchor_ok"] is False,
          v2.get("break", ""))

    # 进程被强杀（os._exit）后：写锁由系统释放，新进程可继续追加且链仍完整
    crash_path = os.path.join(root, "crash.ledger")
    ce = dict(env)
    ce.update({"T_LEDGER_PATH": crash_path, "T_LEDGER_WID": "9",
               "T_LEDGER_N": "3", "T_LEDGER_CRASH": "1"})
    p = subprocess.Popen([sys.executable, "-c", WORKER], env=ce,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _out, err = p.communicate()
    check("被强杀进程退出码非 0", p.returncode != 0, "rc=%d" % p.returncode)

    C = ActionLedger(crash_path, seed)
    C.append({"kind": "act", "worker": 10, "i": 0, "result": "ok"})
    v3 = C.verify()
    check("强杀后恢复写入且链完整", v3["break"] == "" and v3["anchor_ok"] is True,
          json.dumps(v3, ensure_ascii=False))
    check("强杀前 3 条 + genesis + 恢复 1 条",
          v3["lines"] == 1 + 3 + 1 and v3["records"] == 4,
          "lines=%d records=%d" % (v3["lines"], v3["records"]))

    print("ALL PASS" if all(RESULTS) else "HAS FAIL")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
