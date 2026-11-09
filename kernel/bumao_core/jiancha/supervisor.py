# -*- coding: utf-8 -*-
"""supervisor.py —— 执行中监管核心：同步检查点、周期断言、越界中断、留证与恢复。

检查点分三段（同步阻塞 / 半阻塞 / 只能事后）：
  S0 动作前（同步阻塞）：意图单有效 → 动作类型允许 → 目标形态合法 → 在批准集合内
                         → 不在拒绝区 → 基线未漂移 → 有 rc=0 绿票可关联。
                         任一 fail：动作不执行，写 denied 记录，立即中断序列。
  S1 动作后（同步、只能事后补刀）：目标哈希与预期一致 → 目标仍在范围内
                         → 本次动作窗口内是否出现未声明的额外汇出。
                         额外汇出已经落盘，拦不住那一下；能立即中断后续动作并留证。
  P  周期断言（半阻塞）：每个动作前比对「上次快照 vs 当前快照」，发现未经本入口的改动
                         即中断；它挡得住下一步，挡不住已经发生的那一步。

中断不是「报个错退出」：halt 前生成证据包（halt.json／前后镜像／diff／账本快照／
manifest.sha256），状态置 halted，后续动作在 resume 前一律拒绝。恢复分两步：
recover --restore 清理未授权产物；resume --approval 必须由人给出的批准件放行。
"""
import hashlib
import io
import json
import os
import shutil
import time

from . import reasons
from . import scope
from .ledger import ActionLedger, current_op_id, current_run_id, digest, sha_file, ticket_snapshot

ERR = dict(reasons.TEXTS)   # 码表唯一来源：schema/reason_codes.json


class HaltSignal(Exception):
    """越界中断。携带动作记录与证据包路径，调用方不得吞掉当普通错误处理。"""

    def __init__(self, record, bundle, reason):
        self.record = record
        self.bundle = bundle
        self.reason = reason
        super().__init__("越界中断：%s｜证据：%s" % (reason, bundle))


class ToolError(Exception):
    """工具自身的业务报错。不是越界：记账为 result=error，但仍走 S1 窗口扫描。"""

    def __init__(self, code, detail=""):
        self.code = str(code or "TOOL_ERROR")
        self.detail = detail
        super().__init__(detail or self.code)


