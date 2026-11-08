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

"""模块清单校验（模块化单体的第一道约束，不是插件运行时）。

用途：
    python module_check.py          校验 modules.json 并打印清单
    python module_check.py --json   机器可读输出

规则：
- id 唯一；必填字段齐全；
- kind 只能是 builtin / local / experimental；
- status 只能是 active / planned / disabled；
- 模块声明 core 版本范围，必须与当前内核兼容；
- 模块不得声称修改内核（没有这个字段，也不允许加）。

退出码：0 通过；1 有问题。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "modules.json"
REQUIRED = ("id", "name", "version", "core", "kind", "status")
VALID_KIND = {"builtin", "local", "experimental"}
VALID_STATUS = {"active", "planned", "disabled"}
VALID_PERMISSION = {"read", "confirm"}   # execute 禁止进前端入口（交接单 §2.3）
VALID_GROUP = {"read", "write"}
CAP_FIELDS = ("group", "source", "permission", "credential", "evidence", "review_by")
SWITCHES = HERE / "web_config.json"
LIB_DIR = HERE.parent.parent / "00_meta" / "rules_library"   # 宿主层，与生效规则目录分开
PRESET_SLOTS = ("backup", "audit", "credential", "rollback", "logging")
PACK_REQUIRED = ("id", "name", "name_en", "applies_to", "depends_on",
                   "enabled", "rules")
VALID_ENDS = {"personal", "community", "minimal"}
LIB_DIR = HERE.parent.parent / "00_meta" / "rules_library"   # 宿主层，与生效规则目录分开
PRESET_SLOTS = ("backup", "audit", "credential", "rollback", "logging")
PACK_REQUIRED = ("id", "name", "name_en", "applies_to", "depends_on",
                   "enabled", "rules")
VALID_ENDS = {"personal", "community", "minimal"}


def core_version() -> str:
    from xtgl_core import CORE_VERSION
    return CORE_VERSION


def compatible(spec: str, version: str) -> bool:
    """极简范围：'^2.0' 表示同主版本；'2.0' 表示前缀匹配。"""
    spec = str(spec or "").strip()
    if not spec:
        return False
    if spec.startswith("^"):
        return version.split(".")[0] == spec[1:].split(".")[0]
    return version == spec or version.startswith(spec + ".")


def validate(path: Path = MANIFEST):
    errors, modules = [], []
    if not path.is_file():
        return ["缺 modules.json"], []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        return ["modules.json 解析失败：%s" % e], []
    if not isinstance(data, dict):
        return ["modules.json 根节点必须是对象"], []
    ver = core_version()
    if data.get("core") and not compatible(data["core"], ver):
        errors.append("清单要求内核 %s，当前 %s" % (data["core"], ver))
    mods = data.get("modules")
    if not isinstance(mods, list) or not mods:
        return errors + ["modules 必须是非空数组"], []
    seen = set()
    for i, m in enumerate(mods):
        if not isinstance(m, dict):
            errors.append("第 %d 个模块不是对象" % (i + 1))
            continue
        for k in REQUIRED:
            if not str(m.get(k) or "").strip():
                errors.append("第 %d 个模块缺字段 %s" % (i + 1, k))
        mid = str(m.get("id") or "")
        if mid in seen:
            errors.append("模块 id 重复：%s" % mid)
        seen.add(mid)
        if m.get("kind") not in VALID_KIND:
            errors.append("模块 %s 的 kind 非法：%s" % (mid, m.get("kind")))
        if m.get("status") not in VALID_STATUS:
            errors.append("模块 %s 的 status 非法：%s" % (mid, m.get("status")))
        if m.get("core") and not compatible(m["core"], ver):
            errors.append("模块 %s 要求内核 %s，当前 %s" % (mid, m["core"], ver))
        if m.get("write") is True:
            errors.append("模块 %s 不得声明写内核权限" % mid)
        perm = str(m.get("permission") or "")
        if perm == "execute":
            errors.append("能力 %s 的 permission=execute 禁止进前端入口（删除类动作只走命令行）" % mid)
        elif perm and perm not in VALID_PERMISSION:
            errors.append("能力 %s 的 permission 非法：%s（只许 read / confirm）" % (mid, perm))
        if m.get("group") and m["group"] not in VALID_GROUP:
            errors.append("能力 %s 的 group 非法：%s" % (mid, m.get("group")))
        have = [k for k in CAP_FIELDS if k in m]
        if have:
            lack = [k for k in CAP_FIELDS if k not in m]
            if lack:
                errors.append("能力 %s 的能力字段不齐，缺：%s" % (mid, ",".join(lack)))
        if perm == "confirm" and not str(m.get("credential") or "").strip():
            errors.append("能力 %s 是 confirm 级，必须写明凭据口径（rc=0＋结论行＋时间戳＋60 秒窗口）" % mid)
        if str(m.get("source") or "").startswith("snapshot.") \
                and not str(m.get("evidence") or "").strip():
            errors.append("能力 %s 无实物锚点，不许启用" % mid)
        if "name_en" in m and not str(m["name_en"]).strip():
            errors.append("能力 %s 的 name_en 为空——前端中英两版的键必须成对" % mid)
        modules.append(m)
    return errors, modules


def switch_report():
    """开关表与定义表交叉核对。开关有、定义无＝「未挂载能力」，只算提示不算错——
    交接单 §2.5 第 9 步反向用例 A 的口径：不白屏、不抛异常、不猜成「全部已接入」。"""
    unmounted, no_switch = [], []
    try:
        sw = json.loads(SWITCHES.read_text(encoding="utf-8-sig")).get("capabilities")
    except Exception:
        return unmounted, no_switch
    ids = set(str(m.get("id")) for m in validate()[1])
    if isinstance(sw, list):
        unmounted = [str(x) for x in sw if str(x) not in ids]
        no_switch = sorted(ids - set(str(x) for x in sw)) if sw else []
    return unmounted, no_switch


def _pack_errors(doc, caps, fname, check_name=True):
    """按 rules_library/schema.json 校一个包；只校形状，不解释任何规则语义。"""
    errs = []
    if not isinstance(doc, dict):
        return ["%s 根节点必须是对象" % fname]
    for f in PACK_REQUIRED:
        if f not in doc:
            errs.append("%s 缺必填字段 %s" % (fname, f))
    if not str(doc.get("name_en") or u"").strip():
        errs.append("%s name_en 为空——中英两版必须成对" % fname)
    if check_name and str(doc.get("id") or u"") != fname.replace(".json", u""):
        errs.append("%s 的 id 必须与文件名一致" % fname)
    ap = doc.get("applies_to")
    if not isinstance(ap, list) or not ap or [x for x in ap if x not in VALID_ENDS]:
        errs.append("%s applies_to 必须是端名数组（personal／community／minimal）" % fname)
    dep = doc.get("depends_on")
    if not isinstance(dep, list):
        errs.append("%s depends_on 必须是数组" % fname)
    elif caps is not None:
        for x in dep:
            if x not in caps:
                errs.append("%s 依赖了定义表里没有的能力 %s" % (fname, x))
    if not isinstance(doc.get("enabled"), bool):
        errs.append("%s enabled 必须是布尔（默认 false，不许缺）" % fname)
    rl = doc.get("rules")
    if not isinstance(rl, list):
        errs.append("%s rules 必须是数组（预置槽位一律为空数组）" % fname)
    else:
        for r in rl:
            if not isinstance(r, dict) or not str(r.get("id") or u"").strip() \
                    or not str(r.get("action") or u"").strip():
                errs.append("%s 有一条规则缺 id 或 action" % fname)
            elif not isinstance(r.get("params", {}), dict):
                errs.append("%s 规则 %s 的 params 必须是对象（数值由用户自填）" % (fname, r.get("id")))
    return errs


def rules_library_scan():
    """返回 (errors, info)。整库不存在＝只提示不报错（空库三端启动不许崩）。"""
    info = {"mounted": False, "note": u"未建库（不影响启动）", "slots": [],
            "preset_missing": [], "counted": [], "examples": 0}
    if not LIB_DIR.is_dir():
        return [], info
    errs = []
    caps = set(str(m.get("id")) for m in validate()[1])
    schema_p = LIB_DIR / "schema.json"
    if not schema_p.is_file():
        errs.append("rules_library 缺 schema.json")
    else:
        try:
            json.loads(schema_p.read_text(encoding="utf-8-sig"))
        except Exception as e:  # noqa: BLE001
            errs.append("rules_library/schema.json 解析失败：%s" % str(e)[:60])
    packs_dir = LIB_DIR / "packs"
    seen = set()
    if not packs_dir.is_dir():
        errs.append("rules_library 缺 packs/ 目录")
    else:
        for p in sorted(packs_dir.glob("*.json")):
            try:
                doc = json.loads(p.read_text(encoding="utf-8-sig"))
            except Exception as e:  # noqa: BLE001
                errs.append("包 %s 不是合法 JSON：%s" % (p.name, str(e)[:60]))
                continue
            seen.add(str(doc.get("id")))
            errs += _pack_errors(doc, caps, p.name)
            if doc.get("enabled") is True and isinstance(doc.get("rules"), list) and doc["rules"]:
                info["counted"].append(p.name)
            info["slots"].append({"id": p.name, "enabled": bool(doc.get("enabled")),
                                  "rules": len(doc.get("rules") or [])})
        info["preset_missing"] = [s for s in PRESET_SLOTS if s not in seen]
        if info["preset_missing"]:
            errs.append("五类预置槽位缺：%s" % u"、".join(info["preset_missing"]))
    ex_dir = LIB_DIR / "examples"
    if ex_dir.is_dir():
        for p in sorted(ex_dir.glob("*.json")):
            try:
                doc = json.loads(p.read_text(encoding="utf-8-sig"))
            except Exception as e:  # noqa: BLE001
                errs.append("模板 %s 不是合法 JSON：%s" % (p.name, str(e)[:60]))
                continue
            errs += _pack_errors(doc, None, p.name, check_name=False)
            info["examples"] += 1
    info["mounted"] = True
    info["note"] = u"已建库"
    return errs, info


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    errors, modules = validate()
    lib_err, lib_info = rules_library_scan()
    errors = errors + lib_err
    if "--json" in argv:
        um, ns = switch_report()
        print(json.dumps({"ok": not errors, "core": core_version(),
                          "modules": modules, "errors": errors,
                          "rules_library": lib_info,
                          "warnings": ([u"未挂载能力：" + x for x in um]
                                         + [u"本端未打开：" + x for x in ns]),
                          "unmounted": um},
                         ensure_ascii=False, indent=2))
        return 0 if not errors else 1
    print("内核 %s ｜ 模块清单 %s" % (core_version(), MANIFEST.name))
    for m in modules:
        print("  %-11s v%-7s %-6s %-10s %s" % (
            m.get("id"), m.get("version"), m.get("kind"), m.get("status"),
            m.get("desc", "")))
    unmounted, no_switch = switch_report()
    if errors:
        print("FAIL：")
        for e in errors:
            print("  - " + e)
        return 1
    print("PASS：%d 个模块，清单与内核兼容" % len(modules))
    print(u"规则库：%s｜槽位 %d 个（缺 %d）｜生效 %d 包｜模板 %d 个（未启用的不采数、不进快照）" % (
        lib_info.get("note"), len(lib_info.get("slots") or []),
        len(lib_info.get("preset_missing") or []), len(lib_info.get("counted") or []),
        lib_info.get("examples"))) if lib_info else None
    if unmounted:
        print(u"提示：开关表里有 %d 项在定义表里不存在 → 界面显示「未挂载能力」：%s"
              % (len(unmounted), ", ".join(unmounted)))
    if no_switch:
        print(u"提示：定义表里有 %d 项本端未打开（不采数、不显示）" % len(no_switch))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
