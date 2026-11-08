# -*- coding: utf-8 -*-
# Copyright 2026 Bumao
#
# Licensed under the Apache License, Version 2.0.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""Bumao XTGL · Gate Registry（闸门注册表 · 辅助校验层）

============================================================================
本文件的实际状态与它「本该是什么」不一致，请先读完这一段再用它。
============================================================================

【本该是什么】unified_kernel_plan_261104_v1.txt §四「gate_registry.py 闸门动态注册」
  规定本文件应提供 class GateRegistry：
      register(section, gid, label, check_fn, clause_ref=None, heavy=False)
      run_all(db, strict=True)
  闸门不再硬编码在 engine.py，而是从规则包 metadata.gates 声明装载。
  该计划 L193 的复选框「- [ ] 写 gate_registry.py（动态闸门注册表）」仍未勾选。
  → GateRegistry 类【尚未落地】。本文件目前只提供注册完整性的辅助校验函数。

【现在生效的防缩水机制在哪】不在本文件，在 engine.py：
      _registered_gate_ids  每次 register() 都记录 gid
      set_expected(...)     wrapper 在全部 register() 之后声明期望集
      verify_registration() cmd_check 里核对，缺闸即 FAIL
  破坏性验证已实测通过（补充篇 §五 第2条）：注释掉某端 17 个 register()
  中的 1 个 → rc=1、"Expected: 17 gates, Registered: 16"、"MISSING (1): B7"；
  恢复后 sha256 与基线一致、重跑 ALL PASS。

【2026-11-04 的改动】
  删除了原先硬编码在本文件的三个 EXPECTED_<端名大写> frozenset 常量。
  理由：内核不该知道端身份
  （QUXIE_FENXI_261104.md L39「内核不应该写死 XTGL 的业务规则」、L5「内核不许
  知道业务」）；且期望集若同时存在于本文件与各端 wrapper 的 set_expected()，
  就是补充篇 §2.12 批判的二套账——今日三处恰好一致属巧合，任一处漂移即让
  防缩水保证失效。**期望集的唯一来源是各端 wrapper 的 set_expected()。**
  同时修掉三处早已失效的实现（详见各函数 docstring 的「原缺陷」）。

