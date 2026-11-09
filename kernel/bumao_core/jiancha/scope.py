# -*- coding: utf-8 -*-
"""scope.py —— 意图单解析与目标集合判定（同步检查点 S0 的判据源）。

意图单（intent/1）是一份「批准的目标集合」，不是自然语言说明：
  approved_roots  允许写出的目录（相对 workspace）
  approved_files  允许写出的具体文件（相对 workspace）
  denied_zones    无论是否在 approved 根内，一律拒绝的目录段
  allowed_actions 允许的动作类型
  expires_at      过期时刻（空串＝本单不过期，但必须由人持有）
  approved_by     批准人；空串＝未批准单，直接拒
  ticket_tid      该单绑定的绿票 tid（可为空，force_ticket=true 时不允许空）

判定只有三种结果：in_scope / out_of_scope / malformed。没有「大概在范围内」。
"""
import io
import json
import ntpath
import os
import posixpath
import re
import time

from . import reasons


class ScopeError(ValueError):
    """意图单无效或目标路径形态非法。code 取自 schema/reason_codes.json，可直接进票面。"""

    def __init__(self, message, code="TARGET_FORM_INVALID"):
        self.code = code
        super().__init__(message)


RE_DRIVE = re.compile(r"^[A-Za-z]:")
RE_TID = re.compile(r"^[0-9a-f]{16}$")
RE_QUOTE = re.compile(r"「[^」]{2,}」|“[^”]{2,}”|\"[^\"]{2,}\"|'[^']{2,}'")
ACTION_TYPES = ("file_read", "file_write", "cmd_exec", "batch_exec")
PROXY_MARK = "代理代签"
MAX_INTENT_SPAN = 24 * 3600          # live 单据有效期上限 24 小时，逾时不得自动续签


def is_live(order=None, live=None):
    """live 判定（fail-closed）：显式参数优先；环境未设/空/未知值一律按 live。

    只有显式写了 BUMO_JIANCHA_ENV=sandbox 才放宽；忘了配环境变量不会让
    「live 必填 + 24 小时上限」失效。demo_only=true 的单条意图在 live 下也允许空 expires_at。
    """
    if live is not None:
        return bool(live)
    return (os.environ.get("BUMO_JIANCHA_ENV") or "").strip().lower() != "sandbox"


def is_proxy_sign(order):
    return PROXY_MARK in str((order or {}).get("note") or "")


def weak_authorization(order):
    """弱授权识别：代理代签＝弱授权，不得计入「独立审批」。"""
    proxy = is_proxy_sign(order)
    return {
        "mode": "proxy_weak" if proxy else "independent",
        "weak_authorization": proxy,
        "counts_as_independent_approval": not proxy,
        "approved_by": str((order or {}).get("approved_by") or ""),
        "note": str((order or {}).get("note") or ""),
    }


def export_intent(order):
    """导出用摘要：弱授权一眼可见，避免被统计进独立审批。"""
    return {
        "schema": "intent_export/1",
        "order_id": str((order or {}).get("order_id") or ""),
        "approved_by": str((order or {}).get("approved_by") or ""),
        "approved_at": str((order or {}).get("approved_at") or ""),
        "expires_at": str((order or {}).get("expires_at") or ""),
        "authorization": weak_authorization(order),
    }


def load_order(path, live=None):
    if not os.path.isfile(path):
        raise ScopeError("意图单不存在：%s" % path, "NO_ORDER")
    try:
        with io.open(path, encoding="utf-8") as f:
            order = json.load(f)
    except (ValueError, OSError) as e:
        raise ScopeError("意图单无法解析：%s" % e, "ORDER_UNPARSABLE")
    validate_order(order, live=live)
    return order


