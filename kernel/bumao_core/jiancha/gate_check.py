# -*- coding: utf-8 -*-
"""gate_check.py —— A/B 闸门只读镜像（沙盒）。

不调用 contract_test.py --selftest（那条路径会重写 core_manifest.json）。这里只读：
  A 契约载入：kernel_contract.json 可解析、meta.status=frozen、版本与日期形态合规
  B 核心文件在位：personal 端 core_manifest.json 里列的文件逐个存在
另附「指纹」：本次检查时关键文件的 sha256。接入层用它判断闸门结论是否过期——
闸门过了但文件随后被改，指纹即对不上，监管按未通过处理（失败关闭）。

用法：python gate_check.py [--out <path>] [--root <GCML 根>]
"""
import hashlib
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)
# 落 live 后由包位置向上推根（jiancha→10_rac→personal→HX→GCML），不写死盘符。
DEFAULT_ROOT = os.environ.get("BUMO_GCML_ROOT") or os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(HERE))))

CONTRACT = "HX/kernel/kernel_contract.json"
WEB_MANIFEST = "HX/personal/20_view/web/core_manifest.json"
WEB_DIR = "HX/personal/20_view/web"
FINGERPRINT_FILES = [
    "HX/personal/10_rac/mcp_server.py",
    "HX/personal/10_rac/capability.py",
    "HX/personal/10_rac/output_guard.py",
    "HX/personal/10_rac/pretool_guard/core.py",
    WEB_MANIFEST,
    CONTRACT,
]
RE_VER = re.compile(r"^\d+\.\d+(\.\d+)?$")
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def sha_file(p):
    h = hashlib.sha256()
    with io.open(p, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def group_a(root):
    items = []

    def add(i, name, ok, detail):
        items.append({"id": i, "name": name, "result": "pass" if ok else "fail", "detail": detail})

    p = os.path.join(root, CONTRACT)
    if not os.path.isfile(p):
        add("A.1", "contract_exists", False, "契约文件不存在：%s" % CONTRACT)
        return items
    add("A.1", "contract_exists", True, CONTRACT)
    try:
        with io.open(p, encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError) as e:
        add("A.2", "contract_parsable", False, "契约无法解析：%s" % e)
        return items
    add("A.2", "contract_parsable", True, "json ok")
    meta = data.get("meta") or {}
    add("A.3", "contract_frozen", meta.get("status") == "frozen", "meta.status=%r" % meta.get("status"))
    cv = str(meta.get("contract_version") or "")
    add("A.4", "contract_version", bool(RE_VER.match(cv)), "meta.contract_version=%r" % cv)
    for k in ("frozen_at", "updated_at"):
        v = str(meta.get(k) or "")
        add("A.5", "meta_%s" % k, bool(RE_DATE.match(v)), "meta.%s=%r" % (k, v))
    return items


def group_b(root):
    items = []

    def add(i, name, ok, detail):
        items.append({"id": i, "name": name, "result": "pass" if ok else "fail", "detail": detail})

    p = os.path.join(root, WEB_MANIFEST)
    if not os.path.isfile(p):
        add("B.1", "manifest_exists", False, "core_manifest.json 缺失：%s" % WEB_MANIFEST)
        return items
    add("B.1", "manifest_exists", True, WEB_MANIFEST)
    try:
        with io.open(p, encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError) as e:
        add("B.2", "manifest_parsable", False, "core_manifest.json 不可解析：%s" % e)
        return items
    files = data.get("files") or {}
    missing = [n for n in files if not os.path.isfile(os.path.join(root, WEB_DIR, n))]
    add("B.2", "core_files_present", not missing,
        "核心文件 %d 个在位%s" % (len(files), "；缺：%s" % "、".join(missing) if missing else ""))
    return items


def run(root=None):
    root = root or os.environ.get("BUMO_GCML_ROOT") or DEFAULT_ROOT
    a = group_a(root)
    b = group_b(root)
    files_sha = {}
    for rel in FINGERPRINT_FILES:
        p = os.path.join(root, rel)
        files_sha[rel] = sha_file(p) if os.path.isfile(p) else ""
    a_ok = all(i["result"] == "pass" for i in a)
    b_ok = all(i["result"] == "pass" for i in b)
    return {
        "schema": "gate_ref/1",
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "root": root,
        "a": {"result": "pass" if a_ok else "fail", "items": a},
        "b": {"result": "pass" if b_ok else "fail", "items": b},
        "verdict": "PASS" if (a_ok and b_ok) else "FAIL",
        "files_sha": files_sha,
    }


def load(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def freshness(gate, root=None):
    """闸门结论是否对当前文件仍然有效。返回 (fresh, 说明)。"""
    root = root or gate.get("root") or DEFAULT_ROOT
    stale = []
    for rel, want in (gate.get("files_sha") or {}).items():
        p = os.path.join(root, rel)
        got = sha_file(p) if os.path.isfile(p) else ""
        if want != got:
            stale.append(rel)
    if stale:
        return False, "闸门后文件已变：%s" % "、".join(stale)
    return True, "指纹一致"


def main(argv):
    out = os.path.join(HERE, "_out", "gate_ref.json")
    root = None
    if "--out" in argv:
        out = os.path.abspath(argv[argv.index("--out") + 1])
    if "--root" in argv:
        root = argv[argv.index("--root") + 1]
    g = run(root)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(g, ensure_ascii=False, indent=2) + "\n")
    for grp in ("a", "b"):
        for i in g[grp]["items"]:
            print("[%s] %s %s｜%s" % ("PASS" if i["result"] == "pass" else "FAIL",
                                     i["id"], i["name"], i["detail"]))
    print("[闸门] A=%s B=%s → %s" % (g["a"]["result"], g["b"]["result"], g["verdict"]))
    print("[写出] %s" % out)
    return 0 if g["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
