# -*- coding: utf-8 -*-
"""ledger.py —— 动作级账本（只追加、哈希链、四外键对齐现有票链）。

与现有绿票账本（lvpiao/2）的关系：
  不另造一套票。每条动作记录嵌一个 ticket 快照（tid＝原票行 sha256 前 16 位），
  tid／run_id／op_id／rule_id／error_code 五个关联键与 lvpiao.issue() 票面同名字段对齐；
  需要回查时拿 tid 去 check_lvpiao.jsonl 里按行哈希找原票，而不是把票面抄一遍当证据。

链规则与 lvpiao.verify 同构：
  每行 prev＝上一行原始文本的 sha256；首行 prev＝参数件 chain_seed。
  这样动作账本自身也能一条命令验完整性，断点能定位到行号。

只追加、不回改：结果标记（denied/interrupted/ok）写在该动作自己的记录里；
中断之后新增的记录（recovery/resume）另起 seq，不改前一条。
"""
import hashlib
import io
import json
import os
import time
import uuid

OP_ENV = "BUMO_OP_ID"
RUN_ENV = "BUMO_RUN_ID"


def new_run_id():
    return str(uuid.uuid4())


def current_run_id():
    rid = os.environ.get(RUN_ENV) or ""
    if not rid:
        rid = new_run_id()
        os.environ[RUN_ENV] = rid
    return rid


def current_op_id():
    op = os.environ.get(OP_ENV) or ""
    if not op:
        op = "op-%s-%d-%s" % (time.strftime("%Y%m%dT%H%M%S"), os.getpid(),
                              uuid.uuid4().hex[:6])
        os.environ[OP_ENV] = op
    return op


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def raw_lines(path):
    if not os.path.isfile(path):
        return []
    out = []
    with io.open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.rstrip("\n")
            if ln.strip():
                out.append(ln)
    return out


def ticket_snapshot(lab_root, cfg):
    """只读现有绿票账本，返回 (ticket_dict_or_None, why)。

    取最近一张 rc=0 且 source!=rtest 的票。tid＝该行原始文本 sha256 前 16 位，
    与 lvpiao.raw_tickets 的算法一致；不改票本、不领用、不写消费账本。
    """
    rel = str(cfg.get("ticket_ledger") or "").strip()
    if not rel:
        return None, "参数件未配置 ticket_ledger"
    path = os.path.abspath(os.path.join(lab_root, rel))
    if not os.path.isfile(path):
        return None, "现有票本不存在（只读引用失败）：%s" % os.path.basename(path)
    pair = None
    for ln in raw_lines(path):
        try:
            rec = json.loads(ln)
        except ValueError:
            continue
        if rec.get("kind") == "genesis":
            continue
        if rec.get("rc") != 0 or rec.get("source") == "rtest":
            continue
        pair = (rec, hashlib.sha256(ln.encode("utf-8")).hexdigest()[:16])
    if not pair:
        return None, "票本里没有 rc=0 的真跑票"
    rec, tid = pair
    return {
        "tid": tid,
        "at": rec.get("at", ""),
        "rc": rec.get("rc"),
        "run_id": rec.get("run_id", ""),
        "op_id": rec.get("op_id", ""),
        "rule_id": rec.get("rule_id", "*"),
        "error_code": rec.get("error_code", ""),
        "conclusion": (rec.get("conclusion") or "")[:120],
        "out_sha256": (rec.get("out_sha256") or "")[:16],
        "state": "attached",
    }, ""


def resolve_tid(lab_root, cfg, tid):
    """按 tid 回查原票（只读）。返回票 dict 或 None。"""
    rel = str(cfg.get("ticket_ledger") or "").strip()
    path = os.path.abspath(os.path.join(lab_root, rel)) if rel else ""
    if not path or not os.path.isfile(path):
        return None
    for ln in raw_lines(path):
        if hashlib.sha256(ln.encode("utf-8")).hexdigest()[:16] != tid:
            continue
        try:
            return json.loads(ln)
        except ValueError:
            return None
    return None


class ActionLedger:
    """一本账＝一条链。账本文件按 run 目录隔离，seq 在该链内单调递增。"""

    def __init__(self, path, seed):
        self.path = os.path.abspath(path)
        self.seed = seed

    def _anchor(self):
        lines = raw_lines(self.path)
        if lines:
            return lines[-1]
        gen = {"schema": "act/1", "kind": "genesis", "seed": self.seed,
               "at": time.strftime("%Y-%m-%d %H:%M:%S"), "ts": time.time()}
        line = json.dumps(gen, ensure_ascii=False)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with io.open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(line + "\n")
        return line

    def records(self):
        out = []
        for ln in raw_lines(self.path):
            try:
                rec = json.loads(ln)
            except ValueError:
                continue
            if rec.get("kind") == "genesis":
                continue
            out.append(rec)
        return out

    def next_seq(self):
        recs = self.records()
        return (max(int(r.get("seq") or 0) for r in recs) if recs else 0) + 1

    def append(self, rec):
        """只追加。prev 由本层现算，调用方不得自带。"""
        prev = self._anchor()
        rec = dict(rec)
        rec["schema"] = "act/1"
        rec.pop("prev", None)
        rec["prev"] = digest(prev)
        line = json.dumps(rec, ensure_ascii=False, sort_keys=True)
        with io.open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(line + "\n")
        with io.open(self.path, encoding="utf-8") as f:
            tail = [l.rstrip("\n") for l in f if l.strip()][-1]
        if tail != line:
            raise RuntimeError("动作账本回读不符，拒绝对外声称已记录")
        return rec

    def verify(self):
        lines = raw_lines(self.path)
        prev = self.seed
        n, brk = 0, ""
        for i, ln in enumerate(lines, 1):
            try:
                rec = json.loads(ln)
            except ValueError:
                brk = "第 %d 行不是合法 JSON" % i
                break
            if rec.get("kind") == "genesis":
                if rec.get("seed") != self.seed:
                    brk = "第 %d 行起点种子不符" % i
                    break
            elif rec.get("prev") != prev:
                brk = "第 %d 行 prev 不符（上一行被改/插入/删除）" % i
                break
            else:
                n += 1
            prev = digest(ln)
        return {"path": self.path, "lines": len(lines), "records": n, "break": brk}
