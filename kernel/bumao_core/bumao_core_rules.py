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

"""rules_db 参考装载器 —— **参考实现，不参与运行时**

支持三种历史规则格式的解析演示：
1. zhunze/z*.json（个人版旧格式）
2. ZH/*.json（社区版旧格式）
3. rules/r*.json（极简版旧格式 + 未来标准格式）
4. z00..z13.json（新版本——按章节文件名）

【状态 · 2026-11-09 定为「参考实现，不参与运行时」】
一、内核 engine.py 对本模块零引用；三端 wrapper 也零引用。
二、本模块**不满足** HOST_CONTRACT.md §三 的宿主 12 成员契约：
    本模块提供 load_db / duplicate_ids / find_root / index / block_broken /
    shell_clauses / missing_keys / root_mismatches / broken_refs / load_meta / load_json；
    契约要的是 load / dup_ids / block_broken / shell_clauses / load_meta /
    ROOT / HERE / render_all。
    缺 load()、dup_ids()、render_all() 与模块级 ROOT，故**不得**直接传给 configure()。
三、它只用于说明历史规则目录如何被解析。真实接入请自备满足 12 成员的 rules_db，
    可直接复制运行的最小样例见仓库根目录 examples/minimal_host.py。
四、本文件不参与任何三端运行时；改动它不会改变任何一端的 check 结论。
"""

import io
import json
import os
import re
import sys


HERE = os.path.dirname(os.path.abspath(__file__))


def _find_gcml(p):
    """向上找工作区根：锚点是「这一层有 00_meta 子目录」"""
    q = p
    while q:
        if os.path.isdir(os.path.join(q, "00_meta")):
            return q
        n = os.path.dirname(q)
        if n == q:
            break
        q = n
    return os.path.dirname(p)


def find_root(start_path=None):
    """查找项目根——直接检查起始路径及其直接父目录"""
    import os as _os
    import re as _re
    
    base = start_path or HERE
    candidates = [base]  # 先查自身
    p = _os.path.dirname(_os.path.abspath(base))
    while p and p != _os.path.dirname(p):  # until filesystem root
        candidates.append(p)
        p = _os.path.dirname(p)
    
    formats = [
        ("zhunze", r"^z\d+\.json$"),
        ("ZH", r"^.*\.json$"),
        ("rules", r"^r\d+.*\.json$"),
    ]
    
    for q in candidates:
        for dir_name, pat in formats:
            rp = _os.path.join(q, dir_name)
            if _os.path.isdir(rp):
                files = [f for f in _os.listdir(rp) 
                        if f.endswith(".json") and _re.match(pat, f)]
                if files:
                    meta_path = _os.path.join(q, "meta.json")
                    meta = {}
                    if _os.path.exists(meta_path):
                        try:
                            with open(meta_path, "r", encoding="utf-8") as f:
                                meta = json.load(f)
                        except Exception:
                            pass
                    return {
                        "root": q,
                        "rules_dir": dir_name,
                        "format": dir_name,
                        "files": sorted(files),
                        "meta": meta,
                        "META_PATH": meta_path,
                    }
    
    raise RuntimeError("无法在路径树 %s 及其父目录中找到任何规则目录(zhunze/ZH/rules)" % base)


def load_meta(root_info=None):
    """加载元数据"""
    info = root_info or find_root()
    mp = info.get("META_PATH")
    if not mp or not os.path.exists(mp):
        return {"name": "", "version": "0.0"}
    with open(mp, "r", encoding="utf-8") as f:
        return json.load(f)


