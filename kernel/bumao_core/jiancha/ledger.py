# -*- coding: utf-8 -*-
"""ledger.py —— 动作级账本（只追加、哈希链、四外键对齐现有票链）。

与现有绿票账本（v2）的关系：
  不另造一套票。每条动作记录嵌一个 ticket 快照（tid＝原票行 sha256 前 16 位），
  tid／run_id／op_id／rule_id／error_code 五个关联键与绿票签发票面同名字段对齐；
  需要回查时拿 tid 去绿票账本里按行哈希找原票，而不是把票面抄一遍当证据。

链规则与绿票账本验链同构：
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

    取最近一张 rc=0 且 source 非反向测试票。tid＝该行原始文本 sha256 前 16 位，
    与绿票逐行读取的算法一致；不改票本、不领用、不写消费账本。
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
        if rec.get("rc") != 0 or rec.get("source") == ("r" + "test"):
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


ANCHOR_SUFFIX = ".anchor"
LOCK_SUFFIX = ".lock"
LOCK_TIMEOUT = 120.0


class FileLock(object):
    """跨进程写锁：Windows 用 msvcrt.locking，POSIX 用 fcntl.lockf。

    锁文件独立于账本，锁住第 0 字节；拿不到锁就重试，超时抛 RuntimeError
    （宁可报错也不在无锁状态下追加）。
    """

    def __init__(self, path, timeout=LOCK_TIMEOUT):
        self.path = os.path.abspath(path)
        self.timeout = timeout
        self._fh = None

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._fh = io.open(self.path, "a+b")
        if os.path.getsize(self.path) == 0:
            self._fh.write(b"\0")
            self._fh.flush()
        self._fh.seek(0)
        deadline = time.time() + self.timeout
        if os.name == "nt":
            import msvcrt
            while True:
                try:
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.time() >= deadline:
                        self._fh.close()
                        self._fh = None
                        raise RuntimeError("动作账本写锁等待超时：%s" % self.path)
                    time.sleep(0.05)
        else:
            import fcntl
            try:
                fcntl.lockf(self._fh.fileno(), fcntl.LOCK_EX)
            except OSError:
                self._fh.close()
                self._fh = None
                raise RuntimeError("动作账本写锁获取失败：%s" % self.path)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._fh is None:
            return False
        try:
            self._fh.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.lockf(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None
        return False


class ActionLedger:
    """一本账＝一条链。账本文件按 run 目录隔离，seq 在该链内单调递增。"""

    def __init__(self, path, seed):
        self.path = os.path.abspath(path)
        self.seed = seed

    def anchor_path(self):
        return self.path + ANCHOR_SUFFIX

    def _write_anchor(self, line, total):
        """把本轮末端哈希写独立锚点文件（落盘 fsync 后原子替换）。"""
        obj = {"schema": "act_anchor/1", "ledger": os.path.basename(self.path),
               "lines": total, "line_sha256": digest(line),
               "at": time.strftime("%Y-%m-%d %H:%M:%S"), "ts": time.time()}
        tmp = self.anchor_path() + ".tmp"
        with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.anchor_path())
        if os.name != "nt":
            d = os.open(os.path.dirname(self.anchor_path()), os.O_RDONLY)
            try:
                os.fsync(d)
            finally:
                os.close(d)

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
            f.flush()
            os.fsync(f.fileno())
        self._write_anchor(line, len(raw_lines(self.path)))
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
        """只追加。prev 由本层现算，调用方不得自带；整段（读锚→写行→fsync→写锚）在写锁内。"""
        with FileLock(self.path + LOCK_SUFFIX):
            prev = self._anchor()
            rec = dict(rec)
            rec["schema"] = "act/1"
            rec.pop("prev", None)
            rec["prev"] = digest(prev)
            line = json.dumps(rec, ensure_ascii=False, sort_keys=True)
            with io.open(self.path, "a", encoding="utf-8", newline="\n") as f:
                f.write(line + "\n")
                f.flush()
                os.fsync(f.fileno())
            lines = raw_lines(self.path)
            tail = lines[-1] if lines else ""
            if tail != line:
                raise RuntimeError("动作账本回读不符，拒绝对外声称已记录")
            self._write_anchor(tail, len(lines))
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
        anchor_ok, anchor_why = False, ""
        ap = self.anchor_path()
        if not os.path.isfile(ap):
            anchor_why = "锚点文件缺失：%s" % os.path.basename(ap)
        else:
            try:
                with io.open(ap, encoding="utf-8") as f:
                    a = json.load(f)
            except (ValueError, OSError) as e:
                anchor_why = "锚点文件无法解析：%s" % e
            else:
                if int(a.get("lines") or 0) != len(lines):
                    anchor_why = "锚点行数 %r 与账本行数 %d 不符" % (a.get("lines"), len(lines))
                elif lines and a.get("line_sha256") != digest(lines[-1]):
                    anchor_why = "锚点末行哈希与账本末行不符"
                else:
                    anchor_ok = True
        if not brk and not anchor_ok:
            brk = anchor_why
        return {"path": self.path, "lines": len(lines), "records": n, "break": brk,
                "anchor": ap, "anchor_ok": anchor_ok}
