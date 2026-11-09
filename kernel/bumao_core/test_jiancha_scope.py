# -*- coding: utf-8 -*-
"""scope 判据测试：符号链接逃逸、路径穿越、拒绝区非法配置、过期/非法授权单。"""

import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bumao_core.jiancha import scope

RESULTS = []


def check(label, ok, detail=""):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + label + (("  :: %s" % detail) if detail else ""))


def make_link(link, target):
    try:
        os.symlink(target, link, target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError):
        rc = subprocess.call('mklink /J "%s" "%s"' % (link, target), shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "junction" if rc == 0 else ""


def valid_order(**kw):
    o = {
        "schema": "intent/1",
        "order_id": "t-scope",
        "workspace": "ws",
        "approved_at": "2026-11-09 10:00:00",
        "approved_by": "user",
        "approved_roots": ["ok"],
        "approved_files": [],
        "denied_zones": ["secret"],
        "allowed_actions": ["file_write"],
        "expires_at": "",
        "demo_only": True,
    }
    o.update(kw)
    return o


def code_of(fn):
    try:
        fn()
        return ""
    except scope.ScopeError as e:
        return e.code


def main():
    os.environ["BUMO_JIANCHA_ENV"] = "sandbox"
    root = tempfile.mkdtemp(prefix="t_scope_")
    ws = os.path.join(root, "ws")
    outside = os.path.join(root, "outside")
    os.makedirs(ws)
    os.makedirs(outside)

    # 1. 符号链接／目录联结指向区外：必须拒
    kind = make_link(os.path.join(ws, "escape"), outside)
    if kind:
        c = code_of(lambda: scope.target_abs(ws, "escape/pwn.txt"))
        check("区外链接被拒（%s）" % kind, c == "TARGET_OUTSIDE_WORKSPACE", "code=%s" % c)
    else:
        check("区外链接被拒（环境不支持建链，跳过）", True, "SKIP")

    # 2. 区内正常路径仍可用
    p = scope.target_abs(ws, "ok/new.txt")
    check("区内路径放行", os.path.normcase(p).startswith(os.path.normcase(ws) + os.sep), p)

    # 3. 区内链接指向区内：放行
    sub = os.path.join(ws, "sub")
    os.makedirs(sub)
    kind2 = make_link(os.path.join(ws, "inside_link"), sub)
    if kind2:
        p2 = scope.target_abs(ws, "inside_link/f.txt")
        check("区内链接放行（%s）" % kind2,
              os.path.normcase(os.path.dirname(p2)).startswith(os.path.normcase(ws)))

    # 4. 悬空链接：判不了即拒
    dangling = os.path.join(ws, "dangling")
    try:
        os.symlink(os.path.join(root, "not_exist"), dangling)
        c = code_of(lambda: scope.target_abs(ws, "dangling/x.txt"))
        check("悬空链接被拒", c == "TARGET_UNRESOLVABLE", "code=%s" % c)
    except (OSError, NotImplementedError):
        check("悬空链接被拒（环境不支持建链，跳过）", True, "SKIP")

    # 5. 路径穿越形态
    for bad in ("../x", "ok/../../y", "/abs", "C:/z", "ok\\..\\..\\w", ""):
        c = code_of(lambda b=bad: scope.normalize_rel(b))
        check("形态拒 %r" % bad, c == "TARGET_FORM_INVALID", "code=%s" % c)

    # 6. 拒绝区非法配置：装载期即判配置错误
    c = code_of(lambda: scope.validate_order(valid_order(denied_zones=["../outside"])))
    check("拒绝区含 .. 判配置错误", c == "DENIED_ZONES_INVALID", "code=%s" % c)
    c = code_of(lambda: scope.validate_order(valid_order(denied_zones="secret")))
    check("拒绝区非列表判配置错误", c == "DENIED_ZONES_INVALID", "code=%s" % c)
    probs = scope.order_problems(valid_order(denied_zones=["/abs"]))
    check("order_problems 登记 DENIED_ZONES_INVALID",
          any(p["code"] == "DENIED_ZONES_INVALID" for p in probs), "%r" % probs)
    d, why, _m = scope.in_scope("ok/a.txt", valid_order(denied_zones=[".."]))
    check("运行期非法拒绝区一律不放行", d == "out_of_scope", why)
    check("合法拒绝区仍命中", scope.denied("secret/a.txt", ["secret"]) == "secret")

    # 7. 过期与非法授权单
    check("过期单判过期", scope.expired({"expires_at": "2020-01-01 00:00:00"}) is True)
    check("未过期单不判过期", scope.expired({"expires_at": "2099-01-01 00:00:00"}) is False)
    c = code_of(lambda: scope.expired({"expires_at": "2026/11/09"}))
    check("expires_at 形态非法", c == "INVALID_EXPIRES_AT", "code=%s" % c)
    c = code_of(lambda: scope.validate_order(valid_order(schema="intent/2")))
    check("schema 非法被拒", c == "INVALID_SCHEMA", "code=%s" % c)
    c = code_of(lambda: scope.validate_order(valid_order(approved_by="")))
    check("未批准单被拒", c == "NO_APPROVER", "code=%s" % c)
    c = code_of(lambda: scope.validate_order(
        valid_order(expires_at="2026-11-10 23:00:00")))
    check("有效期超 24 小时被拒", c == "INVALID_EXPIRES_AT", "code=%s" % c)
    check("合法单通过", scope.validate_order(valid_order()) is True)

    print("ALL PASS" if all(RESULTS) else "HAS FAIL")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