def load_json(path):
    """安全加载 JSON 文件"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_clauses(root_info=None):
    """从规则目录加载所有章节文件 -> clauses 列表"""
    info = root_info or find_root()
    rules_dir = info["rules_dir"]
    root = info["root"]
    chapter_files = info["files"]
    
    all_chapters = []
    all_clauses = []
    chapter_idx = 0
    
    for cf in chapter_files:
        fp = os.path.join(root, rules_dir, cf)
        try:
            data = load_json(fp)
            ch = data.get("ch", chapter_idx)
            title = data.get("chapter_title", "")
            chapters_list = data.get("chapters", [])
            
            # Collect clause entries - support both single-object and array formats
            raw_clauses = data.get("clauses", [])
            if isinstance(raw_clauses, dict):
                raw_clauses = [raw_clauses]
            
            for cls_entry in raw_clauses:
                cid = cls_entry.get("id", "")
                root_val = cls_entry.get("root", "")
                body = cls_entry.get("body", [])
                if isinstance(body, str):
                    body = [body]
                
                all_clauses.append({
                    "id": cid,
                    "root": root_val,
                    "body": body,
                })
            
            all_chapters.append({
                "ch": ch,
                "chapter_title": title,
                "file": cf,
                "n": len(raw_clauses),
            })
            chapter_idx += 1
            
        except Exception as e:
            print("[WARN] 跳过规则文件 %s: %s" % (cf, e))
    
    return all_chapters, all_clauses, info


def load_db(root_info=None):
    """加载完整数据库 -> 统一内部结构"""
    chapters, clauses, info = load_clauses(root_info)
    meta = info.get("meta", {})
    return {
        "meta": meta,
        "chapters": chapters,
        "clauses": clauses,
        "info": info,
    }


def index(db):
    """构建索引：为 clauses 添加计算字段（broken_refs, broken_blocks, nbody, shell_clauses）"""
    clauses = db["clauses"]
    
    for c in clauses:
        # 计算正文行数
        c["nbody"] = len(c.get("body", []))
        
        # 断链检测
        refs = []
        for b in c.get("body", []):
            # 找条款引用 id (like 1.2, 9.9(9)(9.2))
            for m in re.finditer(r"(\d+\.\d+(?:\([^\)]*\))*)", b):
                ref_id = m.group(1)
                if ref_id != c["id"]:
                    refs.append(ref_id)
        c["ref_ids"] = refs
        
        # broken_refs: 引用了不存在的条款 ID
        referenced_ids = set(cl["id"] for cl in clauses) | set(cl.get("root", "") for cl in clauses)
        broken = []
        for rid in refs:
            if rid not in referenced_ids:
                broken.append(rid)
        c["broken_refs"] = broken
    
    return db


def duplicate_ids(clauses):
    """检测重复条款 ID"""
    seen = {}
    dups = []
    for c in clauses:
        cid = c.get("id", "")
        if cid in seen:
            dups.append(cid)
        else:
            seen[cid] = True
    return dups


def block_broken(clauses):
    """检测块断裂——同一 root 内的条必须连续"""
    broken = []
    prev_root = None
    main_seen = False
    for c in clauses:
        root = c.get("root", "")
        nbody = c.get("nbody", 0)
        
        if prev_root is not None and root != prev_root:
            # Root change
            if main_seen and nbody > 0:
                # 主条之后又出现有正文的条目 = 断裂
                pass
            main_seen = False
        
        prev_root = root
        if nbody > 0:
            main_seen = True
    
    return broken  # 简化实现：基础版本暂为空


def shell_clauses(clauses):
    """检测空壳条款（无正文但有标题/ID）"""
    shells = []
    for c in clauses:
        if c.get("nbody", 0) == 0:
            shells.append(c["id"])
    return shells


def missing_keys(clauses):
    """检测缺失关键字段的条款"""
    missing = []
    for c in clauses:
        if "id" not in c:
            missing.append("%s: no id" % repr(c.get("title", "unknown")))
        if "root" not in c:
            missing.append("%s: no root" % c["id"])
    return missing


def root_mismatches(clauses):
    """检测 root 与 ID 前缀不一致"""
    mismatches = []
    for c in clauses:
        cid = c.get("id", "")
        root = c.get("root", "")
        if root and not cid.startswith(root + "."):
            mismatches.append("%s root=%s" % (cid, root))
    return mismatches


def broken_refs(clauses):
    """检测引用了不存在的条款"""
    referenced_ids = set(cl["id"] for cl in clauses)
    br = []
    for c in clauses:
        for ref in c.get("ref_ids", []):
            if ref not in referenced_ids:
                br.append((c["id"], ref))
    return br
