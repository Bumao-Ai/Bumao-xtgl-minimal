# -*- coding: utf-8 -*-
"""personal_adapter.py —— personal 端接入适配器（沙盒原型，不落 live）。

挂载位置（live 侧只改一处）：mcp_server.handle_message 里
    text, is_error = HANDLERS[name](args)
改为
    text, is_error = JIANCHA.invoke(name, args, HANDLERS[name])
即在 L4 capability / L3 output_guard 之后、工具真正执行之处。前置闸不动、顺序不动。

四档模式（env BUMO_JIANCHA_MODE，缺省 off）：
  off      完全不记账、不建目录、不 import 监管实现（延迟导入）；行为等同接入前
  shadow   S0/S1/P 全部照算并记账，但任何一条都不拦；记录里标 would_deny/would_interrupt
  enforce  S0 失败即拒（动作不执行）并中断；S1 失败即中断后续；P 失败拦下一步
  blocked  A/B 闸门结论缺失/过期/未过——拒写，不做任何放行判断

映射口径（v0.2 只覆盖「写前就声明单目标」的工具）：
  file_write                      → file_write，target=args.path，全量 S0/S1
  其余工具（render_run/ledger_add/beifen_run/preflight/check_run/plan_run/show_clause/
  zhishiku_search/action_review）→ 只记账、covered=false：目标在 handler 内派生或多目标，
                                    S0 无法在动作前判定，不能假装已覆盖
  未登记工具                       → enforce 拒（UNMAPPED_TOOL）；shadow 执行并标 covered=false
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)

MODE_ENV = "BUMO_JIANCHA_MODE"
MODES = ("off", "shadow", "enforce")

# 写前声明单目标的工具：可全量挂 S0/S1
GATED = {"file_write": "file_write"}

# 只记账、不计覆盖：目标在 handler 内派生，或多目标
OBSERVED = {
    "beifen_run": ("file_write", "目录级多目标，handler 内派生"),
    "render_run": ("file_write", "多目标：全部条款 .txt 视图"),
    "ledger_add": ("file_write", "目标在 handler 内派生"),
    "preflight": ("file_read", "只读预检"),
    "check_run": ("file_read", "只读闸门"),
    "plan_run": ("file_read", "只读影响清单"),
    "show_clause": ("file_read", "只读单条"),
    "zhishiku_search": ("file_read", "只读检索"),
    "action_review": ("file_read", "审查闸口，不落盘"),
}


def _load_gate(path):
    if not path or not os.path.isfile(path):
        return None
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def _gate_fresh(gate):
    from . import gate_check
    if not gate:
        return False, "闸门结论缺失"
    if gate.get("verdict") != "PASS":
        return False, "闸门结论未过：verdict=%s" % gate.get("verdict")
    return gate_check.freshness(gate)


class PersonalAdapter:
    def __init__(self, lab_root, cfg, run_dir, order, gate_path=None, mode=None,
                 entry="entry:mcp"):
        self.lab_root = os.path.abspath(lab_root)
        self.cfg = cfg
        self.run_dir = os.path.abspath(run_dir) if run_dir else ""
        self.order = order
        self.gate_path = gate_path
        raw = (mode if mode is not None else os.environ.get(MODE_ENV) or "off").strip().lower()
        self.requested = raw if raw in MODES else "off"
        self.entry = entry
        self.sup = None
        self.gate_why = ""
        self.init_error = ""
        if self.requested != "off":
            # 延迟导入：off 时连监管模块都不加载
            if not order:
                self.init_error = "意图单未就位（order 为空）"
                return
            try:
                from .supervisor import Supervisor
                self.sup = Supervisor(self.lab_root, cfg, self.run_dir, order,
                                      source="personal", entry=entry)
            except Exception as e:      # 意图单/工作区/账本未就绪 → 不裸奔，按 blocked
                self.init_error = "%s: %s" % (type(e).__name__, e)

    # ---------------- 开关 ----------------
    def gate_state(self):
        gate = _load_gate(self.gate_path)
        ok, why = _gate_fresh(gate)
        self.gate_why = why
        return gate, ok, why

    def effective_mode(self):
        if self.requested == "off":
            return "off"
        if self.init_error or self.sup is None:
            self.gate_why = "监管未就绪：%s" % (self.init_error or "supervisor 未初始化")
            return "blocked"
        _gate, ok, why = self.gate_state()
        if not ok:
            return "blocked"
        return self.requested

    def begin(self):
        if self.requested == "off":
            return None
        if self.sup is None:
            return None
        return self.sup.begin()

    def status(self):
        if self.sup is None:
            return {"mode": "off", "records": 0}
        st = self.sup.status()
        st["mode"] = self.effective_mode()
        st["gate"] = self.gate_why
        return st

    # ---------------- 映射 ----------------
    def map_tool(self, tool, args):
        if tool in GATED:
            return {"tool": tool, "action_type": GATED[tool],
                    "target": str((args or {}).get("path") or "").strip(),
                    "content": str((args or {}).get("content") or ""),
                    "gated": True}
        if tool in OBSERVED:
            atype, why = OBSERVED[tool]
            return {"tool": tool, "action_type": atype, "target": "-",
                    "gated": False, "reason": why}
        return None

    # ---------------- 入口 ----------------
    def invoke(self, tool, args, handler):
        """与 mcp_server 的 (text, is_error) 契约一致。"""
        mode = self.effective_mode()
        if mode == "off":
            return handler(args)

        if mode == "blocked":
            if self.sup is None:
                return ("[执行中监管·闸门未过] 拒绝：%s｜未记账（监管未就绪）｜%s"
                        % (self.gate_why, tool), True)
            rec = self.sup.record("file_write" if tool in GATED else "file_read",
                                  "denied", "GATE_NOT_PASSED",
                                  {"pre": {"result": "fail", "items": [
                                      {"id": "G.1", "name": "ab_gate_ref", "result": "fail",
                                       "detail": self.gate_why}]}},
                                  target=str((args or {}).get("path") or "-"),
                                  extra={"tool": tool, "mode": "blocked", "covered": False})
            return ("[执行中监管·闸门未过] 拒绝：%s｜记录 seq=%s｜%s"
                    % (self.gate_why, rec["seq"], tool), True)

        m = self.map_tool(tool, args)
        if m is None:
            return self._unmapped(tool, args, handler, mode)
        if not m["gated"]:
            return self._observed(m, args, handler, mode)
        return self._gated(m, args, handler, mode)

    def _unmapped(self, tool, args, handler, mode):
        if mode == "enforce":
            rec = self.sup.record("file_write", "denied", "UNMAPPED_TOOL",
                                  {"pre": {"result": "fail", "items": [
                                      {"id": "S0.8", "name": "tool_mapped", "result": "fail",
                                       "detail": "工具未登记动作映射：%s" % tool}]}},
                                  target="-",
                                  extra={"tool": tool, "mode": mode, "covered": False})
            return ("[执行中监管·默认拒绝] 未登记动作映射：%s｜记录 seq=%s" % (tool, rec["seq"]), True)
        text, err = handler(args)
        self.sup.sync_snapshot()
        rec = self.sup.record("file_write", "error" if err else "ok", "TOOL_ERROR" if err else "",
                              {"pre": {"result": "skip", "items": [
                                  {"id": "S0.8", "name": "tool_mapped", "result": "skip",
                                   "detail": "未登记映射；shadow 只观测"}]}},
                              target="-",
                              extra={"tool": tool, "mode": "shadow", "covered": False,
                                     "why": "未登记动作映射"})
        return text, err

    def _observed(self, m, args, handler, mode):
        text, err = handler(args)
        self.sup.sync_snapshot()
        rec = self.sup.record(m["action_type"], "error" if err else "ok",
                              "TOOL_ERROR" if err else "",
                              {"pre": {"result": "skip", "items": [
                                  {"id": "S0.8", "name": "covered_scope", "result": "skip",
                                   "detail": m["reason"]}]}},
                              target="-",
                              extra={"tool": m["tool"], "mode": mode, "covered": False,
                                     "why": m["reason"]})
        return text, err

    def _gated(self, m, args, handler, mode):
        from .ledger import digest
        action = {"action_type": m["action_type"], "target": m["target"],
                  "content": m["content"]}
        out = {}

        def run(_target):
            text, err = handler(args)
            out["text"], out["err"] = text, err
            if err:
                from .supervisor import ToolError
                raise ToolError("TOOL_ERROR", text)
            return ("ok", digest(m["content"]))

        if mode == "shadow":
            pre = self.sup.pre_check(action)
            before = self.sup.refresh()
            text, err = handler(args)
            if m["target"]:
                post = self.sup.post_check(action, before, "" if err else digest(m["content"]))
            else:
                post = {"result": "fail", "code": "TARGET_FORM_INVALID", "diff":
                        {"added": [], "removed": [], "changed": []},
                        "items": [{"id": "S1.1", "name": "target_form", "result": "fail",
                                   "detail": "target 为空，未进 S1 扫描"}]}
            self.sup.sync_snapshot()
            would = []
            if pre["result"] == "fail":
                would.append(pre["code"])
            if post["result"] == "fail":
                would.append("S1:" + post["code"])
            rec = self.sup.record(m["action_type"], "error" if err else "ok",
                                  "TOOL_ERROR" if err else "",
                                  {"pre": {"result": pre["result"], "items": pre["items"]},
                                   "post": {"result": post["result"], "items": post["items"]}},
                                  target=m["target"] or "-",
                                  evidence={"would_deny": would, "diff": post["diff"]},
                                  extra={"tool": m["tool"], "mode": "shadow", "covered": True,
                                         "would_deny": would})
            return text, err

        from .supervisor import HaltSignal, ToolError  # noqa: F401（ToolError 供 run 内抛出）
        try:
            self.sup.guard(action, run)
        except HaltSignal as h:
            return ("[执行中监管·已中断] %s｜记录 seq=%s｜证据：%s"
                    % (h.reason, h.record.get("seq"), h.bundle), True)
        return out.get("text", ""), out.get("err", False)