【端无关性】本文件不含任何端名字面量，也不含任何闸门 ID 字面量。
  自查用补充篇 附录A A4 的口径：对 kernel/bumao_core/*.py 统计三个端名
  （即 HX 下三个端目录的同名小写词）出现次数，本文件应为 0。
  注意：写这条自查说明时不要在注释里把三个端名拼出来，否则自查本身就命中
  ——本轮初稿正是这样错的，已改。

生效：2026-11-04 ｜ 适用：三端 wrapper（端无关）
"""

import ast
import os
import re
import sys

# ── 运行时注册表 ────────────────────────────────────────────────────────
# gid -> {"gid":..., "label":..., "file":...}
# 由 _patch_engine_register() 自动填充，或由 wrapper 显式调 register_gate()。
_REGISTRY = {}

# register() 的接收者名。统一内核写法是 core.register(...)，历史写法有
# engine.register(...) 与 bumao_core_engine.register(...)；裸 register(...) 也算。
_RECEIVER_NAMES = frozenset({"core", "engine", "core_engine", "bumao_core_engine"})

# 出闸写法的三种历史口径（补充篇 §2.9）：
#   register("B1", fn, "标签")      统一内核写法
#   ok("B1 标签")                   旧引擎写法
#   o.add("B1", ...) / add("B1",…)  旧引擎写法
_ID = r"[A-Z]\d+[a-z]?"
_SRC_ID_PATTERNS = (
    re.compile(r'\bregister\(\s*["\'](%s)["\']' % _ID),
    re.compile(r'\bok\(\s*["\'](%s)[\s"\']' % _ID),
    re.compile(r'\badd\(\s*["\'](%s)["\']' % _ID),
)


def _patch_engine_register():
    """挂到统一内核的 register() 上，把每次注册的 gid 记进 _REGISTRY。

    原缺陷：import 的是 bumao_core_engine —— 该模块 2026-11-04 已改名为
    engine.py，ImportError 被 except 吞掉，补丁自改名起从未生效过一次。
    现改为 import engine，并保留 ImportError 容错（本模块可在内核之前被导入）。
    """
    try:
        import engine as _fce
    except ImportError:
        return False
    if getattr(_fce, "_gate_registry_patched", False):
        return True
    _fce._original_register = _fce.register

    def patched(gid, fn, label="", section="B"):
        _REGISTRY[gid] = {
            "gid": gid,
            "label": str(label)[:80],
            "file": getattr(fn, "__module__", type(fn).__name__),
        }
        return _fce._original_register(gid, fn, label, section)

    _fce.register = patched
    _fce._gate_registry_patched = True
    return True


_patched = _patch_engine_register()


def register_gate(gid, label=""):
    """显式登记一个闸门（供无法依赖补丁的调用方使用）。"""
    _REGISTRY[gid] = {"gid": gid, "label": str(label)[:80]}


def get_registered_ids():
    return sorted(_REGISTRY.keys())


def get_registered_count():
    return len(_REGISTRY)


def is_patched():
    """补丁是否挂上了统一内核的 register()。False 表示 _REGISTRY 只能靠显式登记。"""
    return bool(_patched)


class RegistryMismatch(Exception):
    """期望闸门缺失（或多出）时抛出。"""


def require_all_registered(expected, name="unknown", max_extra=0):
    """防静默缩水核对：expected 里每个 gid 都必须已注册。

    参数 expected 必须由调用方（各端 wrapper）传入 —— 本文件不再内置任何
    端的期望集，见模块 docstring「2026-11-04 的改动」。

    原缺陷：max_extra 默认 3，即允许多出 3 个未声明闸门而不报错。闸门「多出」
    虽不等于缩水，但会让声明集与实际集长期漂移而无人察觉，故默认收紧为 0。

    返回 True；不符则抛 RegistryMismatch。
    """
    expected = frozenset(expected)
    registered = frozenset(_REGISTRY.keys())
    missing = sorted(expected - registered)
    extra = sorted(registered - expected)

    errors = []
    if missing:
        tail = " (+%d more)" % (len(missing) - 10) if len(missing) > 10 else ""
        errors.append("MISSING (%d): %s%s" % (len(missing), ", ".join(missing[:10]), tail))
    if extra and len(extra) > max_extra:
        errors.append("EXTRA (%d): %s" % (len(extra), ", ".join(extra[:5])))

    if errors:
        raise RegistryMismatch(
            "[gate_registry] %s: REGISTER FAILED\n"
            "  Expected: %d gates\n"
            "  Registered: %d gates\n"
            % (name, len(expected), len(registered))
            + "\n".join("  " + e for e in errors)
            + "\n  依据 补充篇 §五 第2条：注释掉任意一行 register()，"
              "check --strict 必须立刻 FAIL"
        )
    return True


def extract_gate_ids_from_source(src):
    """从源码文本提取闸门 ID，兼容三种历史出闸写法（补充篇 §2.9）。

    原缺陷（verify_against_engine_py）：正则只写 r'"(B[0-9]{1,2}[a-z]?) "'，
    ① 只认 B 闸，用 G 编号的那一端（G01–G17）一个都提取不到；② 只认旧
    ok("Bnn …") 写法，统一内核的 register("B1", …) 一个都提取不到 —— 对三端
    一律返回空集，于是「空集 ⊆ 注册表」恒成立，校验形同虚设。
    """
    ids = set()
    for pat in _SRC_ID_PATTERNS:
        ids.update(pat.findall(src))
    return ids


def verify_against_source(src_path, name="unknown", encoding="utf-8-sig"):
    """交叉核对：源码里声明的闸门 ID 与运行时注册表是否一致。

    返回 (match, missing_from_registry, extra_in_registry)。不一致只写 stderr，
    不抛异常——它是诊断工具，判定权在 require_all_registered。
    """
    with open(src_path, encoding=encoding) as f:
        src_ids = extract_gate_ids_from_source(f.read())
    registered = set(_REGISTRY.keys())
    missing = sorted(src_ids - registered)
    extra = sorted(registered - src_ids)
    match = (not missing and not extra)
    if not match:
        sys.stderr.write(
            "[gate_registry source_check] %s: 源码 %d 个 ID / 注册表 %d 个\n"
            % (name, len(src_ids), len(registered)))
        if missing:
            sys.stderr.write("  源码有而注册表无: %s\n" % missing)
        if extra:
            sys.stderr.write("  注册表有而源码无: %s\n" % extra)
    return match, missing, extra


def count_registers_from_file(wrapper_path, encoding="utf-8-sig"):
    """AST 口径数 register() 调用（不用 grep：grep 会把注释与 docstring 里的
    示例也算进去，这正是「手数」不可靠的原因）。

    原缺陷：只接受 func.value.id == 'engine'，而统一内核写法是 core.register(...)，
    故对三端 wrapper 一律返回 0 —— 一个恒为 0 的计数器比没有计数器更危险，
    因为它看起来像「已核对过」。现接受 _RECEIVER_NAMES 中任一接收者名，
    并额外统计裸 register(...) 调用。

    返回 (count, ids, nonliteral)：nonliteral 是首参非字符串字面量、
    因而无法静态取到 ID 的调用数；非 0 时计数不可全信，调用方应报警。
    """
    with open(wrapper_path, encoding=encoding) as f:
        tree = ast.parse(f.read())

    ids, nonliteral = [], 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            if func.attr != "register":
                continue
            recv = func.value
            if not (isinstance(recv, ast.Name) and recv.id in _RECEIVER_NAMES):
                continue
        elif isinstance(func, ast.Name):
            if func.id != "register":
                continue
        else:
            continue

        if node.args and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str):
            ids.append(node.args[0].value)
        else:
            nonliteral += 1

    return len(ids), sorted(set(ids)), nonliteral


# ── 版本变更授权闸（L2＋L3） ───────────────────────────────────────────
# 立闸原因（2026-11-07）：版本曾被无授权漂到 2.2.1；C2 只比「代码串＝契约串」，
# 同一轮同时改代码与契约声明时两串仍相等，C2 必绿 —— 该缺口由此闸堵住：
# 判据不取自被改的两件，而取自独立的审批册（当日行＋用户授权原话＋最新授权版本）。
# 端无关：本文件不写端名，审批册按「层目录」形态向上搜索。
_APPROVAL_WORDS = ("授权", "批准", "同意", "裁定", "令")
_ENTRY_RE = re.compile(r"【第\s*(\d+)\s*号】\s*(\d{4}-\d{2}-\d{2})")
_APPROVED_RE = re.compile(r"用户批准原文\s*[:：]\s*「([^」]*)」", re.S)
_VERSION_RE = re.compile(r"(?<![\d.])\d+\.\d+(?:\.\d+)?(?![\d.])")


def parse_approval_entries(text):
    """把审批册拆成条目：编号／日期／用户批准原文／整段原文。

    block 是【第 N 号】之后的整段，供「按文件名点名」类判据使用
    （2026-11-07 新增：核心件审批不只看批准原话，还要看该条目是否点名了
    被改的文件；点名写在哪个字段都算，但必须同属这一条，不能跨条目拼证据）。
    """
    marks = list(_ENTRY_RE.finditer(text or ""))
    entries = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        block = text[m.end():end]
        approved = _APPROVED_RE.search(block)
        entries.append({
            "no": int(m.group(1)),
            "date": m.group(2),
            "approved": (approved.group(1).strip() if approved else ""),
            "block": block.strip(),
        })
    return entries


def approval_covers_file(ledger_text, date, filename, words=None):
    """某日审批册里是否有条目「点名了 filename」且含授权词。

    返回命中条目列表（空＝未授权）。判据刻意要求文件名与授权词同属一条：
    防止一条泛授权 + 另一条文件清单被拼成证据。filename 只比对 basename，
    避免审批册因端内相对路径写法不同而漏判。
    """
    words = tuple(words or _APPROVAL_WORDS)
    name = os.path.basename(str(filename or ""))
    if not name:
        return []
    hits = []
    for e in parse_approval_entries(ledger_text):
        if str(date or "") and e["date"] != str(date):
            continue
        if name not in e["block"]:
            continue
        # 授权词只在「用户批准原文」引号内判：整段 block 里永远有「批准原文」这个
        # 字段名，拿 block 判等于任何条目都自带授权词（Q001 实测踩到的假阳性）。
        if not any(w in e["approved"] for w in words):
            continue
        hits.append(e)
    return hits


def version_approval(declared_version, changed_on, ledger_text, ledger_path=""):
    """L2＋L3 判定。declared_version＝契约 current_value；changed_on＝契约 updated_at。

    L2：当日（changed_on）审批行里，必须有含该版本号且带授权词的「用户批准原文」。
    L3：该版本号必须等于审批册里最新一条授权版本 —— 代码与契约同轮双改时，
        两件自洽但审批册没记，故在此被拦（堵 C2 只比字符串的缺口）。
    """
    declared = str(declared_version or "").strip()
    changed_on = str(changed_on or "").strip()
    text = ledger_text or ""
    res = {"ledger_ok": bool(text.strip()), "ledger_path": ledger_path,
           "entries": 0, "latest_authorized": "", "l2_ok": False, "l3_ok": False,
           "l2_detail": "", "l3_detail": ""}

    if not res["ledger_ok"]:
        res["l2_detail"] = "找不到审批册（%s），版本变更无凭据" % (ledger_path or "未指定")
        res["l3_detail"] = "找不到审批册，无法确认授权版本"
        return res

    entries = parse_approval_entries(text)
    res["entries"] = len(entries)
    if not entries:
        res["l2_detail"] = "审批册里没有可解析的【第 N 号】条目"
        res["l3_detail"] = "审批册无可解析条目，无法确认授权版本"
        return res

    # L2：当日授权行
    same_day = [e for e in entries if e["date"] == changed_on]
    hit = [e for e in same_day
           if declared in e["approved"] and any(w in e["approved"] for w in _APPROVAL_WORDS)]
    res["l2_ok"] = bool(hit)
    if hit:
        res["l2_detail"] = "当日（%s）第 %d 号审批行含授权原话且写明 %s" % (
            changed_on, hit[0]["no"], declared)
    elif not same_day:
        res["l2_detail"] = "无当日（%s）审批行（当日行 %d 条）" % (changed_on, len(same_day))
    else:
        res["l2_detail"] = "当日 %d 条审批行，均无含 %s 且带授权词的批准原文" % (
            len(same_day), declared)

    # L3：最新授权版本（按编号取最后一条带版本号的授权原文）
    auth_vers = []
    for e in entries:
        if not any(w in e["approved"] for w in _APPROVAL_WORDS):
            continue
        vers = _VERSION_RE.findall(e["approved"])
        for v in vers:
            auth_vers.append((e["no"], v))
    latest = max(auth_vers)[1] if auth_vers else ""
    res["latest_authorized"] = latest
    res["l3_ok"] = bool(latest) and declared == latest
    if not latest:
        res["l3_detail"] = "审批册里没有带授权原话的版本号，%s 无法自证" % declared
    elif declared == latest:
        res["l3_detail"] = "声明版本 %s 与审批册最新授权版本 %s 一致" % (declared, latest)
    else:
        res["l3_detail"] = ("声明版本 %s 与审批册最新授权版本 %s 不一致 —— "
                            "代码与契约同轮双改不能自证（C2 缺口）" % (declared, latest))
    return res


def find_approval_ledger(start_dir):
    """向上找审批册：环境变量 XTGL_SHENPI 优先；否则按「层目录/30_taizhang」形态搜索。

    端无关：不写任何端名，只认 30_taizhang 这个台账层目录名。
    """
    env = os.environ.get("XTGL_SHENPI")
    if env and os.path.isfile(env):
        return env
    cur = os.path.abspath(start_dir or ".")
    for _ in range(5):
        direct = os.path.join(cur, "30_taizhang", "shenpi_jilu.txt")
        if os.path.isfile(direct):
            return direct
        try:
            subs = sorted(os.listdir(cur))
        except OSError:
            subs = []
        for name in subs:
            if not os.path.isdir(os.path.join(cur, name)):
                continue
            p = os.path.join(cur, name, "30_taizhang", "shenpi_jilu.txt")
            if os.path.isfile(p):
                return p
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return ""


def version_approval_check(declared_version, changed_on, start_dir):
    """读审批册并判定；返回 (ok, detail, result)。"""
    path = find_approval_ledger(start_dir)
    text = ""
    if path:
        try:
            with open(path, encoding="utf-8-sig") as f:
                text = f.read()
        except OSError as e:
            return False, "审批册读取失败：%s" % e, {}
    r = version_approval(declared_version, changed_on, text, ledger_path=path)
    ok = bool(r["l2_ok"] and r["l3_ok"])
    detail = "L2 %s ｜ L3 %s" % (r["l2_detail"], r["l3_detail"])
    return ok, detail, r