class Supervisor:
    def __init__(self, lab_root, cfg, run_dir, order, source="demo", entry="entry:cli"):
        self.lab_root = os.path.abspath(lab_root)
        self.cfg = cfg
        self.run_dir = os.path.abspath(run_dir)
        os.makedirs(self.run_dir, exist_ok=True)
        self.order = order
        self.workspace = scope.workspace_abs(self.lab_root, order)
        if not os.path.isdir(self.workspace):
            raise scope.ScopeError("workspace 不存在：%s" % order["workspace"])
        self.ledger = ActionLedger(os.path.join(self.run_dir, cfg["ledger"]), cfg["chain_seed"])
        self.state_path = os.path.join(self.run_dir, "state.json")
        self.baseline_dir = os.path.join(self.run_dir, cfg["baseline_dir"])
        self.evidence_root = os.path.join(self.run_dir, "evidence")
        self.op_id = current_op_id()
        self.run_id = current_run_id()
        self.source = source
        self.entry = entry
        self.force_ticket = bool(cfg.get("force_ticket"))
        self.ticket, self.ticket_why = ticket_snapshot(self.lab_root, cfg)
        self.state = self._load_state() or {}
        self._snapshot = None

    # ---------------- 状态与快照 ----------------
    def _load_state(self):
        if not os.path.isfile(self.state_path):
            return None
        with io.open(self.state_path, encoding="utf-8") as f:
            return json.load(f)

    def _save_state(self):
        tmp = self.state_path + ".tmp"
        with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(self.state, ensure_ascii=False, indent=2) + "\n")
        os.replace(tmp, self.state_path)

    def _watch_root(self):
        rel = str(self.cfg.get("watch_scope") or ".").strip()
        if rel in ("", "."):
            return self.workspace
        return scope.target_abs(self.workspace, rel)

    def snapshot(self):
        root = self._watch_root()
        out = {}
        for base, _dirs, files in os.walk(root):
            for name in files:
                p = os.path.join(base, name)
                rel = scope.rel_of(self.workspace, p)
                try:
                    out[rel] = sha_file(p)
                except OSError:
                    out[rel] = "READ_ERROR"
        return out

    @property
    def current(self):
        if self._snapshot is None:
            self._snapshot = self.snapshot()
        return self._snapshot

    def refresh(self):
        self._snapshot = self.snapshot()
        return self._snapshot

    def sync_snapshot(self):
        """观测模式用：把当前快照记为上次检查点；不推进 seq、不写账。"""
        self.state["last_snapshot"] = self.refresh()
        self._save_state()

    def _diff(self, before, after):
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        changed = sorted(k for k in before if k in after and before[k] != after[k])
        return {"added": added, "removed": removed, "changed": changed}

    # ---------------- 启动 ----------------
    def begin(self):
        try:
            # 旧轮快照与超龄证据束先清（只动 run_dir 内自生成物；失败不阻断本轮）
            from . import qingli
            qingli.before_begin(self.run_dir, self.cfg)
        except Exception:
            pass
        os.makedirs(self.baseline_dir, exist_ok=True)
        if not os.listdir(self.baseline_dir):
            shutil.copytree(self.workspace, self.baseline_dir, dirs_exist_ok=True)
        base_manifest = self.snapshot()
        self.state = {
            "schema": "act_state/1",
            "order_id": self.order["order_id"],
            "workspace": self.order["workspace"],
            "op_id": self.op_id,
            "run_id": self.run_id,
            "status": "running",
            "seq": 0,
            "ticket_tid": (self.ticket or {}).get("tid", ""),
            "baseline_manifest": base_manifest,
            "last_snapshot": base_manifest,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "halt": {},
            "halt_history": [],
            "recovered": False,
        }
        self._save_state()
        self._snapshot = base_manifest
        rec = self._record("order_begin", "ok", "", {
            "pre": {"result": "pass", "items": [
                {"id": "S0.1", "name": "order_valid", "result": "pass",
                 "detail": "order_id=%s approved_by=%s" % (self.order["order_id"], self.order["approved_by"])},
                {"id": "S0.7", "name": "ticket_attached", "result": "pass" if self.ticket else "fail",
                 "detail": "tid=%s" % ((self.ticket or {}).get("tid") or self.ticket_why)},
            ]},
        }, target="-", evidence={"files": len(base_manifest)},
           extra={"approved_roots": self.order.get("approved_roots") or [],
                  "approved_files": self.order.get("approved_files") or [],
                  "denied_zones": self.order.get("denied_zones") or [],
                  "authorization": scope.weak_authorization(self.order)})
        self.state["seq"] = rec["seq"]
        self._save_state()
        return rec

    # ---------------- 记录 ----------------
    def _record(self, action_type, result, error_code, checks, target="-", evidence=None,
                extra=None):
        seq = self.ledger.next_seq()
        rec = {
            "at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ts": time.time(),
            "seq": seq,
            "op_id": self.op_id,
            "run_id": self.run_id,
            "entry": self.entry,
            "source": self.source,
            "action_type": action_type,
            "tool": (extra or {}).get("tool", action_type),
            "target": target,
            "intent_id": self.order["order_id"],
            "scope": (extra or {}).get("scope", {}),
            "checks": checks,
            "result": result,
            "error_code": error_code,
            "error_text": ERR.get(error_code, "") if error_code else "",
            "evidence": evidence or {},
            "ticket": self.ticket or {"tid": "", "state": "none", "why": self.ticket_why},
            "pid": os.getpid(),
        }
        if extra:
            for k, v in extra.items():
                if k not in rec:
                    rec[k] = v
        return self.ledger.append(rec)

    # ---------------- S0 动作前 ----------------
    def pre_check(self, action):
        items = []

        def add(i, name, ok, detail):
            items.append({"id": i, "name": name, "result": "pass" if ok else "fail",
                          "detail": detail})

        if self.state.get("status") != "running":
            add("S0.0", "state_running", False, "当前状态=%s" % self.state.get("status"))
            return {"result": "fail", "code": "HALTED", "items": items,
                    "reason": "监管状态不是 running"}
        add("S0.0", "state_running", True, "running")

        exp = False
        try:
            exp = scope.expired(self.order)
            add("S0.1", "order_active", not exp,
                "expires_at=%s" % (scope.expires_at(self.order) or "未设置"))
        except scope.ScopeError as e:
            add("S0.1", "order_active", False, str(e))
            code = getattr(e, "code", "ORDER_EXPIRED") or "ORDER_EXPIRED"
            return {"result": "fail", "code": code, "items": items, "reason": str(e)}

        atype = str(action.get("action_type") or "").strip()
        allowed = atype in (self.order.get("allowed_actions") or [])
        add("S0.2", "action_allowed", allowed,
            "action_type=%s allowed=%s" % (atype, ",".join(self.order.get("allowed_actions") or [])))

        target = str(action.get("target") or "").strip()
        norm = ""
        form_ok = True
        try:
            norm = scope.normalize_rel(target)
            scope.target_abs(self.workspace, norm)
            detail = "target=%s" % norm
        except scope.ScopeError as e:
            form_ok = False
            detail = str(e)
        add("S0.3", "target_form", form_ok, detail)

        decision, reason, matched = ("out_of_scope", "未判定", "")
        if form_ok:
            decision, reason, matched = scope.in_scope(norm, self.order)
        add("S0.4", "target_in_scope", decision == "in_scope", reason)

        # 对照「上次检查点」，不是对照初始基线：批准文件被再次改写时，初始基线必然不同，
        # 拿它比会把正常动作误判成漂移。入口外改动通常已被 P 先拦（错误码 EXTERNAL_DRIFT）；
        # 这里保留 S0.5 作为第二道，防 P 被跳过或状态未刷新的场景。
        drift_ok, drift_detail = True, "目标不在上次快照（新建文件）"
        if form_ok and norm in (self.state.get("last_snapshot") or {}):
            abs_p = scope.target_abs(self.workspace, norm)
            if os.path.isfile(abs_p):
                cur = sha_file(abs_p)
                last = self.state["last_snapshot"][norm]
                drift_ok = cur == last
                drift_detail = "last=%s current=%s" % (last[:16], cur[:16])
            else:
                drift_ok = False
                drift_detail = "上次快照有记录但文件已不存在（被入口外删除）"
        add("S0.5", "baseline_consistent", drift_ok, drift_detail)

        t_ok = bool(self.ticket) or not self.force_ticket
        add("S0.6", "ticket_available", t_ok,
            "tid=%s%s" % ((self.ticket or {}).get("tid", ""),
                          "" if self.ticket else "（%s）" % self.ticket_why))

        code = ""
        if exp:
            code = "ORDER_EXPIRED"
        elif not allowed:
            code = "ACTION_TYPE_NOT_ALLOWED"
        elif not form_ok:
            code = "TARGET_FORM_INVALID"
        elif decision != "in_scope":
            code = "OUT_OF_SCOPE"
        elif not drift_ok:
            code = "BASELINE_DRIFT"
        elif not t_ok:
            code = "TICKET_MISSING"
        fail_reason = ""
        if code:
            fail_reason = [i["detail"] for i in items if i["result"] == "fail"][-1]
        return {"result": "fail" if code else "pass", "code": code, "items": items,
                "reason": fail_reason, "target": norm, "scope": {
                    "decision": decision, "reason": reason, "matched": matched}}

    # ---------------- S1 动作后 ----------------
    def post_check(self, action, before_snapshot, expected):
        items = []
        # 只有本动作声明的主目标算「已声明」。side_effects 是演示用的「工具内部额外
        # 汇出」，恰恰属于未声明变更，不能拿来给自己豁免——否则窗口扫描永远发现不了。
        declared = [scope.normalize_rel(action.get("target"))]
        after = self.refresh()

        add = lambda i, n, ok, d: items.append(
            {"id": i, "name": n, "result": "pass" if ok else "fail", "detail": d})

        target = declared[0]
        abs_p = scope.target_abs(self.workspace, target)
        if expected:
            ok = os.path.isfile(abs_p) and sha_file(abs_p) == expected
            add("S1.1", "target_hash", ok,
                "expected=%s actual=%s" % (expected[:16],
                                           sha_file(abs_p)[:16] if os.path.isfile(abs_p) else "MISSING"))
        else:
            add("S1.1", "target_hash", True, "只读动作，无写入预期")

        decision, reason, _m = scope.in_scope(target, self.order)
        add("S1.2", "scope_reassert", decision == "in_scope", reason)

        diff = self._diff(before_snapshot, after)
        changed = diff["added"] + diff["removed"] + diff["changed"]
        side = [r for r in changed if r not in declared]
        out_of_scope = []
        undeclared = []
        for r in side:
            d, _why, _m = scope.in_scope(r, self.order)
            (undeclared if d == "in_scope" else out_of_scope).append(r)
        ok = not side
        add("S1.3", "no_side_effect", ok,
            "变更=%s 额外汇出=%s" % (changed or "无", side or "无"))

        code = ""
        if expected and not os.path.isfile(abs_p):
            code = "WRITE_MISMATCH"
        elif expected and sha_file(abs_p) != expected:
            code = "WRITE_MISMATCH"
        elif out_of_scope:
            code = "SIDE_EFFECT_DETECTED"
        elif undeclared:
            code = "SIDE_EFFECT_DETECTED"
        return {"result": "fail" if code else "pass", "code": code, "items": items,
                "side_effects": {"out_of_scope": out_of_scope, "undeclared_in_scope": undeclared},
                "diff": diff}

    # ---------------- S1 判红回滚 ----------------
    def _read_target_bytes(self, target):
        """动作前取主目标原始字节；不存在返回 None。用于判红后按字节还原。"""
        if not target or target == "-":
            return None
        abs_p = scope.target_abs(self.workspace, target)
        if not os.path.isfile(abs_p):
            return None
        with open(abs_p, "rb") as f:
            return f.read()

    def _rollback_post_fail(self, target, before, pre_bytes, affected):
        """S1 判红后把本次已落盘变更恢复到动作前状态，返回逐项结果。

        主目标：动作前存在则写回原字节，不存在则删除（删前留副本）。
        额外汇出：新增的移入隔离目录后删除；变更/删除的，仅当基线副本哈希与
        动作前快照一致时从基线还原，否则记 unrecoverable（不猜、不覆盖）。
        """
        stamp = time.strftime("%Y%m%d_%H%M%S")
        qroot = os.path.join(self.evidence_root, "rollback_%s" % stamp)
        rows = []

        def keep_copy(abs_p, rel):
            dst = os.path.join(qroot, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(abs_p, dst)

        def sha_bytes(b):
            return hashlib.sha256(b).hexdigest()

        abs_t = scope.target_abs(self.workspace, target)
        cur_exists = os.path.isfile(abs_t)
        if pre_bytes is None:
            if cur_exists:
                landed = sha_file(abs_t)
                keep_copy(abs_t, target)
                os.remove(abs_t)
                rows.append({"target": target, "action": "remove_added",
                             "landed_sha256": landed, "after_sha256": "",
                             "restored": not os.path.isfile(abs_t)})
            else:
                rows.append({"target": target, "action": "nothing_landed",
                             "landed_sha256": "", "after_sha256": "", "restored": True})
        else:
            want = sha_bytes(pre_bytes)
            cur = sha_file(abs_t) if cur_exists else ""
            if cur != want:
                if cur_exists:
                    keep_copy(abs_t, target)
                with open(abs_t, "wb") as f:
                    f.write(pre_bytes)
                got = sha_file(abs_t)
                rows.append({"target": target, "action": "restore_previous",
                             "landed_sha256": cur, "after_sha256": got,
                             "restored": got == want})
            else:
                rows.append({"target": target, "action": "no_change",
                             "landed_sha256": cur, "after_sha256": cur, "restored": True})

        for rel in affected:
            if not rel or rel == "-" or rel == target:
                continue
            abs_p = scope.target_abs(self.workspace, rel)
            cur = sha_file(abs_p) if os.path.isfile(abs_p) else ""
            prev = (before or {}).get(rel, "")
            if not prev:
                if cur:
                    keep_copy(abs_p, rel)
                    os.remove(abs_p)
                    rows.append({"target": rel, "action": "remove_added",
                                 "landed_sha256": cur, "after_sha256": "",
                                 "restored": not os.path.isfile(abs_p)})
                continue
            if cur == prev:
                continue
            src = os.path.join(self.baseline_dir, rel.replace("/", os.sep))
            if os.path.isfile(src) and sha_file(src) == prev:
                if cur:
                    keep_copy(abs_p, rel)
                self._copy_into(src, abs_p)
                rows.append({"target": rel, "action": "restore_from_baseline",
                             "landed_sha256": cur, "after_sha256": sha_file(abs_p),
                             "restored": sha_file(abs_p) == prev})
            else:
                rows.append({"target": rel, "action": "unrecoverable",
                             "landed_sha256": cur, "after_sha256": cur,
                             "restored": False})
        return rows

    # ---------------- 周期断言 ----------------
    def periodic_check(self):
        """动作前比对：上次快照 vs 当前快照。发现入口外改动即中断下一步。"""
        last = self.state.get("last_snapshot") or {}
        cur = self.refresh()
        diff = self._diff(last, cur)
        changed = diff["added"] + diff["removed"] + diff["changed"]
        return {"result": "fail" if changed else "pass",
                "code": "EXTERNAL_DRIFT" if changed else "",
                "changed": changed, "diff": diff,
                "detail": "周期断言：上次快照后变更=%s" % (changed or "无")}

    # ---------------- 执行 ----------------
    def record(self, action_type, result, error_code, checks, target="-", evidence=None,
               extra=None):
        """公开记账入口：供接入层记录不经 S0/S1 的观测类动作（只读／未覆盖工具）。"""
        return self._record(action_type, result, error_code, checks, target=target,
                            evidence=evidence, extra=extra)

    def run_action(self, action):
        """演示/CLI 用：动作自带 content，走内置执行器。"""
        return self.guard(action)

    def guard(self, action, fn=None):
        """单动作监管闭环：P → S0 → fn(target) → S1 → 记账。

        fn=None 走内置执行器（演示/CLI）。接入 personal 时传真实工具 handler：
        handler 返回 (result, expected_sha256[, error_code])，或抛 ToolError。
        两种执行来源共用同一份 S0/S1 代码，避免「演示一套、接入一套」。
        """
        if self.state.get("status") == "halted":
            rec = self._record("periodic_check", "denied", "HALTED",
                               {"periodic": {"result": "fail", "items": [
                                   {"id": "P.0", "name": "state_running", "result": "fail",
                                    "detail": "status=halted，须先 recover+resume"}]}},
                               target=str(action.get("target") or "-"))
            raise HaltSignal(rec, self.state.get("halt", {}).get("bundle", ""),
                             "监管已中断，拒绝执行")

        p = self.periodic_check()
        if p["result"] == "fail":
            rec = self._record(str(action.get("action_type") or "unknown"), "denied",
                               "EXTERNAL_DRIFT",
                               {"periodic": {"result": "fail", "items": [
                                   {"id": "P.1", "name": "no_external_drift", "result": "fail",
                                    "detail": p["detail"]}]}},
                               target=str(action.get("target") or "-"),
                               evidence={"changed": p["changed"]})
            return self._halt("external_drift", rec, p["changed"], p["detail"])

        pre = self.pre_check(action)
        if pre["result"] == "fail":
            rec = self._record(str(action.get("action_type") or "unknown"), "denied",
                               pre["code"], {"pre": {"result": "fail", "items": pre["items"]}},
                               target=pre.get("target") or str(action.get("target") or "-"),
                               evidence={"reason": pre.get("reason", "")},
                               extra={"scope": pre.get("scope", {})})
            return self._halt("pre_denied", rec, [pre.get("target")], pre.get("reason", ""))

        target = pre["target"]
        before = self.refresh()
        pre_bytes = self._read_target_bytes(target)
        expected = ""
        result, code = "ok", ""
        try:
            if fn is None:
                _verb, expected = self._execute(action, target)   # 执行器回的是动作动词，记账统一 ok
            else:
                out = fn(target)
                if isinstance(out, tuple) and len(out) == 3:
                    result, expected, code = out
                else:
                    result, expected = out
        except ToolError as e:
            result, code = "error", e.code
        except Exception as e:
            # 监管自身异常也按「失败关闭」处理：记录后中断，不当普通异常放过。
            rec = self._record(str(action.get("action_type")), "error", "INTERNAL_ERROR",
                               {"pre": {"result": "pass", "items": pre["items"]}},
                               target=target,
                               evidence={"exception": "%s: %s" % (type(e).__name__, e)})
            return self._halt("internal_error", rec, [target],
                              "监管自身异常，失败关闭：%s: %s" % (type(e).__name__, e))

        post = self.post_check(action, before, expected)
        if post["result"] == "fail":
            affected = post["side_effects"]["out_of_scope"] + post["side_effects"]["undeclared_in_scope"]
            affected = affected or [target]
            rollback = self._rollback_post_fail(target, before, pre_bytes, affected)
            rec = self._record(str(action.get("action_type")), "interrupted", post["code"],
                               {"pre": {"result": "pass", "items": pre["items"]},
                                "post": {"result": "fail", "items": post["items"]}},
                               target=target,
                               evidence={"side_effects": post["side_effects"],
                                         "diff": post["diff"],
                                         "expected_sha256": expected,
                                         "rollback": rollback},
                               extra={"scope": pre.get("scope", {})})
            return self._halt("post_detected", rec, affected, ERR.get(post["code"], ""))

        rec = self._record(str(action.get("action_type")), result, code,
                           {"pre": {"result": "pass", "items": pre["items"]},
                            "post": {"result": "pass", "items": post["items"]}},
                           target=target,
                           evidence={"before_sha256": before.get(target, ""),
                                     "after_sha256": sha_file(scope.target_abs(self.workspace, target))
                                     if os.path.isfile(scope.target_abs(self.workspace, target)) else "",
                                     "expected_sha256": expected,
                                     "diff": post["diff"]},
                           extra={"scope": pre.get("scope", {})})
        self.state["seq"] = rec["seq"]
        self.state["last_snapshot"] = self.current
        self._save_state()
        return rec

    def _execute(self, action, target):
        atype = str(action.get("action_type") or "")
        abs_p = scope.target_abs(self.workspace, target)
        if atype == "file_read":
            if not os.path.isfile(abs_p):
                raise RuntimeError("只读目标不存在：%s" % target)
            return "read", ""
        if atype == "file_write":
            content = str(action.get("content") or "")
            os.makedirs(os.path.dirname(abs_p), exist_ok=True)
            with io.open(abs_p, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            return "written", digest(content)
        if atype in ("cmd_exec", "batch_exec"):
            # 演示执行器：声明目标照写；side_effects 模拟「受控命令内部产生的额外汇出」。
            # 真实落地时这一层接宿主命令执行器，S1 的窗口扫描语义不变。
            content = str(action.get("content") or "")
            os.makedirs(os.path.dirname(abs_p), exist_ok=True)
            with io.open(abs_p, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            for s in action.get("side_effects") or []:
                st = scope.normalize_rel(s.get("target"))
                if st == target:
                    continue
                sp = scope.target_abs(self.workspace, st)
                os.makedirs(os.path.dirname(sp), exist_ok=True)
                with io.open(sp, "w", encoding="utf-8", newline="\n") as f:
                    f.write(str(s.get("content") or ""))
            return "executed", digest(content)
        raise RuntimeError("演示执行器不支持的 action_type=%s" % atype)

    # ---------------- 中断与留证 ----------------
    def _halt(self, trigger, record, affected, reason):
        stamp = time.strftime("%Y%m%d_%H%M%S")
        seq = int(record.get("seq") or 0)
        rel_bundle = "evidence/halt_%03d_%s" % (seq, stamp)
        bundle = os.path.join(self.run_dir, rel_bundle)
        os.makedirs(bundle, exist_ok=True)
        diff_rows = []
        base_manifest = self.state.get("baseline_manifest") or {}
        cur = self.snapshot()
        for r in sorted(set(affected or [])):
            rel = str(r or "-")
            b = base_manifest.get(rel, "")
            c = cur.get(rel, "")
            status = ("unchanged" if b and c and b == c else
                      "added" if not b and c else
                      "removed" if b and not c else "changed")
            diff_rows.append({"target": rel, "baseline_sha256": b, "current_sha256": c,
                              "status": status})
            if b and rel in base_manifest:
                src = os.path.join(self.baseline_dir, rel.replace("/", os.sep))
                if os.path.isfile(src):
                    self._copy_into(src, os.path.join(bundle, "baseline", rel))
            if c:
                src = scope.target_abs(self.workspace, rel) if rel != "-" else ""
                if src and os.path.isfile(src):
                    self._copy_into(src, os.path.join(bundle, "current", rel))
        self.state["status"] = "halted"
        self.state["halt"] = {
            "trigger": trigger, "reason": reason, "seq": seq,
            "bundle": rel_bundle, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "affected": affected, "record": record,
            "recovered": False,
        }
        self.state.setdefault("halt_history", []).append({
            "trigger": trigger, "seq": seq, "reason": reason, "bundle": rel_bundle,
            "at": self.state["halt"]["at"],
        })
        self._save_state()
        self._write_bundle(bundle, record, affected, diff_rows, reason, trigger)
        raise HaltSignal(record, rel_bundle, reason)

    def _copy_into(self, src, dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)

    def _write_bundle(self, bundle, record, affected, diff_rows, reason, trigger):
        payload = {
            "schema": "halt/1",
            "trigger": trigger,
            "reason": reason,
            "at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "state": self.state,
            "record": record,
            "order": self.order,
            "ticket": self.ticket,
            "affected": affected,
            "diff": diff_rows,
        }
        with io.open(os.path.join(bundle, "halt.json"), "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        with io.open(os.path.join(bundle, "diff.txt"), "w", encoding="utf-8", newline="\n") as f:
            for d in diff_rows:
                f.write("%s  %s\n  baseline=%s\n  current =%s\n"
                        % (d["status"], d["target"], d["baseline_sha256"] or "-",
                           d["current_sha256"] or "-"))
        shutil.copyfile(self.ledger.path, os.path.join(bundle, "actions_snapshot.jsonl"))
        if self.ticket:
            with io.open(os.path.join(bundle, "ticket.json"), "w", encoding="utf-8") as f:
                f.write(json.dumps(self.ticket, ensure_ascii=False, indent=2) + "\n")
        rows = []
        for base, _d, files in os.walk(bundle):
            for name in files:
                if name == "manifest.sha256":
                    continue
                p = os.path.join(base, name)
                rel = scope.rel_of(bundle, p)
                rows.append((rel, sha_file(p), os.path.getsize(p)))
        rows.sort()
        with io.open(os.path.join(bundle, "manifest.sha256"), "w", encoding="utf-8", newline="\n") as f:
            for rel, h, size in rows:
                f.write("%s  %d  %s\n" % (h, size, rel))

    # ---------------- 恢复 ----------------
    def recover_restore(self):
        if self.state.get("status") != "halted":
            raise RuntimeError("当前未处于中断状态，无恢复动作")
        cur = self.snapshot()
        base = self.state.get("baseline_manifest") or {}
        diff = self._diff(base, cur)
        changed = diff["added"] + diff["removed"] + diff["changed"]
        restored, quarantined, kept, failed = [], [], [], []
        stamp = time.strftime("%Y%m%d_%H%M%S")
        qroot = os.path.join(self.evidence_root, "quarantine", stamp)
        for rel in changed:
            d, _why, _m = scope.in_scope(rel, self.order)
            if d == "in_scope":
                kept.append(rel)                     # 批准范围内的成果不替用户回退
                continue
            abs_p = scope.target_abs(self.workspace, rel)
            if rel in base:
                src = os.path.join(self.baseline_dir, rel.replace("/", os.sep))
                if os.path.isfile(src):
                    self._copy_into(src, abs_p)
                    if sha_file(abs_p) == base[rel]:
                        restored.append(rel)
                    else:
                        failed.append({"target": rel, "why": "写回后哈希与基线不符"})
                else:
                    # 基线副本不在就不能假装恢复成功：逐件记失败，整轮判 fail。
                    failed.append({"target": rel,
                                   "why": "基线副本缺失（%s）"
                                          % scope.rel_of(self.run_dir, src)})
            elif abs_p and os.path.isfile(abs_p):
                self._copy_into(abs_p, os.path.join(qroot, rel))
                os.remove(abs_p)
                quarantined.append(rel)
        if failed:
            rec = self._record("recovery", "fail", "RESTORE_FAILED",
                               {"post": {"result": "fail", "items": [
                                   {"id": "R.1", "name": "restore_unauthorized", "result": "fail",
                                    "detail": "恢复失败 %d 件：%s"
                                              % (len(failed), ", ".join(f["target"] for f in failed))}]}},
                               target="-",
                               evidence={"changed": changed, "restored": restored,
                                         "quarantined": quarantined, "kept_in_scope": kept,
                                         "failed": failed,
                                         "quarantine_dir": scope.rel_of(self.run_dir, qroot)})
            self.state["seq"] = rec["seq"]
            self._save_state()
            raise RuntimeError("恢复失败：%d 件基线副本缺失，未回滚：%s"
                               % (len(failed), ", ".join(f["target"] for f in failed)))
        rec = self._record("recovery", "ok", "",
                           {"post": {"result": "pass", "items": [
                               {"id": "R.1", "name": "restore_unauthorized", "result": "pass",
                                "detail": "restored=%s quarantined=%s kept_in_scope=%s"
                                          % (restored or "无", quarantined or "无", kept or "无")}]}},
                           target="-",
                           evidence={"restored": restored, "quarantined": quarantined,
                                     "kept_in_scope": kept,
                                     "quarantine_dir": scope.rel_of(self.run_dir, qroot)})
        self.refresh()
        self.state["halt"]["recovered"] = True
        self.state["recovered"] = True
        self.state["last_snapshot"] = self.current
        self.state["seq"] = rec["seq"]
        self._save_state()
        return rec

    def resume(self, approval_path):
        if self.state.get("status") != "halted":
            raise RuntimeError("当前未处于中断状态，无需恢复执行")
        if not os.path.isfile(approval_path):
            raise RuntimeError("批准件不存在：%s" % approval_path)
        with io.open(approval_path, encoding="utf-8") as f:
            ap = json.load(f)
        if ap.get("schema") != "approval/1":
            raise RuntimeError("批准件 schema 须为 approval/1")
        for k in ("approval_id", "approved_by", "approved_at"):
            if not ap.get(k):
                raise RuntimeError("批准件缺字段或为空：%s" % k)
        if not isinstance(ap.get("covers"), list):
            raise RuntimeError("批准件缺字段或类型不对：covers 须为列表（可为空）")
        cur = self.snapshot()
        base = self.state.get("baseline_manifest") or {}
        diff = self._diff(base, cur)
        outside = [r for r in diff["added"] + diff["removed"] + diff["changed"]
                   if scope.in_scope(r, self.order)[0] != "in_scope"]
        covers = ap.get("covers") or []
        if "*" not in covers:
            missing = [r for r in outside if r not in covers]
            if missing:
                raise RuntimeError("批准件未覆盖未授权目标：%s" % ", ".join(missing))
        rec = self._record("resume", "ok", "",
                           {"pre": {"result": "pass", "items": [
                               {"id": "R.2", "name": "human_approval", "result": "pass",
                                "detail": "approval_id=%s approved_by=%s"
                                          % (ap.get("approval_id"), ap.get("approved_by"))}]}},
                           target="-",
                           evidence={"approval": ap, "pending_outside": outside},
                           extra={"approval_id": ap.get("approval_id")})
        self.state["status"] = "running"
        self.state["halt"] = {}
        self.state["seq"] = rec["seq"]
        self.state["last_snapshot"] = self.current
        self._save_state()
        return rec

    def done(self):
        rec = self._record("done", "ok", "",
                           {"post": {"result": "pass", "items": [
                               {"id": "D.1", "name": "sequence_completed", "result": "pass",
                                "detail": "动作序列结束"}]}},
                           target="-")
        self.state["status"] = "done"
        self.state["seq"] = rec["seq"]
        self.state["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save_state()
        return rec

    def status(self):
        return {
            "order_id": self.state.get("order_id"),
            "status": self.state.get("status"),
            "seq": self.state.get("seq"),
            "op_id": self.op_id,
            "run_id": self.run_id,
            "ticket_tid": (self.ticket or {}).get("tid", ""),
            "halt": self.state.get("halt", {}),
            "records": len(self.ledger.records()),
            "chain": self.ledger.verify(),
        }