def order_problems(order, now=None, live=None):
    """逐项列出意图单的问题（不抛）。每条含 code/field/detail，code 可直接进票面。"""
    live = is_live(order, live)
    probs = []

    def add(code, field, detail):
        reasons.assert_known(code)
        probs.append({"code": code, "field": field, "detail": detail})

    if not isinstance(order, dict):
        add("ORDER_NOT_OBJECT", "$", "意图单不是对象")
        return probs
    if order.get("schema") != "intent/1":
        add("INVALID_SCHEMA", "schema", "意图单 schema 须为 intent/1，收到 %r" % order.get("schema"))
    for k in ("order_id", "workspace", "approved_at"):
        if not str(order.get(k) or "").strip():
            add("ORDER_FIELD_MISSING", k, "意图单缺字段或为空：%s" % k)
    if not str(order.get("approved_by") or "").strip():
        add("NO_APPROVER", "approved_by", "未批准单：approved_by 为空，拒绝执行")
    note = str(order.get("note") or "")
    if is_proxy_sign(order) and not RE_QUOTE.search(note):
        add("PROXY_QUOTE_MISSING", "note",
            "代理代签必须在 note 含「%s」并附用户原话（引号内至少 2 字）" % PROXY_MARK)
    roots = order.get("approved_roots") or []
    files = order.get("approved_files") or []
    if not isinstance(roots, list) or not isinstance(files, list):
        add("INVALID_APPROVED_PATH", "approved_roots/approved_files", "批准集合须为列表")
    elif not roots and not files:
        add("EMPTY_APPROVAL_SET", "approved_roots+approved_files",
            "批准的目标集合为空：既不批目录也不批文件，等于没批")
    for rel in (roots if isinstance(roots, list) else []) + (files if isinstance(files, list) else []):
        try:
            normalize_rel(rel)                      # 形态不合格在装载期就炸
        except ScopeError as e:
            add("INVALID_APPROVED_PATH", "approved_roots/approved_files", "%s（%r）" % (e, rel))
    zones = order.get("denied_zones")
    if zones is not None:
        if not isinstance(zones, list):
            add("DENIED_ZONES_INVALID", "denied_zones",
                "denied_zones 须为列表，收到 %r" % type(zones).__name__)
        else:
            for z in zones:
                try:
                    normalize_rel(z)                # 拒绝区写不成形态即配置错误，装载期就拒
                except ScopeError as e:
                    add("DENIED_ZONES_INVALID", "denied_zones",
                        "拒绝区配置无效：%s（%r）" % (e, z))
    ws = str(order.get("workspace") or "").strip()
    if ws:
        try:
            normalize_rel(ws)
        except ScopeError as e:
            add("INVALID_WORKSPACE", "workspace", str(e))
    acts = order.get("allowed_actions")
    if not isinstance(acts, list) or not acts:
        add("NO_ALLOWED_ACTIONS", "allowed_actions", "allowed_actions 为空：未声明可用动作类型")
    else:
        for a in acts:
            if a not in ACTION_TYPES:
                add("INVALID_ACTION_TYPE", "allowed_actions", "未知动作类型：%r" % a)
    e = str(order.get("expires_at") or "").strip()
    if not e:
        if live and not bool(order.get("demo_only")):
            add("LIVE_EXPIRES_REQUIRED", "expires_at",
                "live 单据必须写 expires_at（空值只允许沙盒/demo_only）")
    else:
        t1 = None
        try:
            t1 = time.mktime(time.strptime(e, "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            add("INVALID_EXPIRES_AT", "expires_at",
                "expires_at 格式须为 YYYY-MM-DD HH:MM:SS：%s" % e)
        if t1 is not None:
            pa = str(order.get("approved_at") or "").strip()
            try:
                t0 = time.mktime(time.strptime(pa, "%Y-%m-%d %H:%M:%S"))
                span = t1 - t0
                if span > MAX_INTENT_SPAN:
                    add("INVALID_EXPIRES_AT", "expires_at",
                        "有效期 %.1f 小时，超过上限 24 小时；逾时须重新签发，不得自动续签" % (span / 3600.0))
                elif span <= 0:
                    add("INVALID_EXPIRES_AT", "expires_at", "expires_at 须晚于 approved_at")
            except ValueError:
                pass
    tid = str(order.get("ticket_tid") or "").strip()
    if tid and not RE_TID.match(tid):
        add("INVALID_TICKET_TID", "ticket_tid", "ticket_tid 须为 16 位小写十六进制：%s" % tid)
    return probs


def validate_order(order, now=None, live=None):
    probs = order_problems(order, now=now, live=live)
    if probs:
        p = probs[0]
        raise ScopeError(p["detail"], p["code"])
    return True



def normalize_rel(rel):
    """相对路径归一化。绝对路径、盘符、.. 段、NUL 一律判形态非法（不留解析歧义）。"""
    s = str(rel or "").strip().replace("\\", "/")
    if not s:
        raise ScopeError("目标路径为空")
    if "\0" in s:
        raise ScopeError("目标路径含 NUL")
    if RE_DRIVE.match(s) or s.startswith("/") or s.startswith("//"):
        raise ScopeError("目标路径不得为绝对路径或带盘符：%s" % rel)
    raw_parts = s.split("/")
    if any(p == ".." for p in raw_parts):
        raise ScopeError("目标路径不得含 .. 段：%s" % rel)
    s = posixpath.normpath(s)
    if s in ("", ".") or s.startswith("../"):
        raise ScopeError("目标路径归一化后越出根：%s" % rel)
    return s


def under(rel, root):
    """rel 是否在 root 之下（按路径段比较，防 approved 与 approved_evil 前缀混淆）。"""
    r = normalize_rel(rel)
    b = normalize_rel(root)
    return r == b or r.startswith(b + "/")


def denied(rel, zones):
    """命中拒绝区返回区名，否则空串。拒绝区配置本身无效即抛——不得静默跳过（fail-closed）。"""
    r = normalize_rel(rel)
    if zones is None:
        return ""
    if not isinstance(zones, list):
        raise ScopeError("拒绝区配置无效：denied_zones 须为列表，收到 %r" % type(zones).__name__,
                         "DENIED_ZONES_INVALID")
    for z in zones:
        try:
            z = normalize_rel(z)
        except ScopeError as e:
            raise ScopeError("拒绝区配置无效：%s（%r）" % (e, z), "DENIED_ZONES_INVALID")
        if under(r, z):
            return z
    return ""


def in_scope(rel, order):
    """返回 (decision, reason, matched)。decision: in_scope / out_of_scope。

    拒绝区配置无效时按 out_of_scope 处理（一律不放行），并在 reason 里写明配置错误。
    """
    try:
        r = normalize_rel(rel)
    except ScopeError as e:
        return "out_of_scope", str(e), ""
    try:
        z = denied(r, order.get("denied_zones") or [])
    except ScopeError as e:
        return "out_of_scope", str(e), ""
    if z:
        return "out_of_scope", "命中拒绝区 denied_zones=%s" % z, ""
    for root in order.get("approved_roots") or []:
        if under(r, root):
            return "in_scope", "落在批准目录 %s" % root, root
    for f in order.get("approved_files") or []:
        if r == normalize_rel(f):
            return "in_scope", "命中批准文件 %s" % f, f
    return "out_of_scope", "不在批准目录/文件集合内", ""


def expires_at(order):
    return str(order.get("expires_at") or "").strip()


def expired(order, now=None):
    e = expires_at(order)
    if not e:
        return False
    now = now or time.time()
    try:
        ts = time.mktime(time.strptime(e, "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        raise ScopeError("expires_at 格式须为 YYYY-MM-DD HH:MM:SS：%s" % e, "INVALID_EXPIRES_AT")
    return now > ts


def workspace_abs(lab_root, order):
    """意图单里的 workspace 相对本目录解析；解析后必须仍在本目录之下。"""
    rel = normalize_rel(order["workspace"])
    base = os.path.abspath(lab_root)
    full = os.path.abspath(os.path.join(base, rel))
    try:
        inside = os.path.commonpath([base, full]) == base
    except ValueError:
        inside = False
    if not inside:
        raise ScopeError("workspace 越出沙盒根：%s" % order["workspace"], "WORKSPACE_OUTSIDE_ROOT")
    return full


def _true_path(full):
    """把绝对路径解析成真实路径（逐级 realpath）。

    目标不存在时按最近的已存在父目录的真实路径判定；父目录不是目录、链接悬空、
    任何一级解析不出真实路径，一律返回 None——调用方据此拒绝（fail-closed）。
    """
    tail = []
    cur = full
    while True:
        if os.path.lexists(cur):
            if os.path.islink(cur) and not os.path.exists(cur):
                return None                       # 悬空链接：无真实目标，判不了
            real = os.path.realpath(cur)
            if not os.path.exists(real):
                return None                       # realpath 后仍不存在，判不了
            break
        parent = os.path.dirname(cur)
        if not parent or parent == cur:
            return None
        tail.append(os.path.basename(cur))
        cur = parent
    if tail and not os.path.isdir(real):
        return None                               # 父级是文件，无法在其下判定
    for part in reversed(tail):
        real = os.path.join(real, part)
    return real


def target_abs(workspace, rel):
    """目标绝对路径。形态合法后按真实路径（realpath）校验，链接不得跨出 workspace。

    判不出真实路径（悬空链接、权限、跨盘）即拒；这是「拒绝写」而不是「放行」。
    """
    r = normalize_rel(rel)
    base = os.path.realpath(os.path.abspath(workspace))
    if not os.path.isdir(base):
        raise ScopeError("workspace 无法解析成真实目录：%s" % workspace, "TARGET_UNRESOLVABLE")
    full = os.path.abspath(os.path.join(base, r.replace("/", os.sep)))
    real = _true_path(full)
    if real is None:
        raise ScopeError("目标路径真实位置无法判定，拒绝执行：%s" % rel, "TARGET_UNRESOLVABLE")
    nb = os.path.normcase(base)
    nr = os.path.normcase(os.path.abspath(real))
    try:
        inside = os.path.commonpath([nb, nr]) == nb
    except ValueError:
        inside = False
    if not inside:
        raise ScopeError("目标路径实际解析越出 workspace：%s" % rel, "TARGET_OUTSIDE_WORKSPACE")
    return full


def rel_of(workspace, abs_path):
    return ntpath.normpath(os.path.relpath(abs_path, workspace)).replace("\\", "/")
