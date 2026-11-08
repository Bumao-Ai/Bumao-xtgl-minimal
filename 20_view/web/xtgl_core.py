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

"""XTGL Core —— 通用开源控制台内核（纯 Python 标准库，零依赖）

设计要点（对应 2026-11-02 架构评审）：
1. 路径无关：项目根按 命令行 > 环境变量 > 配置 > 默认（web 的父父目录）解析；
   支持中文、空格、跨盘、整体移动（项目根在自身树内时配置记空串）。
2. 三层规则：core（内核，不可覆盖）> default（默认）> user（用户）。
   用户层与内核层同 id 时拒绝用户条并记录冲突，绝不静默覆盖。
3. 首次启动：项目无效时不崩，返回 setup_required；/setup 提供向导，
   可检环境、建骨架、写配置、建第一个任务。
4. 演示环境：--demo 使用 demo/ 合成数据，UI 明确标注。
5. 只读为默认：除向导的四个写接口（写配置/建骨架/建任务/选目录）外，
   服务端不修改项目文件。
"""
from __future__ import annotations

import datetime
import http.server
import json
import os
import re
import shutil
import subprocess
import tempfile
import sys
import threading
import socket
import time
import ctypes
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CORE_VERSION = "0.10"
SCHEMA = 2
HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "web_config.json"
DEMO_DIR = HERE / "demo"
LAYERS = ("core", "default", "user")
LAYER_LABEL = {"core": "内核", "default": "默认", "user": "用户"}
STATIC_FILES = {"index.html", "setup.html", "tutorial.html", "favicon.png", "i18n.js"}
DOC_ALLOW = ("XINSHOU-ZHINAN.txt", "README.md", "README-HX.txt", "CHANGELOG.md",
             "COMPLIANCE.md", "TUTORIAL.md", "TUTORIAL.en.md")
DEMO_MARK = "demo_meta.json"
# 三端共用同一份人工判定记录，放在仓库之外，避免私人路径进入开源包
MANUAL_PATH = Path.home() / ".xtgl" / "manual.json"
MANUAL_DEFAULT = [
    {"key": "b_check", "label": "最近自检已人工核实", "ok": False},
    {"key": "b_defect", "label": "缺陷台账已人工核实", "ok": False},
    {"key": "b_log", "label": "当日日志已人工核实", "ok": False},
    {"key": "ack_open", "label": "已知悉未闭环项并安排处理", "ok": False},
]

# 健康判定阈值：与冻结的桌面端同一份文件（仓库外，三端共读），用户可改、不写死在代码里。
HEALTH_RULES_PATH = Path.home() / ".xtgl" / "health_rules.json"
HEALTH_DEFAULTS = {"disk_min_free_gb": 80, "task_archive_days": 0}
# 导出落盘前缀沿用桌面端那一套（wenti_qingdan／yichang_qingdan／jiaojie_／ai_zhenduan）：
# 前缀不一致，「每类只留 20 份」就会各清各的，同一个资产目录越清越多。
EXPORT_PREFIX = {"defects": "wenti_qingdan", "anomalies": "yichang_qingdan",
                 "ai": "ai_zhenduan", "handover": "jiaojie", "goals": "mubiao",
                 "tasks": "liudang", "projects": "gongcheng"}
EXPORT_KEEP = 20
EXPORT_KIND_ALIAS = {"wenti_qingdan": "defects", "yichang_qingdan": "anomalies",
                     "ai_zhenduan": "ai", "mubiao": "goals", "liudang": "tasks",
                     "gongcheng": "projects", "缺陷": "defects", "异常": "anomalies",
                     "目标": "goals", "任务": "tasks", "项目": "projects",
                     "交接": "handover", "长期目标": "goals"}

AI_CONFIG_DEFAULT = Path.home() / ".xtgl" / "ai_yunwei.json"
AI_PRESETS = (
    {"id": "local_ollama", "label": "Ollama（本地）", "baseUrl": "http://127.0.0.1:11434/v1", "model": "qwen2.5:7b"},
    {"id": "lm_studio", "label": "LM Studio（本地）", "baseUrl": "http://127.0.0.1:1234/v1", "model": "local-model"},
    {"id": "deepseek", "label": "DeepSeek", "baseUrl": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    {"id": "openai", "label": "OpenAI 兼容端点", "baseUrl": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    {"id": "custom", "label": "自定义", "baseUrl": "", "model": ""},
)


def _ai_public_key(value):
    value = str(value or "")
    if not value:
        return ""
    return "已配置（长度 %d，末4位 %s）" % (len(value), value[-4:])


# 浏览器：优先 Google Chrome，找不到再退回系统默认。
CHROME_CANDIDATES = (
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
)


def find_chrome() -> str:
    for tpl in CHROME_CANDIDATES:
        p = os.path.expandvars(tpl)
        if p and "%" not in p and os.path.isfile(p):
            return p
    return shutil.which("chrome") or shutil.which("chrome.exe") or ""


def open_browser(url: str) -> str:
    """优先用 Chrome 新窗口打开；Chrome 不在则退回系统默认浏览器。"""
    exe = find_chrome()
    if exe:
        try:
            subprocess.Popen([exe, "--new-window", url])
            return "chrome"
        except OSError:
            pass
    try:
        import webbrowser
        webbrowser.open(url)
        return "default"
    except Exception:  # noqa: BLE001
        return "failed"


class ConfigError(Exception):
    """配置/路径类错误，直接展示给人看。"""


# ------------------------------------------------------------------
# 配置
# ------------------------------------------------------------------
def _read_json(path: Path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def normalize_config(raw: dict, allow_missing_engine: bool = False) -> dict:
    """兼容 v1（engine_cwd / engine_cmd / rules_dir）与 v2（engine / rules）。

    allow_missing_engine=True 仅用于「配置缺失/损坏」的降级路径：此时返回可用的
    最小配置（engine.cmd 为空），让服务起得来、向导能修；显式配置走默认校验。
    """
    raw = raw or {}
    eng = raw.get("engine") or {}
    rule_raw = raw.get("rules")
    if not rule_raw:
        rule_raw = {
            "core": {"dir": "core_rules", "enabled": False},
            "default": {"dir": raw.get("rules_dir") or "rules", "enabled": True},
            "user": {"dir": "rules_user", "enabled": False},
        }
    rules = {}
    for name in LAYERS:
        spec = rule_raw.get(name) or {}
        d = str(spec.get("dir") or "").strip()
        rules[name] = {
            "dir": d,
            "enabled": bool(spec.get("enabled", name == "default" and bool(d))),
        }
    cmd = eng.get("cmd") or raw.get("engine_cmd")
    if not cmd:
        # 不再回退到写死的 engine.py。路线B 统一内核后三端入口是
        # BumaoXTGL_<Edition>_v01.py；engine.py 在任一端 10_rac 下都已不存在
        # （旧引擎已归档为 90_lishi/old_engine_legacy_<edition>_v01.py）。
        # 回退到它只会抛出与本因无关的 FileNotFoundError，把真因「配置缺
        # engine.cmd」掩盖掉（Q121）。此处也不自动猜入口：normalize_config
        # 阶段拿不到 self.root，相对 cwd 无从解析——真正的解析在 run 阶段
        # （cwd = self.root / eng["cwd"]）。缺配置就显式报错给人看。
        if not allow_missing_engine:
            raise ConfigError(
                "web_config.json 缺 engine.cmd（或旧字段 engine_cmd），无法确定引擎入口。"
                '请显式配置，例如 "engine": {"cwd": "10_rac", '
                '"cmd": ["python", "BumaoXTGL_<Edition>_v01.py"]}')
        cmd = []
    if isinstance(cmd, str):
        cmd = [cmd]
    goal_path = ""
    if "goals" in raw:
        goal_path = str(raw.get("goals") or "").strip()
    else:
        goal_path = os.environ.get("XTGL_GOALS", "").strip()
        if not goal_path:
            # 个人目标文件放在仓库之外，避免把私人路径写进开源包
            _p = Path.home() / ".xtgl" / "goals.txt"
            goal_path = str(_p) if _p.is_file() else ""
    short_path = ""
    if "short_tasks" in raw:
        short_path = str(raw.get("short_tasks") or "").strip()
    else:
        short_path = os.environ.get("XTGL_SHORT_TASKS", "").strip()
        if not short_path:
            _s = Path.home() / ".xtgl" / "short_tasks.txt"
            short_path = str(_s) if _s.is_file() else ""
    log_path = str(raw.get("logs") or os.environ.get("XTGL_LOGS") or "").strip()
    # 周期待办总表（11.50）：与短期任务并列的第三种任务源，路径显式配置，不猜
    daiban_path = str(raw.get("daiban") or os.environ.get("XTGL_DAIBAN") or "").strip()
    # Agent 系统健康三项的真实数据源（与桌面端同源，不拿代理条件凑数）
    defect_path = str(raw.get("defects") or os.environ.get("XTGL_DEFECTS") or "").strip()
    check_log_dir = str(raw.get("check_log_dir") or os.environ.get("XTGL_CHECK_LOG_DIR") or "").strip()
    return {
        "schema": raw.get("schema", SCHEMA),
        "title": raw.get("title") or "XTGL",
        # 发行版后缀（Community/Minimal/Personal）：随 web_config 发行配置走，
        # 内核不含品牌硬编码；读不到就不带后缀（display_title 兜底）。
        "product_edition": str(raw.get("product_edition") or "").strip(),
        "subtitle": raw.get("subtitle") or "",
        "subtitle_en": str(raw.get("subtitle_en") or "").strip(),
        "project_root": str(raw.get("project_root") or "").strip().strip('"'),
        "goals": goal_path,
        "short_tasks": short_path,
        "daiban": daiban_path,
        "logs": log_path,
        "defects": defect_path,
        "check_log_dir": check_log_dir,
        "port": int(raw.get("port") or 8804),
        "engine": {
            "cwd": eng.get("cwd") or raw.get("engine_cwd") or "10_rac",
            "cmd": [str(x) for x in cmd],
            "timeout": int(eng.get("timeout") or raw.get("engine_timeout") or 120),
            "enabled": bool(eng.get("enabled", True)),
        },
        "rules": rules,
        # 以下键必须显式带出去：normalize_config 是白名单返回，
        # 不在这里点名的配置一律读不到（capabilities／ai_config／anomaly 都踩过这个坑）。
        "capabilities": raw.get("capabilities") or [],
        "ai_config": str(raw.get("ai_config") or "").strip(),
        "projects": raw.get("projects") or {},
        "metrics": raw.get("metrics") or {},
        "oss": raw.get("oss") or {},
        "archive": raw.get("archive") or {},
        "health": raw.get("health") or {},
        "access": raw.get("access") or {},
        "export": raw.get("export") or {},
        "anomaly": raw.get("anomaly") or {},
        "backup": raw.get("backup") or {},
        "rules_library": raw.get("rules_library") or {},
    }


# 发行版标题：基础名 + 可选后缀（product_edition），同一份内核三端各显其名。
# 读不到 edition、或 edition 已含在基础名里，就不动——旧配置零回退。
def display_title(cfg: dict) -> str:
    base = str(cfg.get("title") or "").strip()
    edition = str(cfg.get("product_edition") or "").strip()
    if edition and edition not in base:
        return ("%s %s" % (base, edition)).strip()
    return base


def edition_labels(cfg: dict) -> dict:
    """端名中文称谓只从配置层 labels 取词；代码不写死任何中文端名。"""
    raw = (cfg or {}).get("labels") or {}
    out = {}
    for key in ("personal", "community", "minimal"):
        rec = raw.get(key) if isinstance(raw.get(key), dict) else {}
        out[key] = {"zh": str(rec.get("zh") or key),
                    "en": str(rec.get("en") or key.capitalize())}
    return out


def load_config(path: Path = DEFAULT_CONFIG):
    """返回 (cfg, error)。配置损坏不抛异常——服务要能起来，向导要能修。"""
    if not path.exists():
        return normalize_config({}, allow_missing_engine=True), \
            "配置文件不存在：%s" % path.name
    try:
        raw = _read_json(path)
    except json.JSONDecodeError as e:
        return normalize_config({}, allow_missing_engine=True), \
            "配置无法解析（第 %d 行）：%s" % (e.lineno, e.msg)
    except OSError as e:
        return normalize_config({}, allow_missing_engine=True), "配置读取失败：%s" % e
    if not isinstance(raw, dict):
        return normalize_config({}, allow_missing_engine=True), "配置根节点必须是对象"
    # 本机覆盖：优先仓库外的 ~/.xtgl/web_config.local.json，
    # 其次同目录 web_config.local.json；两者都不进开源包。
    # 测试用 XTGL_NO_LOCAL_OVERLAY=1 关闭，避免个人路径污染夹具。
    if os.environ.get("XTGL_NO_LOCAL_OVERLAY") != "1":
        for local in (Path.home() / ".xtgl" / "web_config.local.json",
                      path.with_name("web_config.local.json")):
            if not local.is_file():
                continue
            try:
                overlay = _read_json(local)
                if isinstance(overlay, dict):
                    raw = dict(raw)
                    raw.update(overlay)
                    break
            except Exception:  # noqa: BLE001
                continue
    return normalize_config(raw), None


def resolve_root(cfg: dict, cli_root=None):
    """返回 (Path|None, 来源说明, 错误)。优先级：命令行 > 环境变量 > 配置 > 默认。"""
    if cli_root:
        return _as_path(cli_root, HERE), "命令行 --root", None
    env = os.environ.get("XTGL_PROJECT_ROOT", "").strip()
    if env:
        return _as_path(env, HERE), "环境变量 XTGL_PROJECT_ROOT", None
    conf = (cfg.get("project_root") or "").strip()
    if conf:
        return _as_path(conf, HERE), "web_config.json", None
    return (HERE.parent.parent).resolve(), "默认（web 的上级项目根）", None


def _as_path(value, base: Path) -> Path:
    p = Path(str(value)).expanduser()
    if not p.is_absolute():
        p = (base / p)
    try:
        return p.resolve()
    except OSError:
        return p.absolute()


# 客户端名归一：与桌面端 logs_screen.dart 的 _clientName 同规则，
# 否则同一台机器会出现「DeepSeek」和「DeepSeek deepseek-flash（…）」两个客户端。
def client_name(raw) -> str:
    s = str(raw or "").strip()
    if not s:
        return "未标注"
    s = re.sub(r"（.*$", "", s).strip()
    s = re.sub(r"\s+deepseek.*$", "", s, flags=re.I).strip()
    # 白名单归一：回传件名与日志 who 列的写法统一到同一个客户端名，否则
    # 「workbuddy」「haness」这类小写签名与准入集合里的规范名对不上。
    s = HUICHUAN_ALIAS.get(s.lower(), s)
    return s or "未标注"


# N5 接入凭据回传目录：与桌面端 logs_screen.dart 的 _baselinePassed() 同一口径。
# 判据件是 <项目>\10_rac\adapters\jilu\huichuan\<端名>.txt，同含「已接入」与「ALL PASS」。
HUICHUAN_ALIAS = {
    "workbuddy": "WorkBuddy",
    "deepseek": "DeepSeek",
    "haness": "DeepSeek",     # Harness 端在账本里的旧签名，随 DeepSeek 判
    "harness": "DeepSeek",
    "dsh": "DeepSeek",
    "doubao": "豆包",
}


def huichuan_dir():
    """回传目录：环境变量优先，其次本端，再退到同机其它端。找不到返回 None。"""
    cands = []
    env = os.environ.get("XTGL_HUICHUAN_DIR", "").strip()
    if env:
        cands.append(Path(env))
    root = HERE.parent.parent
    for base in (root, root.parent / "personal", root.parent / "community",
                 root.parent / "minimal"):
        cands.append(base / "10_rac" / "adapters" / "jilu" / "huichuan")
    for c in cands:
        if c.is_dir():
            return c
    return None


def baseline_passed():
    """基线准入：四条里 ①②③ 的机器判据＝回传件同含「已接入」与「ALL PASS」；
    ④（账本有登记）由日志 who 列天然满足。白名单外的端一律不认。"""
    d = huichuan_dir()
    passed = set()
    if not d:
        return passed
    for f in d.iterdir():
        if not f.is_file():
            continue
        name = HUICHUAN_ALIAS.get(f.stem.lower())
        if not name:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "已接入" in text and "ALL PASS" in text:
            passed.add(name)
    return passed


def baseline_ok(name, passed):
    """客户端是否过基线；未过的一律不显示（不置灰、不占位）。"""
    if name in passed:
        return True
    # 角色签名随端走：Harness（DeepSeek）端在账本里的签名
    return name == "Harness" and "DeepSeek" in passed


# 历史执行者角色不是客户端：接入名册与统计不列；日志正文的 who 原样保留（审计用）
NON_CLIENT_PREFIXES = ("执行",)


# 项目键：以留档所在目录为准（...\40_renwu\<项目名>\benci_gongcheng.txt），
# 与桌面端 _logKey / 前端 logKey 三处同规则。不能直接用日志表的「任务」列——
# 那列历史上混着长标题，同一项目会被拆成多个名字。
def project_key(row) -> str:
    p = str(row.get("detail") or "").replace("\\", "/")
    p = re.sub(r"/+", "/", p)
    m = re.search(r"/40_renwu/([^/]+)/", p)
    return m.group(1) if m else "其他记录"


# ---------- 详细说明（明细）：与任务文件同名同目录的 .detail.json ----------
# 设计口径（2026-11-03）：任务文件（goals.txt / short_tasks.txt / daiban_zongbiao.txt）
# 仍是「一张看板」，只放短字段；长文（用户要求、给 AI 的具体提示词）放同名 sidecar，
# 这样 ① 看板解析不被多行文本污染 ② 三端读同一份 ③ 明细丢了看板照样能看。
def detail_path_of(board_path: Path) -> Path:
    """goals.txt -> goals.detail.json；short_tasks.txt -> short_tasks.detail.json"""
    return board_path.with_suffix(".detail.json")


def load_details(board_path: Path):
    p = detail_path_of(board_path)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001
        return {}
    items = data.get("items") if isinstance(data, dict) else None
    return items if isinstance(items, dict) else {}


def detail_of(details, item_id):
    d = details.get(str(item_id)) or {}
    return {
        "req": str(d.get("req") or ""),
        "prompt": str(d.get("prompt") or ""),
        "by": str(d.get("by") or ""),
        "at": str(d.get("at") or ""),
    }


def validate_root(root: Path) -> str:
    """返回错误文本；None 表示可用。"""
    if root is None:
        return "未指定项目根"
    try:
        if not root.exists():
            return "目录不存在：%s" % root
        if not root.is_dir():
            return "不是目录：%s" % root
        meta = root / "00_meta" / "meta.json"
        if not meta.exists():
            return "不是 XTGL 项目（缺 00_meta/meta.json）：%s" % root
        try:
            _read_json(meta)
        except json.JSONDecodeError as e:
            return "00_meta/meta.json 无法解析：%s" % e
        except OSError as e:
            return "00_meta/meta.json 读取失败：%s" % e
        if not os.access(str(root), os.R_OK):
            return "目录不可读（权限不足）：%s" % root
    except OSError as e:
        return "路径不可用：%s（%s）" % (root, e)
    return None


# ------------------------------------------------------------------
# 规则解析与分层
# ------------------------------------------------------------------
def _collect_clauses(obj, out, seen):
    if isinstance(obj, dict):
        cid = obj.get("id")
        if cid is not None and ("title" in obj or "body" in obj):
            cid = str(cid)
            if cid not in seen:
                seen.add(cid)
                title = str(obj.get("title") or obj.get("root") or "")
                body = obj.get("body")
                if isinstance(body, list):
                    body = [str(x) for x in body]
                else:
                    body = [str(body)] if body else []
                out.append({"id": cid, "title": title, "body": body})
        for v in obj.values():
            _collect_clauses(v, out, seen)
    elif isinstance(obj, list):
        for v in obj:
            _collect_clauses(v, out, seen)


def extract_clauses(data):
    out, seen = [], set()
    _collect_clauses(data, out, seen)
    return out


def core_compatible(spec, version=CORE_VERSION):
    """模块声明的内核范围：'^2.0' 同主版本；'2.0' 前缀匹配。"""
    spec = str(spec or "").strip()
    if not spec:
        return False
    if spec.startswith("^"):
        return version.split(".")[0] == spec[1:].split(".")[0]
    return version == spec or version.startswith(spec + ".")


GOAL_KEYS = ("目标", "阶段", "状态", "进度", "关联项目", "关联文件", "下一步", "证据", "复核",
             "完成于")

# ---- 任务生命周期（2026-11-03 新增）----
# 用户问题：打了勾的任务不消退，列表越积越长；归档的也一直在。
# 口径：① 状态含「已完成/已归档/已关闭」= 完成 → 退出主列表，进「已完成」折叠区；
#      ② 完成日期取「完成于」，没有就退回「复核」；
#      ③ 完成满 RETIRE_DAYS 天 → 连折叠区也不显示（文件里还在，由 xtgl_clean.py 搬进归档）。
DONE_WORDS = ("已完成", "已归档", "已关闭")
RETIRE_DAYS = 30


def _parse_date(s):
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", str(s or "").strip())
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def task_lifecycle(item, today=None):
    today = today or datetime.date.today()
    status = str(item.get("状态") or "")
    done = any(w in status for w in DONE_WORDS)
    raw = str(item.get("完成于") or item.get("复核") or "").strip()
    d = _parse_date(raw)
    days = (today - d).days if d else None
    retired = bool(done and days is not None and days >= RETIRE_DAYS)
    return {"done": done, "done_at": raw, "days_since": days, "retired": retired,
            "retire_days": RETIRE_DAYS}


def parse_goals(text: str):
    """解析 [G编号] + 「键：值」格式；返回列表，不抛异常。"""
    goals, cur = [], None
    for raw in (text or "").splitlines():
        line = raw.strip()
        m = re.match(r"^\[([A-Za-z])(\d+)\]$", line)
        if m:
            cur = {"id": m.group(1).upper() + m.group(2)}
            goals.append(cur)
            continue
        if cur is None or "：" not in line:
            continue
        key, val = line.split("：", 1)
        key = key.strip()
        if key in GOAL_KEYS:
            cur[key] = val.strip()
    return goals



def _safe_unlink(p):
    try:
        os.remove(str(p))
    except OSError:
        pass


def _slug_id(s):
    """把任意路径／盘符／标题压成可当 key 用的短串（不进代码逻辑，只进展示键）。"""
    t = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", str(s or "").strip())
    t = t.strip("_")
    return (t[:24] or "x")


def _port_open(host, port, timeout):
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True, "端口在听"
    except ConnectionRefusedError:
        return False, "拒绝连接"
    except socket.timeout:
        return False, "连接超时"
    except OSError as e:
        return False, "连不上（%s）" % str(e)[:80]


def _file_busy(path):
    """占用判定：能以 r+b 打开＝没被独占锁住。只打开、不写一个字节。"""
    try:
        f = open(path, "r+b")
    except FileNotFoundError:
        return False, "文件不在"
    except PermissionError:
        return True, "被别的进程独占（PermissionError）"
    except OSError as e:
        return True, "打不开：%s" % str(e)[:80]
    try:
        return False, "可读写、未被独占"
    finally:
        try:
            f.close()
        except OSError:
            pass


def _power_read():
    """电量行：与内核 11.54（1）同一口径（Q220 修正后的字节序）。

    返回 (标签, 详情, 百分比或 None, 读到了没有)。读不到就说读不到，不猜数。
    """
    try:
        if not sys.platform.startswith("win"):
            raise OSError("非 Windows")

        class _PS(ctypes.Structure):
            _fields_ = [("ACLineStatus", ctypes.c_ubyte),
                        ("BatteryFlag", ctypes.c_ubyte),
                        ("BatteryLifePercent", ctypes.c_ubyte),
                        ("SystemStatusFlag", ctypes.c_ubyte),
                        ("BatteryLifeTime", ctypes.c_int),
                        ("BatteryFullLifeTime", ctypes.c_int)]

        ps = _PS()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(ps)):
            raise OSError("GetSystemPowerStatus 调用失败")
        src = "插电" if ps.ACLineStatus == 1 else (
            "电池" if ps.ACLineStatus == 0 else "电源状态未知")
        pct = None if ps.BatteryLifePercent > 100 else int(ps.BatteryLifePercent)
        tail = "" if ps.BatteryLifeTime >= 0 else "，剩余寿命不可读"
        return ("电量", "电量：%s（%s%s）" % (
            "未知" if pct is None else "%d%%" % pct, src, tail), pct, True)
    except Exception as e:  # noqa: BLE001
        return ("电量", "电量：读取失败（%s）——须手动核" % str(e)[:80], None, False)


# ------------------------------------------------------------------
# 控制台
# ------------------------------------------------------------------
class Console:
    def __init__(self, config_path: Path = DEFAULT_CONFIG, cli_root=None,
                 demo: bool = False, cli_port=None):
        self.config_path = Path(config_path)
        self.demo = demo
        self.cli_port = cli_port
        self.config_error = None
        self.cfg, err = load_config(self.config_path)
        self.config_error = err
        if demo:
            # 演示模式不读真实配置，避免把 demo 路径写进用户配置
            self.cfg = normalize_config({
                "title": "Bumao XTGL（演示）",
                "subtitle": "合成数据 · 不需要真实项目",
                "port": 8899,
                "engine": {"cwd": "10_rac", "cmd": [sys.executable, "fake_engine.py"], "timeout": 30},
                "rules": {
                    "core": {"dir": "rules_core", "enabled": True},
                    "default": {"dir": "rules", "enabled": True},
                    "user": {"dir": "rules_user", "enabled": True},
                },
            })
        self.root, self.root_source, _ = resolve_root(
            self.cfg, str(DEMO_DIR) if demo else cli_root)
        if demo:
            self.root_source = "内置演示项目"
            self.config_error = None
        self.root_error = validate_root(self.root)

    # ---------- 基础信息 ----------
    def meta(self):
        if self.root_error:
            return {"error": self.root_error}
        try:
            return _read_json(self.root / "00_meta" / "meta.json")
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}

    def python_version(self):
        return sys.version.split()[0]

    def labels(self):
        return edition_labels(self.cfg)

    def label(self, key):
        rec = self.labels().get(str(key or "").strip().lower()) or {}
        return str(rec.get("zh") or key or "")

    def config_view(self):
        return {
            "path": str(self.config_path),
            "error": self.config_error,
            "schema": self.cfg.get("schema"),
            "title": self.cfg.get("title"),
            "subtitle": self.cfg.get("subtitle"),
            "port": self.cfg.get("port"),
            "engine": self.cfg.get("engine"),
            "rules": self.cfg.get("rules"),
            "labels": self.labels(),
        }

    # ---------- 规则 ----------
    def layer_path(self, spec: dict):
        """规则目录解析：绝对路径直接用；相对路径先 engine.cwd 再项目根。

        v1 的语义是「相对引擎目录」（如 10_rac/zhunze）；通用版允许把规则放在
        项目根（rules/），两种都认，先存在的优先。
        """
        d = str(spec.get("dir") or "").strip()
        if not d or self.root_error:
            return None
        p = Path(d)
        if p.is_absolute():
            return p
        cands = [self.root / self.cfg["engine"]["cwd"] / d, self.root / d]
        for c in cands:
            if c.is_dir():
                return c
        return cands[0]

    def rules(self):
        """按层加载并合并。core 优先，user 可覆盖 default，但绝不覆盖 core。"""
        summary, clauses, conflicts, errors = [], [], [], []
        file_rows = []
        index = {}
        for layer in LAYERS:
            spec = self.cfg["rules"].get(layer, {})
            row = {"layer": layer, "label": LAYER_LABEL[layer], "dir": spec.get("dir", ""),
                   "enabled": bool(spec.get("enabled")), "exists": False, "files": 0, "clauses": 0}
            summary.append(row)
            if not spec.get("enabled") or not spec.get("dir") or self.root_error:
                continue
            d = self.layer_path(spec)
            if d is None or not d.is_dir():
                errors.append("%s 层目录不存在：%s" % (LAYER_LABEL[layer], spec["dir"]))
                continue
            row["exists"] = True
            files = sorted(d.glob("*.json"))
            row["files"] = len(files)
            for f in files:
                try:
                    data = _read_json(f)
                except Exception as e:  # noqa: BLE001
                    errors.append("%s/%s 解析失败：%s" % (spec["dir"], f.name, e))
                    file_rows.append({"file": f.name, "layer": layer, "clauses": 0, "error": str(e)})
                    continue
                got = extract_clauses(data)
                row["clauses"] += len(got)
                file_rows.append({"file": f.name, "layer": layer, "clauses": len(got)})
                for c in got:
                    cid = c["id"]
                    prev = index.get(cid)
                    if prev and prev["layer"] == "core":
                        conflicts.append({
                            "id": cid, "layer": layer, "file": f.name,
                            "reason": "内核层条款不可被覆盖，已忽略该条",
                        })
                        continue
                    index[cid] = dict(c, layer=layer, file=f.name)
        clauses = list(index.values())
        return {"rules": summary, "file_rows": file_rows, "clauses": clauses,
                "conflicts": conflicts, "errors": errors}

    def rules_of_file(self, filename: str, layer=None):
        filename = os.path.basename(str(filename))
        order = [layer] if layer in LAYERS else list(LAYERS)
        for name in order:
            spec = self.cfg["rules"].get(name, {})
            if not spec.get("enabled") or not spec.get("dir") or self.root_error:
                continue
            d = self.layer_path(spec)
            if d is None:
                continue
            fp = d / filename
            if fp.is_file():
                try:
                    got = extract_clauses(_read_json(fp))
                except Exception as e:  # noqa: BLE001
                    return {"file": filename, "layer": name, "error": str(e), "clauses": []}
                return {"file": filename, "layer": name, "clauses": got[:400]}
        return {"file": filename, "error": "未找到该规则文件", "clauses": []}

    # ---------- 引擎 ----------
    def run_engine(self):
        if self.root_error:
            return {"ok": False, "exit_code": -1, "cmd": "", "cwd": "", "lines": [self.root_error]}
        eng = self.cfg["engine"]
        if not eng.get("enabled", True):
            return {"ok": False, "exit_code": -1, "cmd": "", "cwd": "",
                    "lines": ["引擎检查已关闭（web_config.json: engine.enabled=false）"]}
        cwd = self.root / eng["cwd"]
        cmd = list(eng["cmd"])
        if not cmd:
            return {"ok": False, "exit_code": -1, "cmd": "", "cwd": str(cwd),
                    "lines": ["未配置引擎命令"]}
        if Path(cmd[0]).name.lower() in ("python", "python.exe", "python3", "python3.exe"):
            cmd[0] = sys.executable
        if not cwd.is_dir():
            return {"ok": False, "exit_code": -1, "cmd": " ".join(eng["cmd"]), "cwd": str(cwd),
                    "lines": ["引擎目录不存在：%s" % eng["cwd"]]}
        # -B 只作用于本进程；子进程要靠环境变量，否则引擎会在内核目录写 __pycache__
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
                   PYTHONDONTWRITEBYTECODE="1")
        try:
            proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace",
                                  timeout=eng["timeout"], env=env)
        except FileNotFoundError:
            return {"ok": False, "exit_code": -1, "cmd": " ".join(eng["cmd"]), "cwd": str(cwd),
                    "lines": ["找不到引擎：%s" % eng["cmd"][0]]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "exit_code": -2, "cmd": " ".join(eng["cmd"]), "cwd": str(cwd),
                    "lines": ["引擎超时（>%d 秒）" % eng["timeout"]]}
        except OSError as e:
            return {"ok": False, "exit_code": -1, "cmd": " ".join(eng["cmd"]), "cwd": str(cwd),
                    "lines": ["引擎启动失败：%s" % e]}
        out = (proc.stdout or "") + (proc.stderr or "")
        _lines = out.rstrip().splitlines()
        _cl = [l.strip() for l in _lines if l.strip().startswith("[结论]")]
        # 凭据三件套（rc + 结论 + 时刻）：check_run 声明的 credential 要在界面上可对得上，
        # 只给退出码不够——「rc=0 但没说哪一轮」无法与绿票账本相接。
        return {"ok": proc.returncode == 0, "exit_code": proc.returncode,
                "cmd": " ".join(eng["cmd"]), "cwd": str(cwd),
                "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "conclusion": _cl[-1] if _cl else "",
                "lines": _lines}

    # ---------- 任务与文档 ----------
    def tasks(self):
        if self.root_error:
            return []
        base = self.root / "40_renwu"
        rows = []
        if not base.is_dir():
            return rows
        for d in sorted(base.iterdir()):
            if not d.is_dir() or "guidang" in d.name:
                continue
            files = [p.name for p in d.rglob("*") if p.is_file()]
            if not files:
                continue
            rec = [f for f in files
                   if f in ("benci_gongcheng.txt", "renwu_liudang.txt", "xiangmu_jilu.txt")
                   or "liudang" in f]
            rows.append({"name": d.name, "files": len(files), "record": rec[0] if rec else ""})
        return rows

    def doc(self, name):
        name = os.path.basename(str(name))
        if name not in DOC_ALLOW:
            return {"error": "不允许读取该文件"}
        cands = [self.root / name, self.root / "00_meta" / name, HERE / name]
        if name == "README.md":
            cands.append(self.root / "README-HX.txt")
        for p in cands:
            if p.is_file():
                try:
                    return {"name": name, "text": p.read_text(encoding="utf-8")[:60000]}
                except Exception as e:  # noqa: BLE001
                    return {"error": str(e)}
        return {"error": "文件不存在：%s" % name}

    # ---------- 模块清单（平台入口） ----------
    def modules(self):
        p = HERE / "modules.json"
        if not p.is_file():
            return {"ok": False, "core": CORE_VERSION, "modules": [],
                    "errors": ["缺 modules.json"]}
        try:
            data = _read_json(p)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "core": CORE_VERSION, "modules": [],
                    "errors": ["modules.json 解析失败：%s" % e]}
        mods = data.get("modules") or []
        errors = []
        for m in mods:
            if not core_compatible(m.get("core")):
                errors.append("模块 %s 要求内核 %s，当前 %s"
                              % (m.get("id"), m.get("core"), CORE_VERSION))
        return {"ok": not errors, "core": CORE_VERSION,
                "list_version": data.get("schema"), "modules": mods, "errors": errors}

    # ---------- 短期 / 长期任务（同一套字段与解析） ----------
    def _cfg_path(self, spec):
        """配置里的相对路径一律按项目根解——与 snapshot.root_dir／conf_path 同一把尺子。

        原先按 HERE（web 目录）解，同一条上跳两级的相对路径服务端比快照少上两级，
        于是快照有数、界面却报「文件不存在」。用户自填的 root 仍走 _as_path(…, HERE)。
        """
        return _as_path(spec, self.root or HERE.parent.parent)

    def _board(self, spec, missing_msg):
        if not spec:
            return {"ok": False, "path": "", "count": 0, "list": [], "error": missing_msg}
        path = self._cfg_path(spec)
        if not path.is_file():
            return {"ok": False, "path": str(path), "count": 0, "list": [],
                    "error": "文件不存在"}
        try:
            text = path.read_text(encoding="utf-8-sig")
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "path": str(path), "count": 0, "list": [],
                    "error": "读取失败：%s" % e}
        items = []
        for g in parse_goals(text):
            raw = str(g.get("进度", "0")).replace("%", "").strip() or "0"
            try:
                prog = max(0, min(100, int(raw)))
            except ValueError:
                prog = 0
            projects = [x.strip() for x in re.split(r"[、,，]", g.get("关联项目", "")) if x.strip()]
            files = [x.strip() for x in re.split(r"[；;]", g.get("关联文件", "")) if x.strip()]
            items.append(dict(g, progress=prog, projects=projects,
                              files=[{"path": f, "exists": os.path.exists(f)} for f in files]))
        details = load_details(path)
        for it in items:
            d = detail_of(details, it.get("id", ""))
            it["detail"] = d
            it["has_detail"] = bool(d["req"] or d["prompt"])
            it.update(task_lifecycle(it))
        active = [x for x in items if not x["done"]]
        done = [x for x in items if x["done"] and not x["retired"]]
        retired = [x for x in items if x["retired"]]
        return {"ok": True, "path": str(path), "display": self._tilde(path),
                "detail_path": str(detail_path_of(path)),
                "detail_display": self._tilde(detail_path_of(path)),
                "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime)),
                "count": len(items), "active": len(active), "done": len(done),
                "retired": len(retired),
                "retire_days": RETIRE_DAYS,
                "list": active + done + retired}

    def goals(self):
        return self._board(self.cfg.get("goals"),
                           "未配置长期任务文件（web_config.json 的 goals）")

    def short_tasks(self):
        return self._board(self.cfg.get("short_tasks"),
                           "未配置短期任务文件（web_config.json 的 short_tasks）")

    def daiban(self):
        """周期待办总表（11.50）：8 列表格，与短期任务并列的第三种任务源。"""
        spec = self.cfg.get("daiban") or ""
        if not spec:
            return {"ok": False, "list": [], "count": 0,
                    "error": "未配置待办总表（web_config.json 的 daiban）"}
        path = self._cfg_path(spec)
        if not path.is_file():
            return {"ok": False, "list": [], "count": 0,
                    "display": self._tilde(path), "error": "文件不存在"}
        try:
            text = path.read_text(encoding="utf-8-sig")
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "list": [], "count": 0, "error": "读取失败：%s" % e}
        details = load_details(path)
        rows = []
        for line in text.splitlines():
            s = line.strip()
            if not s.startswith("|"):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) < 8:
                continue
            if cells[0] == "编号" or set(cells[0]) <= set("-: "):
                continue  # 表头与分隔行
            d = detail_of(details, cells[0])
            rows.append({
                "id": cells[0], "name": cells[1], "kind": cells[2],
                "cycle": cells[3], "last": cells[4], "next": cells[5],
                "status": cells[6], "note": cells[7],
                "has_detail": bool(d["req"] or d["prompt"]),
                "detail_at": d["at"],
            })
        return {"ok": True, "list": rows, "count": len(rows),
                "display": self._tilde(path),
                "detail_display": self._tilde(detail_path_of(path))}

    # ---------- 工作日志：按天溯源到项目留档 ----------
    # ---------- Agent 系统健康：三项判据的真数据源（与桌面端同口径） ----------
    def defects(self):
        """缺陷台账：九列表（状态在第 8 列），判「已闭环」＝状态含「闭环」且不含「未闭环」。"""
        spec = self.cfg.get("defects") or ""
        if not spec:
            return {"configured": False, "total": 0, "open": 0, "clean": False,
                    "error": "未配置缺陷台账（web_config.json 的 defects）"}
        path = self._cfg_path(spec)
        if not path.is_file():
            return {"configured": True, "total": 0, "open": 0, "clean": False,
                    "display": self._tilde(path), "error": "文件不存在"}
        try:
            text = path.read_text(encoding="utf-8-sig")
        except Exception as e:  # noqa: BLE001
            return {"configured": True, "total": 0, "open": 0, "clean": False,
                    "error": "读取失败：%s" % e}
        total = closed = 0
        open_ids = []
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [x.strip() for x in line.split("|")][1:-1]
            if len(cells) < 9 or not re.match(r"^[A-Za-z]{0,3}\d{1,4}$", cells[0] or ""):
                continue
            total += 1
            st = cells[7]
            if "闭环" in st and "未闭环" not in st:
                closed += 1
            else:
                open_ids.append(cells[0])
        return {"configured": True, "total": total, "closed": closed,
                "open": len(open_ids), "open_ids": open_ids[:10],
                "clean": total > 0 and not open_ids,
                "display": self._tilde(path)}

    def last_check(self):
        """最后一次 check 的结论：取 check_YYYYMMDD_HHMMSS.log 里最新的一个。"""
        spec = self.cfg.get("check_log_dir") or ""
        if not spec:
            return {"configured": False, "ok": False,
                    "error": "未配置自检日志目录（web_config.json 的 check_log_dir）"}
        d = self._cfg_path(spec)
        if not d.is_dir():
            return {"configured": True, "ok": False, "display": self._tilde(d),
                    "error": "目录不存在"}
        files = []
        for p in d.iterdir():
            m = re.match(r"^check_(\d{8})_(\d{6})\.log$", p.name)
            if p.is_file() and m:
                files.append((m.group(1) + m.group(2), p))
        if not files:
            return {"configured": True, "ok": False, "display": self._tilde(d),
                    "error": "目录里没有 check 日志"}
        files.sort(key=lambda x: x[0], reverse=True)
        key, p = files[0]
        try:
            body = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            return {"configured": True, "ok": False, "error": "读取失败：%s" % e}
        m = re.search(r"\[结论\]\s*([^\n]*)", body)
        concl = m.group(1).strip() if m else "未读到结论"
        return {"configured": True, "ok": "ALL PASS" in concl, "conclusion": concl,
                "at": "%s-%s-%s %s:%s:%s" % (key[0:4], key[4:6], key[6:8],
                                             key[8:10], key[10:12], key[12:14]),
                "file": p.name, "display": self._tilde(p)}

    def logs(self, limit=30):
        spec = self.cfg.get("logs") or ""
        if not spec:
            return {"ok": False, "list": [], "count": 0,
                    "error": "未配置日志文件（web_config.local.json 的 logs）"}
        path = self._cfg_path(spec)
        if not path.is_file():
            return {"ok": False, "list": [], "count": 0,
                    "display": self._tilde(path), "error": "文件不存在"}
        try:
            text = path.read_text(encoding="utf-8-sig")
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "list": [], "count": 0, "error": "读取失败：%s" % e}
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [x.strip() for x in line.split("|")]
            if len(cells) < 8:
                continue
            cells = cells[1:-1]
            if len(cells) < 6 or not re.match(r"^\d{4}-\d{2}-\d{2}$", cells[0]):
                continue
            detail = cells[5]
            rows.append({
                "date": cells[0], "time": cells[1], "who": cells[2],
                "task": cells[3], "what": cells[4], "detail": detail,
                "detail_name": os.path.basename(detail) if detail else "",
                "exists": bool(detail) and os.path.exists(detail),
            })
        rows = rows[-limit:][::-1]
        return {"ok": True, "display": self._tilde(path), "count": len(rows), "list": rows}

    def clients(self, logs=None):
        """已接入客户端：从工作日志的 who 列汇总，名字按 client_name() 归一。

        不另建清单文件——「接入」的事实由日志本身证明：谁在这台机器上留下过登记，
        谁就算接入。这样清单永远不会和现实脱节（没有登记就没有条目）。
        """
        lg = logs if isinstance(logs, dict) else self.logs(limit=100000)
        rows = lg.get("list") or []
        passed = baseline_passed()
        agg = {}
        for r in rows:
            name = client_name(r.get("who"))
            if name.startswith(NON_CLIENT_PREFIXES):
                continue
            # 基线准入：未过基线的客户端不显示（与桌面端 _baselineOk 同口径）
            if not baseline_ok(name, passed):
                continue
            a = agg.setdefault(name, {"name": name, "count": 0, "last": "",
                                      "projects": set()})
            a["count"] += 1
            stamp = ("%s %s" % (r.get("date") or "", r.get("time") or "")).strip()
            if stamp > a["last"]:
                a["last"] = stamp
            a["projects"].add(project_key(r))
        out = []
        for a in agg.values():
            a["projects"] = len(a["projects"])
            out.append(a)
        out.sort(key=lambda x: (-x["count"], x["name"]))
        return {"ok": bool(lg.get("ok")), "count": len(out), "list": out,
                "total": len(rows), "display": lg.get("display") or "",
                "error": lg.get("error") or ""}

    def goals_export(self):
        d = self.goals()
        out = ["# XTGL 长期目标导出", "",
               "生成：%s" % time.strftime("%Y-%m-%d %H:%M"),
               "源文件：%s" % (d.get("display") or "（未配置）"), ""]
        if not d.get("ok"):
            out += ["状态：%s" % d.get("error", "不可用"), ""]
        for g in d.get("list", []):
            out += ["## %s %s" % (g.get("id", ""), g.get("目标", "")), "",
                    "- 阶段：%s" % g.get("阶段", ""),
                    "- 状态：%s（%d%%）" % (g.get("状态", ""), g.get("progress", 0)),
                    "- 关联项目：%s" % "、".join(g.get("projects", [])),
                    "- 关联文件："]
            for f in g.get("files", []):
                out.append("  - %s（%s）" % (f["path"], "存在" if f["exists"] else "缺失"))
            out += ["- 下一步：%s" % g.get("下一步", ""),
                    "- 证据：%s" % g.get("证据", ""),
                    "- 复核：%s" % g.get("复核", ""), ""]
        out += ["---", "源文件为准；导出只列路径与存在状态，不复制项目文件。", ""]
        return "\n".join(out)

    # ---------- 人工判定（机器算不了的，允许人画勾） ----------
    # 三端统一 key 命名空间（电脑健康已整块移出，不再有 A 段）：
    #   System: b_check, b_defect, b_log
    #   Tasks: task_<id>
    #   Legacy (兼容旧数据): a_* / review_a / review_b 三类历史残留读时丢弃；
    #                        health_* 自动映射到对应的标准 key
    def manual(self):
        items, seen = [], set()
        if MANUAL_PATH.is_file():
            try:
                data = _read_json(MANUAL_PATH)
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "items": [], "map": {}, "path": str(MANUAL_PATH),
                        "updated": "", "error": "manual.json 解析失败：%s" % e}
            for x in (data.get("items") or []):
                if not isinstance(x, dict) or not x.get("key"):
                    continue
                k = str(x["key"])
                # 电脑健康已移出：A 段历史残留读时丢弃，下次写回自然清盘
                if k.startswith("a_") or k in ("review_a", "review_b"):
                    continue
                # 兼容旧 key：health_* -> 映射到对应的标准 key
                if k.startswith("health_"):
                    legacy_map = {
                        "health_meta": "b_check",
                        "health_rules": "b_check",
                        "health_conflict": "b_check",
                        "health_tasks": "b_log",
                    }
                    k = legacy_map.get(k, k)
                seen.add(k)
                _ok = bool(x.get("ok"))
                _v = str(x.get("verdict") or "")
                if _v not in ("auto", "pass", "fail"):
                    _v = "pass" if _ok else "auto"      # 兼容只有 ok 的旧记录
                _label = re.sub(r"^[AB]\s*·\s*", "", str(x.get("label") or k))
                items.append({"key": k, "label": _label,
                              "ok": _ok, "verdict": _v,
                              "note": str(x.get("note") or ""),
                              "at": str(x.get("at") or "")})
            updated = data.get("updated", "")
        else:
            updated = ""
        for d in MANUAL_DEFAULT:
            if d["key"] not in seen:
                items.append(dict(d))
        return {"ok": True, "items": items, "map": {i["key"]: i["ok"] for i in items},
                "path": str(MANUAL_PATH), "updated": updated,
                "note": "人工勾选可覆盖机器判据；被覆盖项标「人工」"}

    def set_manual(self, key, ok, label=None, verdict=None):
        """人工裁定：verdict = auto / pass / fail。人工压过机器，两个方向都压。"""
        key = str(key or "").strip()
        if not re.match(r"^[A-Za-z0-9_]{1,40}$", key):
            raise ConfigError("人工判定项 key 不合法：%s" % key)
        v = str(verdict or "").strip()
        if v not in ("auto", "pass", "fail"):
            v = "pass" if ok else "auto"
        ok = (v == "pass")
        d = self.manual()
        if not d.get("ok"):
            raise ConfigError(d.get("error") or "manual.json 不可用")
        items = d["items"]
        at = time.strftime("%Y-%m-%d %H:%M:%S")
        hit = False
        for it in items:
            if it["key"] == key:
                it["ok"] = bool(ok)
                it["verdict"] = v
                it["at"] = at
                if label:
                    it["label"] = str(label)[:80]
                hit = True
        if not hit:
            items.append({"key": key, "label": str(label or key)[:80], "ok": bool(ok),
                          "verdict": v, "note": "", "at": at})
        data = {"schema": 2, "updated": at, "items": items}
        MANUAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        if MANUAL_PATH.exists():
            shutil.copy2(MANUAL_PATH, MANUAL_PATH.with_name(
                MANUAL_PATH.name + "." + time.strftime("%Y%m%d-%H%M%S") + ".bak"))
        tmp = MANUAL_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        json.loads(tmp.read_text(encoding="utf-8"))
        os.replace(tmp, MANUAL_PATH)
        return {"ok": True, "items": items, "map": {i["key"]: i["ok"] for i in items},
                "updated": data["updated"]}

    # ---------- 详细说明：读 / 写 ----------
    def _board_path(self, board):
        board = str(board or "").strip()
        if board not in ("goals", "short", "daiban"):
            raise ConfigError("board 只能是 goals / short / daiban")
        key = {"short": "short_tasks", "goals": "goals", "daiban": "daiban"}[board]
        label = {"short": "短期任务", "goals": "长期任务", "daiban": "待办总表"}[board]
        spec = self.cfg.get(key)
        if not spec:
            raise ConfigError("未配置%s文件" % label)
        p = self._cfg_path(spec)
        if not p.is_file():
            raise ConfigError("任务文件不存在：%s" % p)
        return board, p

    def detail(self, board, item_id):
        board, p = self._board_path(board)
        item_id = str(item_id or "").strip()
        d = detail_of(load_details(p), item_id)
        return {"ok": True, "board": board, "id": item_id, "detail": d,
                "path": str(detail_path_of(p)),
                "display": self._tilde(detail_path_of(p)),
                "has_detail": bool(d["req"] or d["prompt"])}

    def save_detail(self, board, item_id, req, prompt, by=None):
        board, p = self._board_path(board)
        item_id = str(item_id or "").strip()
        if not re.match(r"^[A-Za-z]\d{1,3}$", item_id):
            raise ConfigError("编号不合法：%s" % item_id)
        dp = detail_path_of(p)
        data = {"version": 1, "items": {}}
        if dp.is_file():
            try:
                data = json.loads(dp.read_text(encoding="utf-8-sig"))
            except Exception:  # noqa: BLE001
                data = {"version": 1, "items": {}}
            if not isinstance(data.get("items"), dict):
                data["items"] = {}
        data["items"][item_id] = {
            "req": str(req or "")[:20000],
            "prompt": str(prompt or "")[:20000],
            "by": str(by or "UI")[:40],
            "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        dp.parent.mkdir(parents=True, exist_ok=True)
        if dp.exists():
            shutil.copy2(dp, dp.with_name(dp.name + "." + time.strftime("%Y%m%d-%H%M%S") + ".bak"))
        tmp = dp.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        json.loads(tmp.read_text(encoding="utf-8"))
        os.replace(tmp, dp)
        return {"ok": True, "board": board, "id": item_id,
                "detail": data["items"][item_id], "display": self._tilde(dp)}


    # ---------- 任务新增 / 删除（S3 收口：界面写回看板，只迁不删） ----------
    @staticmethod
    def _progress_of(raw):
        try:
            n = int(str(raw).strip().rstrip("%"))
        except (TypeError, ValueError):
            return 0
        return 0 if n < 0 else (100 if n > 100 else n)

    def add_task(self, payload):
        board, p = self._board_path(payload.get("board"))
        if board == "daiban":
            raise ConfigError("待办总表是 8 列表格，不支持在此新增；请走 daiban.py")
        title = str(payload.get("目标") or "").strip()
        if not title:
            raise ConfigError("目标不能为空")
        if "\n" in title or "：" in title[:2]:
            raise ConfigError("目标请写成一行，不要换行")
        prefix = "S" if board == "short" else "G"
        text = p.read_text(encoding="utf-8-sig")
        items = parse_goals(text)
        nums = []
        for it in items:
            iid = str(it.get("id", "")).upper()
            m = re.match(r"^[A-Za-z](\d+)$", iid)
            if m and iid.startswith(prefix):
                nums.append(int(m.group(1)))
        nid = prefix + str((max(nums) + 1) if nums else 1)
        field = lambda name, dft: str(payload.get(name) or dft).strip() or dft
        block = "\n".join([
            "", "[%s]" % nid,
            "目标：%s" % title,
            "阶段：%s" % field("阶段", "本周"),
            "状态：%s" % field("状态", "进行中"),
            "进度：%d" % self._progress_of(payload.get("进度")),
            "关联项目：%s" % field("关联项目", "—"),
            "关联文件：%s" % field("关联文件", "—"),
            "下一步：%s" % field("下一步", "—"),
            "证据：（界面新增 %s）" % time.strftime("%Y-%m-%d %H:%M"),
            "复核：%s" % time.strftime("%Y-%m-%d"),
        ])
        shutil.copy2(p, p.with_name(p.name + "." + time.strftime("%Y%m%d-%H%M%S") + ".bak"))
        new_text = text.rstrip("\n") + "\n" + block + "\n"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(new_text, encoding="utf-8")
        back = parse_goals(tmp.read_text(encoding="utf-8"))
        if nid not in [str(i.get("id", "")).upper() for i in back]:
            tmp.unlink(missing_ok=True)
            raise ConfigError("写回校验失败：新编号 %s 未出现在重读结果里" % nid)
        os.replace(tmp, p)
        return {"ok": True, "board": board, "id": nid, "display": self._tilde(p)}

    def delete_task(self, payload):
        board, p = self._board_path(payload.get("board"))
        if board == "daiban":
            raise ConfigError("待办总表走 daiban.py 管理，不支持在此删除")
        item_id = str(payload.get("id") or "").strip().upper()
        if not re.match(r"^[A-Za-z]\d{1,3}$", item_id):
            raise ConfigError("编号不合法：%s" % item_id)
        text = p.read_text(encoding="utf-8-sig")
        pat = re.compile(
            r"(?ms)^\[" + item_id + r"\]\s*\n.*?(?=^\[[A-Za-z]\d+\]\s*\n|\Z)")
        m = pat.search(text)
        if not m:
            raise ConfigError("没有编号 %s 这一块" % item_id)
        block = m.group(0).rstrip("\n")
        shutil.copy2(p, p.with_name(p.name + "." + time.strftime("%Y%m%d-%H%M%S") + ".bak"))
        # 只迁不删：块搬进同目录 <看板>.archive.txt，带归档行可回查（与 xtgl_clean 同一口径）
        arch = p.with_name(p.stem + ".archive.txt")
        stamp = time.strftime("%Y-%m-%d %H:%M")
        with arch.open("a", encoding="utf-8") as f:
            f.write("\n" + block + "\n归档：%s ｜ 原编号 %s（界面删除）\n" % (stamp, item_id))
        new_text = text[:m.start()] + text[m.end():]
        tmp = p.with_suffix(".tmp")
        tmp.write_text(new_text, encoding="utf-8")
        back_ids = [str(i.get("id", "")).upper() for i in parse_goals(tmp.read_text(encoding="utf-8"))]
        if item_id in back_ids:
            tmp.unlink(missing_ok=True)
            raise ConfigError("删除校验失败：%s 仍在重读结果里" % item_id)
        os.replace(tmp, p)
        return {"ok": True, "board": board, "id": item_id,
                "archive": self._tilde(arch)}

    # ---------- 环境自检 ----------

    def env_report(self, root=None):
        target = _as_path(root, HERE) if root else self.root
        checks = []

        def add(name, ok, detail, warn=False):
            checks.append({"name": name, "ok": bool(ok), "detail": detail, "warn": warn})

        add("Python", sys.version_info >= (3, 8), sys.version.split()[0])
        if target is None:
            add("项目目录", False, "未指定")
            return {"root": "", "ok": False, "checks": checks}
        try:
            exists = target.is_dir()
        except OSError:
            exists = False
        add("项目目录", exists, str(target))
        if not exists:
            return {"root": str(target), "ok": False, "checks": checks}
        meta = target / "00_meta" / "meta.json"
        ok = meta.is_file()
        detail = ""
        if ok:
            try:
                m = _read_json(meta)
                detail = "v%s（%s）" % (m.get("version", "?"), m.get("name", ""))
            except Exception as e:  # noqa: BLE001
                ok, detail = False, "解析失败：%s" % e
        add("00_meta/meta.json", ok, detail or str(meta))
        eng = self.cfg["engine"]
        ecwd = target / eng["cwd"]
        exe = eng["cmd"][0] if eng["cmd"] else ""
        engine_ok = ecwd.is_dir() and (target / eng["cwd"] / (eng["cmd"][1] if len(eng["cmd"]) > 1 else "")).is_file()
        add("引擎", engine_ok, "%s / %s" % (eng["cwd"], " ".join(eng["cmd"])),
            warn=not engine_ok)
        for layer in LAYERS:
            spec = self.cfg["rules"].get(layer, {})
            if not spec.get("enabled") or not spec.get("dir"):
                add("规则层·" + LAYER_LABEL[layer], True, "未启用", warn=True)
                continue
            d = target / spec["dir"]
            add("规则层·" + LAYER_LABEL[layer], d.is_dir(),
                "%s（%d 个 json）" % (spec["dir"], len(list(d.glob('*.json'))) if d.is_dir() else 0))
        try:
            writable = os.access(str(target), os.W_OK)
        except OSError:
            writable = False
        add("项目可写", writable, "向导建任务需要写权限", warn=True)
        ok_all = all(c["ok"] for c in checks if not c["warn"])
        return {"root": str(target), "ok": ok_all, "checks": checks}

    # ---------- 写入：配置 / 骨架 / 任务 ----------
    def save_config(self, payload: dict):
        root_raw = str(payload.get("root") or "").strip()
        if not root_raw:
            raise ConfigError("请先选择项目目录")
        root = _as_path(root_raw, HERE)
        reason = validate_root(root)
        if reason:
            raise ConfigError(reason)

        rules = payload.get("rules") or {}
        rule_cfg = {}
        for name in LAYERS:
            spec = rules.get(name) or {}
            d = str(spec.get("dir") or "").strip()
            rule_cfg[name] = {"dir": d, "enabled": bool(d) if spec.get("enabled") is None
                              else bool(spec.get("enabled"))}
        if not rule_cfg["default"]["dir"]:
            rule_cfg["default"] = {"dir": "rules", "enabled": True}

        # 项目根在自身树内（root/20_view/web == HERE）时记空串：整体搬家仍然可用
        try:
            inside = (root / "20_view" / "web").resolve() == HERE
        except OSError:
            inside = False
        cfg = {
            "schema": SCHEMA,
            "title": payload.get("title") or self.cfg.get("title") or "Bumao XTGL",
            "subtitle": payload.get("subtitle") or self.cfg.get("subtitle") or "",
            "project_root": "" if inside else str(root),
            "port": int(payload.get("port") or self.cfg.get("port") or 8804),
            "engine": {
                "cwd": (payload.get("engine") or {}).get("cwd") or self.cfg["engine"]["cwd"],
                "cmd": (payload.get("engine") or {}).get("cmd") or self.cfg["engine"]["cmd"],
                "timeout": int((payload.get("engine") or {}).get("timeout") or self.cfg["engine"]["timeout"]),
            },
            "rules": rule_cfg,
        }
        text = json.dumps(cfg, ensure_ascii=False, indent=2) + "\n"
        if self.config_path.exists():
            bak = self.config_path.with_name(
                self.config_path.name + "." + time.strftime("%Y%m%d-%H%M%S") + ".bak")
            shutil.copy2(self.config_path, bak)
        tmp = self.config_path.with_suffix(self.config_path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        json.loads(tmp.read_text(encoding="utf-8"))  # 回读校验
        os.replace(tmp, self.config_path)
        self.cfg, self.config_error = load_config(self.config_path)
        self.root, self.root_source, _ = resolve_root(self.cfg)
        self.root_error = validate_root(self.root)
        return {"ok": True, "config": str(self.config_path), "root": str(self.root),
                "project_root": cfg["project_root"]}

    def scaffold(self, payload: dict):
        root_raw = str(payload.get("root") or "").strip()
        if not root_raw:
            raise ConfigError("请先选择项目目录")
        root = _as_path(root_raw, HERE)
        if root.exists() and any(root.iterdir()) and not (root / "00_meta").exists():
            raise ConfigError("目录非空且不是 XTGL 项目，换一个空目录或已有项目")
        created = []
        root.mkdir(parents=True, exist_ok=True)
        meta_dir = root / "00_meta"
        meta_dir.mkdir(exist_ok=True)
        meta = meta_dir / "meta.json"
        if not meta.exists():
            name = str(payload.get("name") or root.name)
            data = {"schema": 1, "name": name, "short": "", "version": "0.1",
                    "effective": time.strftime("%Y-%m-%d"), "nature": "本地工作区",
                    "level": "普通"}
            meta.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            created.append("00_meta/meta.json")
        rules_dir = root / "rules"
        rules_dir.mkdir(exist_ok=True)
        sample = rules_dir / "r01_default.json"
        if not sample.exists():
            data = {"ch": 1, "file": "r01_default.json", "chapter_title": "1. 默认规则",
                    "pre": ["这是首次启动生成的示例规则，可直接改或删除。"],
                    "clauses": [
                        {"id": "1.1", "root": "1.1", "title": "1.1 改动前先备份",
                         "body": ["任何覆盖写之前，同目录留一份带时间戳的 .bak。"]},
                        {"id": "1.2", "root": "1.2", "title": "1.2 一件活一条留档",
                         "body": ["每个任务目录至少有一份留档，写清目标、产物、结论。"]},
                    ]}
            sample.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            created.append("rules/r01_default.json")
        for d in ("10_rac", "30_taizhang", "40_renwu"):
            p = root / d
            if not p.exists():
                p.mkdir()
                created.append(d + "/")
        return {"ok": True, "root": str(root), "created": created}

    def create_task(self, payload: dict):
        root = _as_path(payload.get("root") or self.root, HERE)
        reason = validate_root(root)
        if reason:
            raise ConfigError(reason)
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ConfigError("任务名称不能为空")
        safe = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", name).strip(" .")
        if not safe:
            raise ConfigError("任务名称不合法")
        goal = str(payload.get("goal") or "").strip() or safe
        d = root / "40_renwu" / safe
        d.mkdir(parents=True, exist_ok=True)
        f = d / "benci_gongcheng.txt"
        if f.exists():
            return {"ok": True, "existed": True, "path": str(f)}
        today = time.strftime("%Y-%m-%d")
        text = "\n".join([
            "任务：" + goal,
            "日期：" + today,
            "执行者：（请填写：模型名＋客户端名）",
            "状态：进行中",
            "任务目标：" + goal,
            "前序：无",
            "关键改动：",
            "- 任务已创建，正文待补",
            "未完成：",
            "- 待办",
            "溯源关键词：" + safe,
            "",
            "================================================================",
            "（正文明细：目标 / 过程 / 产物 / 结论）",
            "================================================================",
            "【索引尾开始】",
            "- 入口：本文件",
            "- 关联：（待补）",
            "【索引尾结束】",
            "",
        ])
        f.write_text(text, encoding="utf-8")
        return {"ok": True, "existed": False, "path": str(f)}

    # ---------- AI 运维接入 ----------
    def _ai_pick(self):
        """AI 配置件来路：环境变量 > 端配置 ai_config > 用户目录默认，取第一个真实存在的。

        配了却不存在时不偷偷退回默认件——那样页面会把「读了另一件」
        说成「读了你配的那件」，正是这类错位最难查的地方。
        """
        base = self.root or HERE.parent.parent
        env = os.environ.get("XTGL_AI_CONFIG", "").strip()
        conf = str(self.cfg.get("ai_config") or "").strip()
        cands = []
        if env:
            cands.append((_as_path(env, HERE), "环境变量 XTGL_AI_CONFIG"))
        if conf:
            cands.append((_as_path(conf, base), "web_config.json 的 ai_config"))
        for p, src in cands:
            if p.is_file():
                return p, src, True
        if AI_CONFIG_DEFAULT.is_file():
            return AI_CONFIG_DEFAULT, "默认落点（用户目录 .xtgl）", True
        if cands:
            return cands[0][0], cands[0][1] + "（该件不存在，保存会写到这里）", False
        return AI_CONFIG_DEFAULT, "默认落点（用户目录 .xtgl，尚未创建）", False

    def _ai_path(self):
        return self._ai_pick()[0]

    def _ai_defaults(self):
        return {"schema": 1, "enabled": False, "presetId": "local_ollama",
                "baseUrl": AI_PRESETS[0]["baseUrl"], "model": AI_PRESETS[0]["model"],
                "apiKey": "", "timeoutSec": 120}

    def _ai_load(self):
        p = self._ai_path()
        doc = self._ai_defaults()
        if p.is_file():
            try:
                raw = _read_json(p)
                if isinstance(raw, dict):
                    doc.update(raw)
            except Exception as e:  # noqa: BLE001
                return doc, "AI 配置件存在但解析失败：%s" % e
        return doc, ""

    def _ai_validate(self, doc):
        doc["enabled"] = bool(doc.get("enabled"))
        try:
            timeout = int(doc.get("timeoutSec") or 120)
        except (TypeError, ValueError):
            timeout = 120
        doc["timeoutSec"] = max(1, min(600, timeout))
        base = str(doc.get("baseUrl") or "").strip().rstrip("/")
        doc["baseUrl"] = base
        if base:
            try:
                parsed = urllib.parse.urlparse(base)
            except ValueError:
                parsed = None
            if not parsed or parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ConfigError("AI baseUrl 必须是 http/https 地址")
        doc["model"] = str(doc.get("model") or "").strip()
        doc["apiKey"] = str(doc.get("apiKey") or "")
        doc["presetId"] = str(doc.get("presetId") or "custom")
        if doc["enabled"] and (not base or not doc["model"]):
            raise ConfigError("启用 AI 前必须先填 baseUrl 与 model")
        return doc

    def ai_config(self):
        doc, err = self._ai_load()
        p, src, found = self._ai_pick()
        return {"ok": not err, "error": err, "path": str(p),
                "configSource": src, "fileFound": found,
                "enabled": bool(doc.get("enabled")), "presetId": doc.get("presetId"),
                "baseUrl": doc.get("baseUrl"), "model": doc.get("model"),
                "apiKey": _ai_public_key(doc.get("apiKey")), "hasKey": bool(doc.get("apiKey")),
                "timeoutSec": doc.get("timeoutSec"), "presets": list(AI_PRESETS)}

    def save_ai_config(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        doc, err = self._ai_load()
        if err:
            raise ConfigError(err)
        for key in ("enabled", "presetId", "baseUrl", "model", "timeoutSec"):
            if key in payload:
                doc[key] = payload[key]
        # 页面永远不回显明文；只有用户真的填了新密钥才覆盖。
        supplied = payload.get("apiKey")
        if supplied is not None and not str(supplied).startswith("已配置"):
            doc["apiKey"] = str(supplied)
        doc = self._ai_validate(doc)
        doc = {"schema": 1, "note": "AI 诊断配置。apiKey 只存在本机此件，不进源码或导出。",
               "enabled": doc["enabled"], "presetId": doc["presetId"], "baseUrl": doc["baseUrl"],
               "model": doc["model"], "apiKey": doc["apiKey"], "timeoutSec": doc["timeoutSec"]}
        p = self._ai_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.is_file():
            bak = "%s.%s.bak" % (p, time.strftime("%y%m%d-%H%M%S"))
            shutil.copyfile(p, bak)
            if Path(bak).read_bytes() != p.read_bytes():
                raise ConfigError("AI 配置改前件回验失败")
        fd, tmp = tempfile.mkstemp(prefix=p.name + ".", dir=str(p.parent))
        os.close(fd)
        try:
            Path(tmp).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
            back = json.loads(Path(tmp).read_text(encoding="utf-8"))
            if back != doc:
                raise ConfigError("AI 配置写后回读不一致")
            os.replace(tmp, p)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        result = self.ai_config()
        result["saved"] = True
        return result

    def set_ai_enabled(self, enabled):
        """只翻「启用」一个键，其余原样留着——页面上的开关不该重写整件配置。"""
        return self.save_ai_config({"enabled": bool(enabled)})

    def _ai_request(self, config, messages):
        config = self._ai_validate(dict(config))
        if not config.get("enabled"):
            raise ConfigError("AI 未启用")
        url = config["baseUrl"].rstrip("/") + "/chat/completions"
        body = json.dumps({"model": config["model"], "messages": messages,
                           "temperature": 0.1}, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if config.get("apiKey"):
            headers["Authorization"] = "Bearer " + config["apiKey"]
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=config["timeoutSec"]) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "ignore")[:500]
            except Exception:
                pass
            raise ConfigError("AI 返回 HTTP %s：%s" % (e.code, detail or e.reason))
        except urllib.error.URLError as e:
            raise ConfigError("AI 网络不可达：%s" % (e.reason,))
        except TimeoutError:
            raise ConfigError("AI 请求超时（%d 秒）" % config["timeoutSec"])
        except json.JSONDecodeError as e:
            raise ConfigError("AI 响应不是 JSON：%s" % e)
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ConfigError("AI 响应缺少 choices[0].message.content：%s" % str(data)[:300])
        return str(text), data

    def ai_probe(self, base=None):
        config = self._ai_load()[0]
        base = str(base or config.get("baseUrl") or "").strip()
        if not base:
            raise ConfigError("未配置 baseUrl，无法探测")
        parsed = urllib.parse.urlparse(base)
        if not parsed or parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ConfigError("baseUrl 必须是 http/https 地址")
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            with socket.create_connection((host, port), timeout=2):
                return {"ok": True, "host": host, "port": port, "conclusion": "TCP 可达"}
        except OSError as e:
            return {"ok": False, "host": host, "port": port, "error": str(e)}

    def ai_test(self):
        doc, err = self._ai_load()
        if err:
            return {"ok": False, "error": err}
        probe = self.ai_probe(doc.get("baseUrl"))
        if not probe.get("ok"):
            return {"ok": False, "probe": probe, "error": probe.get("error") or "端口不可达"}
        try:
            text, raw = self._ai_request(doc, [{"role": "user", "content": "只回复：连接正常"}])
            return {"ok": True, "probe": probe, "reply": text.strip(),
                    "modelUsed": raw.get("model") or doc.get("model")}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "probe": probe, "error": str(e)}

    def ai_diagnose(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        doc, err = self._ai_load()
        if err:
            return {"ok": False, "error": err}
        focus = str(payload.get("focus") or "总体")
        facts = {"defects": self.defects(), "tasks": self.tasks(),
                 "manual": self.manual(), "clients": self.clients(self.logs(limit=500))}
        prompt = ("你是 XTGL 系统诊断助手。请按「结论／证据／下一步」诊断，只依据下面 JSON，不编造路径或状态。\n"
                  "关注面：%s\n%s" % (focus, json.dumps(facts, ensure_ascii=False)[:30000]))
        try:
            text, raw = self._ai_request(doc, [
                {"role": "system", "content": "用简体中文，短直答，指出无法判断时必须明说。"},
                {"role": "user", "content": prompt}])
            report = ("# XTGL AI 诊断报告\n\n- 时间：%s\n- 端点：%s\n- 模型：%s\n- 关注面：%s\n\n"
                      "## 结论\n\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), doc.get("baseUrl"),
                                            raw.get("model") or doc.get("model"), focus, text.strip()))
            return {"ok": True, "report": report, "reply": text, "modelUsed": raw.get("model")}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e), "prompt": prompt}

    def ai_report_export(self):
        got = self.ai_diagnose({})
        if not got.get("ok"):
            raise ConfigError(got.get("error") or "AI 诊断失败")
        return got["report"]

    # ---------- 设置面 / 未处理面 ----------
    _ANOM_SKIP = {"build", "dist", "node_modules", ".git", ".dart_tool", ".idea",
                  "__pycache__", "ev", "logs", "coverage", ".venv", "venv", "guidang"}
    _ANOM_COPY = re.compile(r"(副本|拷贝|copy|Copy|COPY|最终版|最新版|未命名|\(1\)|（1）|_old|_旧|备份)")
    _ANOM_TEMP = re.compile(r"^(temp|tmp|新建文件夹|未命名文件夹|output|outputs|导出|临时|test|测试)$", re.I)

    # ---------- 功能包（三端同一接口，本端只读） ----------
    def _cfg_caps(self):
        """web_config 里声明的能力 id，两种历史写法都认。"""
        raw = self.cfg.get("capabilities")
        if isinstance(raw, dict):
            return sorted([str(k) for k, v in raw.items() if v])
        return sorted(set([str(x) for x in (raw or []) if str(x).strip()]))

    def feature_packs(self):
        """扫 00_meta/feature_packs/*.json。只报在位与是否启用，不改任何文件。"""
        out = {"ok": True, "dir": "", "list": [], "enabled": [], "added": [], "errors": []}
        if not self.root:
            out["errors"].append("无项目根")
            return out
        d = self.root / "00_meta" / "feature_packs"
        out["dir"] = str(d)
        if not d.is_dir():
            out["errors"].append("未建功能包目录（不影响启动）")
            return out
        ed = str(self.cfg.get("product_edition") or "").strip().lower()
        base = set(self._cfg_caps())
        for f in sorted(d.glob("*.json")):
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                out["errors"].append("%s 解析失败：%s" % (f.name, e))
                continue
            pid = str(doc.get("id") or f.stem)
            caps = [str(x) for x in (doc.get("capabilities") or []) if str(x).strip()]
            ap = [str(x).strip().lower() for x in (doc.get("applies_to") or []) if str(x).strip()]
            item = {"id": pid, "name": doc.get("name") or pid, "name_en": doc.get("name_en") or "",
                    "enabled": bool(doc.get("enabled")), "capabilities": caps,
                    "applies_to": ap, "file": f.name, "note": doc.get("note") or "",
                    "skipped": ""}
            if item["enabled"] and ap and ed and ed not in ap:
                item["skipped"] = "applies_to 不含本端"
                item["enabled"] = False
            out["list"].append(item)
            if item["enabled"]:
                out["enabled"].append(pid)
                for x in caps:
                    if x not in base:
                        base.add(x)
                        out["added"].append(x)
        return out

    def capability_ids(self):
        """本端实际打开的能力＝配置里声明的 ＋ 已启用功能包带来的。"""
        ids = self._cfg_caps()
        for x in (self.feature_packs().get("added") or []):
            if x not in ids:
                ids.append(x)
        return ids

    def packages_view(self):
        """包加载情况：规则包目录只报在位，功能包报逐项启用结果。"""
        rl = {"dir": "", "exists": False, "packs": []}
        if self.root:
            d = self.root / "00_meta" / "rules_library" / "packs"
            rl["dir"] = str(d)
            rl["exists"] = d.is_dir()
            if rl["exists"]:
                for f in sorted(d.glob("*.json")):
                    try:
                        doc = json.loads(f.read_text(encoding="utf-8"))
                        rl["packs"].append({"id": doc.get("id") or f.stem,
                                            "name": doc.get("name") or f.stem,
                                            "enabled": bool(doc.get("enabled")),
                                            "file": f.name})
                    except Exception as e:  # noqa: BLE001
                        rl["packs"].append({"id": f.stem, "file": f.name, "error": str(e)})
        return {"ok": True, "feature": self.feature_packs(), "rules_library": rl}

    def settings_view(self):
        """设置面：本端现在用什么，逐项现读。密钥不回流感值，只说配没配。"""
        eng = self.cfg.get("engine") or {}
        # capabilities 历史上两种写法都存在：清单（打开即列出）与字典（键→真假）。
        # 功能包（00_meta/feature_packs）里 enabled=true 的能力在运行时并入，不写回配置。
        on = self.capability_ids()
        total = len(on)
        ai_p, ai_src, ai_found = self._ai_pick()
        rules_cfg = self.cfg.get("rules") or {}
        return {
            "ok": True,
            "edition": str(self.cfg.get("product_edition") or ""),
            "title": self.cfg.get("title") or "",
            "core_version": CORE_VERSION,
            "schema": self.cfg.get("schema"),
            "python": sys.version.split()[0],
            "config_path": str(self.config_path),
            "config_error": self.config_error or "",
            "root": str(self.root) if self.root else "",
            "root_source": self.root_source or "",
            "root_error": self.root_error or "",
            "port": self.cfg.get("port"),
            "check_cmd": " ".join([str(x) for x in (eng.get("cmd") or [])]),
            "check_cwd": eng.get("cwd") or "",
            "check_timeout": eng.get("timeout"),
            "capabilities_on": len(on),
            "capabilities_total": total,
            "capabilities_on_ids": on,
            "layers": [{"layer": k, "label": LAYER_LABEL[k],
                        "enabled": bool((rules_cfg.get(k) or {}).get("enabled")),
                        "dir": str((rules_cfg.get(k) or {}).get("dir") or "")}
                       for k in LAYERS],
            "ai_path": str(ai_p),
            "ai_source": ai_src,
            "ai_found": ai_found,
            "endpoints": {"read": ["/api/overview", "/api/env", "/api/clauses", "/api/doc",
                                   "/api/tasks", "/api/modules", "/api/goals", "/api/detail",
                                   "/api/manual", "/api/snapshot", "/api/config",
                                   "/api/anomaly", "/api/ai/config", "/api/ai/probe",
                                   "/api/ai/export", "/api/goals/export",
                                   "/api/projects", "/api/renwu", "/api/metrics",
                                   "/api/oss", "/api/jieru", "/api/paths",
                                   "/api/archive", "/api/logdays", "/api/logday",
                                   "/api/recent", "/api/export", "/api/defects",
                                   "/api/health", "/api/health/rules",
                                   "/api/access", "/api/search", "/api/jieru/runs",
                                   "/api/gates"],
                          "write": ["/api/setup/save", "/api/setup/scaffold", "/api/setup/task",
                                    "/api/setup/pick", "/api/manual", "/api/detail",
                                    "/api/task/add", "/api/task/delete", "/api/ai/config",
                                    "/api/ai/test", "/api/ai/diagnose", "/api/ai/enable",
                                    "/api/anomaly/scan", "/api/project/status",
                                    "/api/task/status", "/api/task/stub",
                                    "/api/health/rules", "/api/health/computer",
                                    "/api/export/save", "/api/oss/check"]},
        }

    # ==================== 项目面（11.56 基线 + 11.58 覆盖层） ====================
    # 档位名/百分比清单自带在 gongcheng_qingdan.json 里；这两份常量只作读不到清单时的兜底，
    # 与冻结件 zhuangtai.dart 的 stageNames/stagePct 同值，不另起一套。
    STAGE_NAMES = {"S0": "立项", "S1": "在研", "S2": "可运行", "S3": "已验收", "S4": "已归档"}
    STAGE_PCT = {"S0": 10, "S1": 35, "S2": 65, "S3": 90, "S4": 100}
    STAGE_CRITERIA = {
        "S0": "有项目记录或任务目录，且写明目标/边界/交付物",
        "S1": "有源码或材料，但没有能直接打开的成品",
        "S2": "成品存在且非空（exe/网页/docx/成片），能打开",
        "S3": "用户当场认可，或在这里自己勾「已验收」",
        "S4": "整目录已移入 90_lishi，原位不再有实体",
    }
    STUB_MAX_FILES = 40

    @staticmethod
    def _norm_key(p):
        """覆盖层键归一：手写 JSON 常用正斜杠，比对用反斜杠——不统一就「写了却不生效」。"""
        return str(p or "").replace("/", "\\")

    def _proj_cfg(self):
        spec = self.cfg.get("projects")
        if not isinstance(spec, dict) or not (spec.get("list_file") or spec.get("dirs")):
            raise ConfigError("未配置项目面（web_config.json 的 projects：list_file／state_file／dirs）")
        return spec

    def _proj_path(self, cfg, key, required_msg):
        f = cfg.get(key) or ""
        if not f:
            raise ConfigError(required_msg)
        return self._cfg_path(f)

    def _overlay_read(self, cfg):
        """读 11.58 覆盖层。坏了按「无覆盖」降级并把原因带出去，不静默吞（11.58(6)）。"""
        try:
            sp = self._proj_path(cfg, "state_file",
                                 "未配置状态覆盖层（web_config.json 的 projects.state_file）")
        except ConfigError as e:
            return {}, {}, "", str(e)
        disp = self._tilde(sp)
        if not sp.is_file():
            return {}, {}, disp, ""
        try:
            doc = json.loads(sp.read_text(encoding="utf-8-sig"))
        except Exception as e:  # noqa: BLE001
            return {}, {}, disp, "覆盖层读取失败，本屏按「无覆盖」显示：%s" % e
        if not isinstance(doc, dict):
            return {}, {}, disp, "覆盖层根节点不是对象，本屏按「无覆盖」显示"
        tasks = {self._norm_key(k): v for k, v in (doc.get("tasks") or {}).items()
                 if isinstance(v, dict)}
        projs = {str(k): v for k, v in (doc.get("projects") or {}).items()
                 if isinstance(v, dict)}
        return tasks, projs, disp, ""

    def _overlay_write(self, cfg, tasks, projs):
        """原子写覆盖层：同目录 .bak → .tmp → 回读对数 → os.replace。

        直接覆写一旦中断就是半截 JSON，下次读回来静默降级成「无覆盖」，
        等于用户亲手勾的结果全丢——所以回读条数不符就弃件报错，不留坏档。
        """
        sp = self._proj_path(cfg, "state_file",
                             "未配置状态覆盖层（web_config.json 的 projects.state_file）")
        sp.parent.mkdir(parents=True, exist_ok=True)
        doc = {"schema": 1,
               "note": ("状态覆盖层（准则 11.58）：这里写的是用户亲自勾的结果，显示时压过系统基线。"
                        "tasks 的键 = 留档 TXT 绝对路径；projects 的键 = 项目缩写。"
                        "清掉某个键即恢复系统判定。"),
               "tasks": tasks, "projects": projs}
        text = json.dumps(doc, ensure_ascii=False, indent=2)
        if sp.is_file():
            shutil.copy2(sp, "%s.%s.bak" % (sp, time.strftime("%y%m%d-%H%M")))
        fd, tmp = tempfile.mkstemp(prefix=sp.name + ".", dir=str(sp.parent))
        os.close(fd)
        try:
            with open(tmp, "wb") as f:
                f.write(text.encode("utf-8"))
            back = json.loads(open(tmp, "rb").read().decode("utf-8"))
            bt = len((back.get("tasks") or {}))
            bp = len((back.get("projects") or {}))
            if bt != len(tasks) or bp != len(projs):
                raise ConfigError("覆盖层写入校验失败：期望 %d/%d，回读 %d/%d"
                                  % (len(tasks), len(projs), bt, bp))
            os.replace(tmp, sp)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        return sp

    def _artifact_ok(self, p):
        try:
            f = self._cfg_path(p) if not os.path.isabs(str(p)) else Path(str(p))
            return f.is_file() and f.stat().st_size > 0, f
        except Exception:  # noqa: BLE001
            return False, None

    def _baseline_stage(self, root_ok, archive_ok, artifacts, material, record):
        """与 zhuangtai.dart baselineStage 同序：S4 → S2 → S1 → S0，不看主观。"""
        if not root_ok and archive_ok:
            return "S4"
        if artifacts and all(a["ok"] for a in artifacts):
            return "S2"
        if material and os.path.isdir(str(material)):
            return "S1"
        if record and os.path.isfile(str(record)):
            return "S0"
        return "S0"

    def projects(self):
        cfg = self._proj_cfg()
        lp, sp_disp, terr = None, "", ""
        try:
            lp = self._proj_path(cfg, "list_file",
                                  "未配置项目清单（web_config.json 的 projects.list_file）")
        except ConfigError as e:
            return {"ok": False, "error": str(e), "list": [], "counts": {},
                    "state_file": sp_disp, "list_file": ""}
        tasks_ov, proj_ov, sp_disp, terr = self._overlay_read(cfg)
        try:
            doc = json.loads(lp.read_text(encoding="utf-8-sig"))
            list_err = ""
        except FileNotFoundError:
            doc, list_err = {}, "项目清单不存在：%s" % self._tilde(lp)
        except Exception as e:  # noqa: BLE001
            doc, list_err = {}, "项目清单读取失败：%s" % e
        names = (doc.get("stage_name") if isinstance(doc.get("stage_name"), dict) else {}) or {}
        pcts = (doc.get("stage_pct") if isinstance(doc.get("stage_pct"), dict) else {}) or {}
        stage_names = dict(self.STAGE_NAMES)
        stage_names.update({str(k): str(v) for k, v in names.items()})
        stage_pct = dict(self.STAGE_PCT)
        for k, v in pcts.items():
            try:
                stage_pct[str(k)] = int(v)
            except Exception:  # noqa: BLE001
                pass
        rows = []
        for raw in (doc.get("projects") or []):
            if not isinstance(raw, dict):
                continue
            abbr = str(raw.get("abbr") or "").strip()
            if not abbr:
                continue
            root = str(raw.get("root") or "")
            root_p = self._cfg_path(root) if root else None
            root_ok = bool(root_p and root_p.is_dir())
            arch = str(raw.get("archive") or "")
            arch_p = self._cfg_path(arch) if arch else None
            arch_ok = bool(arch_p and arch_p.is_dir())
            mats = []
            for m in ([raw.get("material")] if raw.get("material") else []):
                mp = self._cfg_path(m)
                mats.append({"path": str(mp), "display": self._tilde(mp), "exists": mp.is_dir()})
            arts = []
            for a in (raw.get("artifacts") or []):
                ap = self._cfg_path(a)
                ok = False
                try:
                    ok = ap.is_file() and ap.stat().st_size > 0
                except Exception:  # noqa: BLE001
                    ok = False
                arts.append({"path": str(ap), "display": self._tilde(ap), "ok": ok,
                             "bytes": (ap.stat().st_size if ok else 0)})
            rec = str(raw.get("record") or "")
            rec_p = self._cfg_path(rec) if rec else None
            rec_ok = bool(rec_p and rec_p.is_file())
            base = self._baseline_stage(root_ok, arch_ok, arts,
                                        (mats[0]["path"] if mats and mats[0]["exists"] else ""),
                                        (str(rec_p) if rec_ok else ""))
            o = proj_ov.get(abbr) or {}
            user_stage = str(o.get("stage") or "") if str(o.get("stage") or "") in stage_names else ""
            rows.append({
                "abbr": abbr, "name": str(raw.get("name") or abbr),
                "kind": str(raw.get("kind") or "软件"), "icon": str(raw.get("icon") or ""),
                "note": str(raw.get("note") or ""),
                "root": str(root_p) if root_p else "", "root_display": (self._tilde(root_p) if root_p else ""),
                "root_exists": root_ok,
                "material": mats, "artifacts": arts,
                "artifact_hit": sum(1 for a in arts if a["ok"]), "artifact_total": len(arts),
                "record": str(rec_p) if rec_p else "", "record_exists": rec_ok,
                "archive": str(arch_p) if arch_p else "", "archive_exists": arch_ok,
                "archived": (not root_ok) and arch_ok,
                "baseline_stage": base, "stage": (user_stage or base),
                "stage_name": stage_names.get(user_stage or base, ""),
                "pct": stage_pct.get(user_stage or base, 0),
                "is_manual": bool(user_stage),
                "overlay_by": str(o.get("by") or ""), "overlay_at": str(o.get("at") or ""),
                "overlay_note": str(o.get("note") or ""),
            })
        counts = {k: 0 for k in stage_names}
        for r in rows:
            counts[r["stage"]] = counts.get(r["stage"], 0) + 1
        return {"ok": True, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "list_file": str(lp), "list_display": self._tilde(lp), "list_error": list_err,
                "state_file": str(self._cfg_path(cfg["state_file"])) if cfg.get("state_file") else "",
                "state_display": sp_disp, "overlay_error": terr,
                "overlay_task_count": len(tasks_ov), "overlay_project_count": len(proj_ov),
                "stage_names": stage_names, "stage_pct": stage_pct,
                "stage_criteria": self.STAGE_CRITERIA,
                "counts": counts, "total": len(rows),
                "manual_count": sum(1 for r in rows if r["is_manual"]),
                "list": sorted(rows, key=lambda x: (-x["pct"], x["abbr"]))}

    def save_project(self, payload):
        """勾档位＝写 11.58 覆盖层；传基线档或空＝清掉覆盖回退系统判定。绝不改清单本体。"""
        payload = payload or {}
        abbr = str(payload.get("abbr") or "").strip()
        stage = str(payload.get("stage") or "").strip()
        if not abbr:
            raise ConfigError("缺参数：abbr")
        cfg = self._proj_cfg()
        d = self.projects()
        known = {r["abbr"] for r in (d.get("list") or [])}
        if abbr not in known:
            return {"ok": False, "error": "项目缩写不在清单里，不新建：%s" % abbr}
        tasks_ov, proj_ov, _disp, terr = self._overlay_read(cfg)
        if terr:
            return {"ok": False, "error": terr}
        base = next((r["baseline_stage"] for r in d["list"] if r["abbr"] == abbr), "S0")
        if not stage or stage == base:
            proj_ov.pop(abbr, None)
            action = "清除覆盖"
        else:
            if stage not in self.STAGE_NAMES:
                return {"ok": False, "error": "档位只能是 S0—S4：%s" % stage}
            proj_ov[abbr] = {"stage": stage, "by": "用户",
                             "at": time.strftime("%Y-%m-%d %H:%M"),
                             "note": str(payload.get("note") or "")}
            action = "覆盖为 %s" % stage
        sp = self._overlay_write(cfg, tasks_ov, proj_ov)
        return {"ok": True, "action": action, "abbr": abbr, "state_file": str(sp),
                "state_display": self._tilde(sp), "project": next(
                    (r for r in self.projects().get("list") or [] if r["abbr"] == abbr), None)}

    # ==================== 任务留档普查（repos.dart loadTasks / unlogged / logged） ====================
    def _renwu_roots(self):
        cfg = self.cfg.get("projects") or {}
        out = []
        for x in (cfg.get("dirs") or []):
            if not str(x).strip():
                continue
            d = self._cfg_path(x)
            out.append({"spec": str(x), "path": str(d), "display": self._tilde(d),
                        "exists": d.is_dir()})
        return out

    def _dir_files(self, d, cap=3000):
        """列目录里的文件（跳 build 等噪声），封顶 cap，超了如实标 truncated。"""
        files, n, trunc = [], 0, False
        for base, dirs, fns in os.walk(str(d)):
            dirs[:] = [x for x in dirs if x not in self._ANOM_SKIP]
            for fn in fns:
                n += 1
                if n > cap:
                    trunc = True
                    break
                files.append(Path(base) / fn)
            if trunc:
                break
        return files, n, trunc

    def _record_kind(self, name):
        if name == "xiangmu_jilu.txt":
            return "项目记录"
        if name == "benci_gongcheng.txt":
            return "本次项目"
        if name == "renwu_liudang.txt":
            return "任务留档"
        if "liudang" in name.lower():
            return "任务留档"
        return ""

    def _declared_stage(self, path):
        """只认正文明写的「完成度：S?」（11.56(9)）；没写返回空，不猜。"""
        try:
            text = Path(str(path)).read_text(encoding="utf-8-sig", errors="ignore")
        except Exception:  # noqa: BLE001
            return ""
        m = re.search(r"完成度[：:]\s*(S[0-4])", text)
        return m.group(1) if m else ""

    def _logged_detail_set(self):
        lg = self.logs(limit=100000)
        s = set()
        for r in (lg.get("list") or []):
            d = str(r.get("detail") or "").strip()
            if d:
                s.add(self._norm_key(d))
        return s, lg

    def renwu(self):
        roots = self._renwu_roots()
        if not roots:
            raise ConfigError("未配置任务留档扫描根（web_config.json 的 projects.dirs）")
        tasks_ov, _po, _sd, terr = self._overlay_read(self._proj_cfg())
        logged, lg = self._logged_detail_set()
        rows, unlogged, missing_roots = [], [], [r["display"] for r in roots if not r["exists"]]
        seen = set()
        for r in roots:
            if not r["exists"]:
                continue
            d = Path(r["path"])
            try:
                subs = sorted(x for x in d.iterdir() if x.is_dir())
            except Exception as e:  # noqa: BLE001
                unlogged.append({"name": r["display"], "path": r["path"], "files": 0,
                                 "error": "读取失败：%s" % e})
                continue
            for sub in subs:
                if sub.name in self._ANOM_SKIP:
                    continue
                files, total, trunc = self._dir_files(sub)
                recs = [(f, self._record_kind(f.name)) for f in files
                        if self._record_kind(f.name)]
                recs.sort(key=lambda x: (0 if x[1] == "本次项目" else (1 if x[1] == "任务留档" else 2),
                                         x[0].name))
                if not files:
                    continue
                key = {"name": sub.name, "path": str(sub), "root": r["display"],
                       "files": total, "truncated": trunc,
                       "bytes": sum(f.stat().st_size for f in files if f.is_file()),
                       "mtime": time.strftime("%Y-%m-%d %H:%M",
                                              time.localtime(sub.stat().st_mtime)),
                       "records": [{"file": str(p), "name": p.name, "kind": k,
                                    "bytes": p.stat().st_size,
                                    "mtime": time.strftime("%Y-%m-%d %H:%M",
                                                           time.localtime(p.stat().st_mtime)),
                                    "declared_stage": self._declared_stage(p),
                                    "manual": (tasks_ov.get(self._norm_key(p)) or {}).get("status") or "",
                                    "manual_at": (tasks_ov.get(self._norm_key(p)) or {}).get("at") or "",
                                    "logged": self._norm_key(p) in logged}
                                   for p, k in recs]}
                if key["path"] in seen:
                    continue
                seen.add(key["path"])
                rows.append(key)
                if not recs:
                    unlogged.append({"name": sub.name, "path": str(sub), "root": r["display"],
                                     "files": total, "error": ""})
        done = sum(1 for x in rows for rr in x["records"] if rr["manual"] == "完成")
        withrec = sum(1 for x in rows if x["records"])
        declared = sum(1 for x in rows for rr in x["records"] if rr["declared_stage"])
        return {"ok": True, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "roots": roots, "roots_missing": missing_roots,
                "log_index": lg.get("display") or "", "log_error": lg.get("error") or terr or "",
                "logged_count": len(logged), "overlay_task_count": len(tasks_ov),
                "counts": {"dirs": len(rows), "with_record": withrec, "without_record": len(unlogged),
                           "declared_stage": declared, "manual_done": done},
                "note": ("档位一律读正文，没写「完成度：S?」就不标；"
                         "完成只认 11.58 覆盖层里用户亲手勾的，系统不猜（11.58 基线恒为未完成）。"),
                "list": sorted(rows, key=lambda x: x["name"]),
                "unlogged": sorted(unlogged, key=lambda x: x["name"])}

    def save_task_status(self, payload):
        payload = payload or {}
        p = self._norm_key(payload.get("file") or "").strip()
        if not p:
            raise ConfigError("缺参数：file（留档 TXT 绝对路径）")
        cfg = self._proj_cfg()
        tasks_ov, proj_ov, _sd, terr = self._overlay_read(cfg)
        if terr:
            return {"ok": False, "error": terr}
        if payload.get("done"):
            if not Path(p).is_file():
                return {"ok": False, "error": "留档文件不在盘上，不写覆盖：%s" % p}
            tasks_ov[p] = {"status": "完成", "by": "用户",
                           "at": time.strftime("%Y-%m-%d %H:%M"),
                           "note": str(payload.get("note") or "")}
            action = "标完成"
        else:
            tasks_ov.pop(p, None)
            action = "清除覆盖"
        sp = self._overlay_write(cfg, tasks_ov, proj_ov)
        return {"ok": True, "action": action, "file": p, "state_file": str(sp),
                "state_display": self._tilde(sp), "task_count": len(tasks_ov)}

    def create_liudang_stub(self, payload):
        """补骨架：只列目录里真实存在的文件名 ＋「待人工补全」占位，不编造目标与结论。

        已存在 renwu_liudang.txt 就直接拒——这是「补缺」，不是重写别人的留档。
        """
        payload = payload or {}
        raw_dir = str(payload.get("dir") or "").strip()
        if not raw_dir:
            raise ConfigError("没选目录，不写")
        d = Path(raw_dir)
        # 必须是绝对路径且真实存在：Path("") 就是 "."，is_dir() 为真，
        # 上一版靠这条把 renwu_liudang.txt 写进了 web 目录自己脚下。
        if not d.is_absolute():
            raise ConfigError("只接受绝对路径，不写：%s" % raw_dir)
        if not d.is_dir():
            raise ConfigError("目录不存在，不写：%s" % d)
        target = d / "renwu_liudang.txt"
        if target.exists():
            return {"ok": False, "error": "已有留档，不覆盖：%s" % target}
        names = []
        for base, sub_dirs, fns in os.walk(str(d)):
            sub_dirs[:] = [x for x in sub_dirs if x not in self._ANOM_SKIP]
            for fn in fns:
                names.append(fn)
                if len(names) >= self.STUB_MAX_FILES:
                    break
            if len(names) >= self.STUB_MAX_FILES:
                break
        lines = ["===== 任务摘要头 =====",
                 "任务：（待补：一句话说清这个目录是干什么的）",
                 "执行者：（待补）",
                 "时间：%s（骨架由本机管理台生成）" % time.strftime("%Y-%m-%d %H:%M"),
                 "状态：（待补：S0—S4）", "",
                 "===== 正文明细 =====",
                 "一、目录里有什么（自动列名，未加任何判断）",
                 "  共 %d 个文件（最多列 %d 个）：" % (len(names), self.STUB_MAX_FILES)]
        lines += ["  · %s" % n for n in names]
        lines += ["", "二、结论（待人工补全）", "三、没做完 / 待确认（待人工补全）", "",
                  "【索引尾开始】", "", "=== 索引尾 ===", "目录：%s" % d,
                  "关联：B42（任务目录必须有留档）", "【索引尾结束】", ""]
        text = "\r\n".join(lines)
        with open(target, "wb") as f:
            f.write(text.encode("utf-8"))
        if target.read_bytes() != text.encode("utf-8"):
            raise ConfigError("骨架写入回读不符：%s" % target)
        return {"ok": True, "created": str(target), "display": self._tilde(target),
                "files_listed": len(names),
                "note": "骨架只列了真实文件名，摘要头与结论三处仍待人工补全。"}

    # ==================== 接入面 ====================
    def jieru(self):
        lg = self.logs(limit=100000)
        agg = {}
        for r in (lg.get("list") or []):
            w = client_name(r.get("who"))
            if w.startswith(NON_CLIENT_PREFIXES):
                continue
            a = agg.setdefault(w, {"rows": 0, "last": ""})
            a["rows"] += 1
            stamp = ("%s %s" % (r.get("date") or "", r.get("time") or "")).strip()
            if stamp > a["last"]:
                a["last"] = stamp
        _runs = self.jieru_runs()
        roots = self._renwu_roots()
        projects, unreg = [], []
        for r in roots:
            if not r["exists"]:
                unreg.append(r["display"])
                continue
            try:
                subs = [x for x in Path(r["path"]).iterdir()
                        if x.is_dir() and x.name not in self._ANOM_SKIP]
            except Exception:  # noqa: BLE001
                subs = []
            projects += [{"name": x.name, "root": r["display"], "path": str(x)} for x in subs]
        return {"ok": True, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "clients_source": lg.get("display") or "", "log_error": lg.get("error") or "",
                "clients": [{"name": k, "rows": v["rows"], "last": v["last"]}
                            for k, v in sorted(agg.items(), key=lambda x: -x[1]["rows"])],
                "clients_count": len(agg),
                "check_runs": _runs.get("runs") or [],
                "check_run_total": _runs.get("total_log", 0),
                "check_today": _runs.get("today_count", 0),
                "check_streak_days": _runs.get("streak_days", 0),
                "check_avg_seconds": _runs.get("avg_seconds", 0),
                "check_runs_error": _runs.get("error") or "",
                "projects": projects, "project_count": len(projects),
                "unregistered": unreg, "unregistered_count": len(unreg),
                "desktop_only": ["快捷方式（.lnk）健康检测", "已知乱放点提示 MisplacedHint",
                                 "浏览器 chrome:// 新标签页", "本机目录选择器",
                                 "开机启动项与注册表项"],
                "note": "接入与否只由日志登记证明；未登记目录如实列成缺口，不并入已接入。"}

    # ==================== 闸门状态面（三端各一行，只读各端 check 日志）====================
    def gates_all(self):
        """三端闸门状态：只读各端 check_*.log 的现成输出（PASS/FAIL 行即 nfail 与 B 编号），
        不在前端算、不另立口径；读不到就报不可用，不渲染成 0 绿 0 红。"""
        ends = ((self.cfg.get("oss") or {}).get("ends") or [])
        if not ends:
            # 开源两端没有配 oss.ends：闸门状态面按三端固定布局回退，仍只读各端自己的 web_config。
            ends = [{"abbr": "Personal", "root": "../personal"},
                    {"abbr": "Community", "root": "../community"},
                    {"abbr": "Minimal", "root": "../minimal"}]
        rows = []
        for e in ends:
            if not isinstance(e, dict):
                continue
            abbr = str(e.get("abbr") or "?")
            root = self._cfg_path(e.get("root") or ".")
            row = {"abbr": abbr, "available": False, "green": 0, "red": 0, "total": 0,
                   "red_item": [], "at": "", "src": "", "error": ""}
            spec = ""
            try:
                spec = str(json.loads((root / "20_view" / "web" / "web_config.json")
                                      .read_text(encoding="utf-8-sig")).get("check_log_dir") or "")
            except Exception as ex:  # noqa: BLE001
                row["error"] = "web_config 读取失败：%s" % ex
            d = (root / spec).resolve() if spec else None
            logs = (sorted(d.glob("check_*.log"), key=lambda p: p.stat().st_mtime)
                    if (d and d.is_dir()) else [])
            if not logs:
                row["error"] = row["error"] or "未找到 check 日志（check_log_dir 未配置或为空）"
                rows.append(row)
                continue
            p = logs[-1]
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except Exception as ex:  # noqa: BLE001
                row["error"] = "日志读取失败：%s" % ex
                rows.append(row)
                continue
            for line in txt.splitlines():
                m = re.match(r"^\s*(PASS|FAIL)\s+([A-Za-z]\d+[a-z]?)\s+(.*)$", line)
                if m:
                    code, rest = m.group(2), m.group(3).strip()
                    if rest.startswith(code):
                        rest = rest[len(code):].strip()
                    title, _, why = rest.partition("::")
                    title, why = " ".join(title.split()), " ".join(why.split())
                    if m.group(1) == "PASS":
                        row["green"] += 1
                    else:
                        row["red"] += 1
                        row["red_item"].append({"code": code, "why": why or title})
            row.update({"available": True, "total": row["green"] + row["red"],
                        "at": time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime)),
                        "src": p.name})
            rows.append(row)
        return {"ok": True, "at": time.strftime("%Y-%m-%d %H:%M:%S"), "rows": rows,
                "note": "闸门状态只读各端 check_*.log 的现成输出；红项编号取日志原文，不在前端重算。"}

    # ==================== 开源面（repos.dart loadOss ＋ 发布清单） ====================
    def oss(self):
        cfg = self.cfg.get("oss") or {}
        ends = []
        for e in (cfg.get("ends") or []):
            if not isinstance(e, dict):
                continue
            root = self._cfg_path(e.get("root") or ".")
            meta = root / "00_meta" / "meta.json"
            ver, meta_err = "无 meta", ""
            if meta.is_file():
                try:
                    ver = str(json.loads(meta.read_text(encoding="utf-8-sig")).get("version")
                              or "无版本")
                except Exception as ex:  # noqa: BLE001
                    meta_err = "meta 读取失败：%s" % ex
            eng = root / "10_rac"
            eng_dir = eng if eng.is_dir() else root
            eng_cmd = [str(x) for x in (e.get("cmd") or [])]
            abbr = str(e.get("abbr") or root.name)
            ends.append({"abbr": abbr, "label": str(e.get("label") or self.label(abbr)),
                         "root": str(root), "root_display": self._tilde(root),
                         "root_exists": root.is_dir(), "version": ver, "meta_error": meta_err,
                         "meta_file": self._tilde(meta),
                         "engine_dir": str(eng_dir), "engine_dir_is_rac": eng.is_dir(),
                         "check_cmd": " ".join(eng_cmd), "check_configured": bool(eng_cmd),
                         "mtime": (time.strftime("%Y-%m-%d %H:%M", time.localtime(root.stat().st_mtime))
                                   if root.exists() else "")})
        arts = []
        for a in (cfg.get("artifacts") or []):
            if not isinstance(a, dict):
                continue
            d = self._cfg_path(a.get("dir") or "")
            files = []
            for fn in (a.get("files") or []):
                f = d / str(fn)
                ok = f.is_file()
                files.append({"name": str(fn), "path": str(f), "exists": ok,
                              "bytes": (f.stat().st_size if ok else 0)})
            miss = [x["name"] for x in files if not x["exists"]]
            arts.append({"id": str(a.get("id") or ""), "label": str(a.get("label") or ""),
                         "dir": str(d), "dir_exists": d.is_dir(), "files": files,
                         "hit": len(files) - len(miss), "total": len(files), "missing": miss,
                         "verdict": ("空清单" if not files
                                     else ("齐全" if not miss else "有缺件"))})
        return {"ok": True, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "configured": bool(cfg), "ends": ends, "ends_count": len(ends),
                "artifacts": arts, "artifacts_count": len(arts),
                "note": ("三家版本读各家 00_meta/meta.json，跑 check 用各家 10_rac；"
                         "发布清单只报在位与否，不代下载。"),
                "error": ("" if cfg else "未配置开源面（web_config.json 的 oss：ends／artifacts）")}

    def oss_check(self, payload):
        """在指定那一端跑 check --strict：命令与 cwd 全来自配置，不在代码里写死别端入口。"""
        abbr = str((payload or {}).get("abbr") or "").strip()
        hit = next((e for e in self.oss().get("ends") or [] if e["abbr"] == abbr), None)
        if not hit:
            return {"ok": False, "error": "端不在 oss.ends 清单里：%s" % abbr}
        cfg_cmd = [x for x in str(hit["check_cmd"]).split(" ") if x]
        if not cfg_cmd:
            return {"ok": False, "error": "该端未配置 check 命令（web_config.json 的 oss.ends[].cmd）"}
        if not hit["root_exists"]:
            return {"ok": False, "error": "该端根目录不存在：%s" % hit["root_display"]}
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            p = subprocess.run(cfg_cmd, cwd=hit["engine_dir"], env=env, timeout=300,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out = p.stdout.decode("utf-8", "replace")
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "该端 check 超时（300 秒）"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": "该端 check 起不来：%s" % e}
        gates = {}
        for line in out.splitlines():
            for g in set(re.findall(r"\b([A-Z]\d{1,2})\b", line)):
                if "FAIL" in line.upper():
                    gates[g] = False
                else:
                    gates.setdefault(g, True)
        return {"ok": (p.returncode == 0), "abbr": abbr, "rc": p.returncode,
                "engine_dir": hit["engine_dir"], "cmd": " ".join(cfg_cmd),
                "gates": [{"gate": k, "pass": v} for k, v in sorted(gates.items())],
                "gates_count": len(gates), "gates_fail": sum(1 for v in gates.values() if not v),
                "output": out[-20000:],
                "note": "闸门结果按 check 真实输出解析，未跑＝无数据；界面不补「全绿」。"}

    # ==================== 指标面（stats.dart 同口径：文件 mtime 一条轴） ====================
    def _walk_stats(self, roots, cap=20000, depth=6):
        files = dirs = 0
        total_bytes = 0
        truncated = False
        walk_error = ""
        ladder = {}
        timeline = {}
        ext = {}

        def bucket(n):
            """体积分档：<1KB / KB级 / MB级 / >MB级（冻结件 stats.dart 同四档）。"""
            if n < 1024:
                return "<1 KB"
            if n < 1024 * 1024:
                return "KB 级"
            if n < 1024 * 1024 * 1024:
                return "MB 级"
            return "GB 级"

        def bump(k, v=1):
            ladder[k] = ladder.get(k, 0) + v

        for r in roots:
            d = Path(str(r))
            if not d.is_dir():
                continue
            stack = [(d, 0)]
            while stack:
                cur, lvl = stack.pop()
                try:
                    entries = list(os.scandir(str(cur)))
                except Exception as e:  # noqa: BLE001
                    walk_error = walk_error or ("%s：%s" % (self._tilde(cur), e))
                    continue
                for it in entries:
                    if files + dirs >= cap:
                        truncated = True
                        break
                    try:
                        if it.is_dir(follow_symlinks=False):
                            dirs += 1
                            if it.name not in self._ANOM_SKIP and lvl < depth:
                                stack.append((Path(it.path), lvl + 1))
                        elif it.is_file(follow_symlinks=False):
                            st = it.stat()
                            files += 1
                            total_bytes += st.st_size
                            bump(bucket(st.st_size))
                            day = time.strftime("%Y-%m-%d", time.localtime(st.st_mtime))
                            timeline[day] = timeline.get(day, 0) + 1
                            e2 = os.path.splitext(it.name)[1].lower() or "（无后缀）"
                            ext[e2] = ext.get(e2, 0) + 1
                    except Exception:  # noqa: BLE001
                        continue
                if truncated:
                    break
            if truncated:
                break
        return {"files": files, "dirs": dirs, "bytes": total_bytes,
                "truncated": truncated, "walk_error": walk_error,
                "ladder": sorted(ladder.items(), key=lambda x: -x[1]),
                "timeline": sorted(timeline.items(), key=lambda x: x[0], reverse=True)[:60],
                "ext": sorted(ext.items(), key=lambda x: -x[1])[:20]}

    def metrics(self):
        spec = self.cfg.get("metrics") or {}
        roots = [str(self._cfg_path(x)) for x in (spec.get("roots") or []) if str(x).strip()]
        walked = self._walk_stats(roots) if roots else {
            "files": 0, "dirs": 0, "bytes": 0, "truncated": False, "walk_error": "",
            "ladder": [], "timeline": [], "ext": []}
        rows = []

        def add(key, label, value, src, ok=True, note=""):
            rows.append({"key": key, "label": label,
                         "value": (value if ok else "状态未知"),
                         "state": ("真数" if ok else "状态未知"), "source": src, "note": note})

        lg = self.logs(limit=100000)
        add("log_rows", "日志登记行数", lg.get("count"), lg.get("display") or "未配置日志",
            bool(lg.get("ok")), lg.get("error") or "")
        gd = self.goals()
        add("goals", "长期任务条数", gd.get("count"), "长期目标总表",
            bool(gd.get("ok")), gd.get("error") or "")
        st = self.short_tasks()
        add("short_tasks", "短期任务条数", st.get("count"), "短期任务表",
            bool(st.get("ok")), st.get("error") or "")
        db = self.daiban()
        add("daiban", "待办总表条数", db.get("count"), "待办总表",
            bool(db.get("ok")), db.get("error") or "")
        df = self.defects()
        add("defects_open", "缺陷未闭环", df.get("open"), "缺陷台账",
            bool(df.get("configured")), df.get("error") or "")
        rl = self.rules()
        add("clauses", "生效条款数", len(rl.get("clauses") or []), "准则真身",
            not (rl.get("errors") or []), "；".join(rl.get("errors") or []))
        add("conflicts", "规则冲突数", len(rl.get("conflicts") or []), "规则对账", True, "")
        cl = self.clients(lg)
        add("clients", "已接入客户端", len(cl.get("list") or []), "日志 who 列", True, "")
        mods = self.modules()
        add("capabilities", "能力定义数", len(mods.get("modules") or []), "modules.json",
            bool(mods.get("ok")), "；".join(mods.get("errors") or []))
        pr = None
        try:
            pr = self.projects()
            add("projects", "项目清单条数", pr.get("total"), pr.get("list_display") or "",
                bool(pr.get("ok")), pr.get("error") or "")
        except ConfigError as e:
            add("projects", "项目清单条数", 0, "", False, str(e))
        rw = None
        try:
            rw = self.renwu()
            add("renwu_dirs", "任务目录数", rw["counts"]["dirs"], "projects.dirs 扫描", True, "")
            add("renwu_unlogged", "有实体无留档", rw["counts"]["without_record"], "同上",
                True, "B42 类缺口，界面必须看得见")
        except ConfigError as e:
            add("renwu_dirs", "任务目录数", 0, "", False, str(e))
        return {"ok": True, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "counts": rows, "roots": roots, "roots_missing": [],
                "files": walked["files"], "dirs": walked["dirs"], "bytes": walked["bytes"],
                "volume": [{"bucket": k, "count": v} for k, v in walked["ladder"]],
                "ext": [{"ext": k, "count": v} for k, v in walked["ext"]],
                "timeline": [{"date": k, "count": v} for k, v in walked["timeline"]],
                "truncated": walked["truncated"], "walk_error": walked["walk_error"],
                "note": "计数各归各源；遍历只跟文件 mtime 一条轴，与冻结件 stats.dart 同口径。"}

    # ==================== 缺陷台账逐条（defects.dart 同七列同判据） ====================
    def defect_rows(self):
        """defects() 只出统计；界面与导出要的是逐条。七列：编号｜日期｜执行者｜漏洞｜影响｜状态｜处置。

        关掉判据与 defects()／冻结件一致：含「闭环」且不含「未闭环」——
        台账里有「已终闭环」这类写法，只匹配「已闭环」会把它误判成未修。
        """
        spec = self.cfg.get("defects") or ""
        if not spec:
            return {"ok": False, "error": "未配置缺陷台账（web_config.json 的 defects）",
                    "list": [], "count": 0}
        path = self._cfg_path(spec)
        if not path.is_file():
            return {"ok": False, "error": "文件不存在", "display": self._tilde(path),
                    "list": [], "count": 0}
        try:
            text = path.read_text(encoding="utf-8-sig")
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": "读取失败：%s" % e, "list": [], "count": 0}
        today = time.strftime("%Y-%m-%d")
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [x.strip() for x in line.split("|")][1:-1]
            if len(cells) < 9 or not re.match(r"^[A-Za-z]{0,3}\d{1,4}$", cells[0] or ""):
                continue
            st = cells[7]
            closed = ("闭环" in st) and ("未闭环" not in st)
            rows.append({"id": cells[0], "date": cells[1], "who": cells[2], "title": cells[3],
                         "impact": cells[4], "status": st, "fix": cells[6],
                         "closed": closed, "today": cells[1] == today})
        return {"ok": True, "display": self._tilde(path), "count": len(rows),
                "open": sum(1 for r in rows if not r["closed"]),
                "closed": sum(1 for r in rows if r["closed"]),
                "today": sum(1 for r in rows if r["today"]),
                "note": "「未闭环」不算闭环；判据与闸门 defects 计数同一把尺子。",
                "list": rows}

    # ==================== 归档／日志日历／最近改动 ====================
    def archive(self):
        cfg = self.cfg.get("archive") or {}
        spec = cfg.get("dir") or ""
        if not spec:
            raise ConfigError("未配置归档目录（web_config.json 的 archive.dir）")
        d = self._cfg_path(spec)
        if not d.is_dir():
            return {"ok": False, "error": "归档目录不存在：%s" % self._tilde(d),
                    "display": self._tilde(d), "list": [], "count": 0}
        notes = cfg.get("compliance_notes") or {}
        rows = []
        for x in sorted(d.iterdir()):
            hit = ""
            for k, v in notes.items():
                if str(k) in x.name:
                    hit = str(v)
            try:
                st = x.stat()
            except Exception:  # noqa: BLE001
                continue
            rows.append({"name": x.name, "is_dir": x.is_dir(), "bytes": st.st_size,
                         "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
                         "compliance_note": hit})
        rows.sort(key=lambda r: r["mtime"], reverse=True)
        return {"ok": True, "display": self._tilde(d), "path": str(d), "count": len(rows),
                "dirs": sum(1 for r in rows if r["is_dir"]),
                "noted": sum(1 for r in rows if r["compliance_note"]),
                "note": "只列不删不移；合规标注来自配置 compliance_notes，不在代码里写死。",
                "list": rows}

    def logdays(self):
        cfg = self.cfg.get("metrics") or {}
        spec = cfg.get("riji_dir") or ""
        if not spec:
            raise ConfigError("未配置每日日志目录（web_config.json 的 metrics.riji_dir）")
        d = self._cfg_path(spec)
        if not d.is_dir():
            return {"ok": False, "error": "目录不存在：%s" % self._tilde(d), "list": [], "count": 0}
        rows = []
        for f in sorted(d.iterdir()):
            if not f.is_file():
                continue
            m = re.match(r"^(\d{4}-\d{2}-\d{2})\.md$", f.name)
            if not m:
                continue
            rows.append({"date": m.group(1), "name": f.name, "bytes": f.stat().st_size,
                         "display": self._tilde(f)})
        rows.sort(key=lambda r: r["date"], reverse=True)
        return {"ok": True, "display": self._tilde(d), "count": len(rows),
                "bytes": sum(r["bytes"] for r in rows), "list": rows,
                "note": "只认 YYYY-MM-DD.md 命名；其他文件不算日志日。"}

    def logday_read(self, date):
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(date or "")):
            return {"ok": False, "error": "日期格式应为 YYYY-MM-DD：%s" % date}
        if not _parse_date(date):
            # 2026-13-40 形状对、日历上不存在；不拦就会答「该日无日志」，
            # 把「问错了」说成「没有」。
            return {"ok": False, "error": "这个日期不存在（按日历校验）：%s" % date}
        cfg = self.cfg.get("metrics") or {}
        if not (cfg.get("riji_dir") or ""):
            raise ConfigError("未配置每日日志目录（web_config.json 的 metrics.riji_dir）")
        f = self._cfg_path(cfg["riji_dir"]) / ("%s.md" % date)
        if not f.is_file():
            return {"ok": False, "error": "该日无日志：%s" % self._tilde(f)}
        text = f.read_text(encoding="utf-8-sig", errors="replace")
        return {"ok": True, "date": date, "display": self._tilde(f), "bytes": f.stat().st_size,
                "chars": len(text), "text": text[:200000]}

    def recent(self):
        cfg = self.cfg.get("metrics") or {}
        items = []
        for x in (cfg.get("recent_roots") or []):
            d = self._cfg_path(x)
            if not d.is_dir():
                items.append({"path": self._tilde(d), "exists": False, "mtime": ""})
                continue
            latest, n = 0.0, 0
            for base, sub_dirs, fns in os.walk(str(d)):
                sub_dirs[:] = [y for y in sub_dirs if y not in self._ANOM_SKIP]
                for fn in fns:
                    n += 1
                    if n > 400:
                        break
                    try:
                        latest = max(latest, os.stat(os.path.join(base, fn)).st_mtime)
                    except Exception:  # noqa: BLE001
                        pass
                if n > 400:
                    break
            items.append({"path": self._tilde(d), "spec": str(x), "exists": True,
                          "scanned": min(n, 400), "capped": n > 400,
                          "mtime": (time.strftime("%Y-%m-%d %H:%M", time.localtime(latest))
                                    if latest else "无时间戳")})
        items.sort(key=lambda r: r["mtime"], reverse=True)
        return {"ok": True, "at": time.strftime("%Y-%m-%d %H:%M:%S"), "list": items,
                "note": "每容器最多扫 400 个文件取最新 mtime；超了标 capped，不谎称扫全。"}

    # ==================== 路径地图／导出 ====================
    def paths_map(self):
        hx = (self.root.parent.parent if self.root else None)
        rows = [("本端项目根", self.root or "", "resolve_root 现读"),
                ("web 目录", HERE, "本件所在"),
                ("HX 层", (hx / "HX") if hx else "", "三端共用的上一层"),
                ("内核包", (hx / "HX" / "kernel" / "bumao_core") if hx else "", "HX/kernel/bumao_core"),
                (self.label("community"), (hx / "HX" / "community") if hx else "", "HX/community"),
                (self.label("minimal"), (hx / "HX" / "minimal") if hx else "", "HX/minimal"),
                ("配置件", self.config_path, "本端 web_config.json"),
                ("准则真身", (self.root / "10_rac" / "zhunze") if self.root else "", "闸门跑的那份"),
                ("缺陷台账", (self._cfg_path(self.cfg["defects"])
                            if self.cfg.get("defects") else ""), "未配置则不出行"),
                ("立法台账", (self._cfg_path(self.cfg["legislation_ledger"])
                           if self.cfg.get("legislation_ledger") else ""), "未配置则不出行"),
                ("长期目标", (self._cfg_path(self.cfg["goals"])
                           if self.cfg.get("goals") else ""), "未配置则不出行"),
                ("待办总表", (self._cfg_path(self.cfg["daiban"])
                           if self.cfg.get("daiban") else ""), "未配置则不出行"),
                ("项目清单", ((self.cfg.get("projects") or {}).get("list_file")
                          and self._cfg_path((self.cfg["projects"] or {})["list_file"]) or ""),
                 "11.56 判据来源"),
                ("状态覆盖层", ((self.cfg.get("projects") or {}).get("state_file")
                           and self._cfg_path((self.cfg["projects"] or {})["state_file"]) or ""),
                 "11.58 用户亲手勾的"),
                ("自检日志目录", (self._cfg_path(self.cfg["check_log_dir"])
                            if self.cfg.get("check_log_dir") else ""), "最近一次 check 落这里"),
                ("备份计划目录", ((self.cfg.get("backup") or {}).get("plan_dir")
                            and self._cfg_path(self.cfg["backup"]["plan_dir"]) or ""), "只读展示")]
        out = []
        for label, val, note in rows:
            if val in (None, ""):
                continue
            p = Path(str(val))
            out.append({"label": label, "path": str(p), "display": self._tilde(p),
                        "kind": ("目录" if p.is_dir() else ("文件" if p.is_file() else "无")),
                        "note": note})
        return {"ok": True, "at": time.strftime("%Y-%m-%d %H:%M:%S"), "list": out,
                "note": "只读展示。快捷方式／启动项检测属桌面特权，本端不复刻（见 jieru.desktop_only）。"}

    def export_markdown(self, kind, payload=None):
        kind = str(kind or "").strip().lower()
        kind = EXPORT_KIND_ALIAS.get(kind, kind)
        if kind in ("goals", "长期目标"):
            return self.goals_export()
        if kind in ("defects", "缺陷"):
            dv = self.defect_rows()
            lines = ["# XTGL 导出 · 缺陷台账", "",
                     "来源：%s" % (dv.get("display") or "未配置"),
                     "共 %s 条 ｜ 未闭环 %s ｜ 已闭环 %s ｜ 今日新增 %s" % (
                         dv.get("count"), dv.get("open"), dv.get("closed"), dv.get("today")),
                     "时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"), ""]
            if not dv.get("ok"):
                lines.append("读不到：%s（本导出无逐条数据，不补零）" % dv.get("error"))
                return "\n".join(lines)
            for r in (dv.get("list") or []):
                lines.append("## %s %s" % (r["id"], r["title"]))
                lines.append("- 状态：%s ｜ 发现：%s ｜ 执行者：%s" % (r["status"], r["date"], r["who"]))
                if r["impact"]:
                    lines.append("- 影响：%s" % r["impact"])
                if r["fix"]:
                    lines.append("- 处置：%s" % r["fix"])
                lines.append("")
            return "\n".join(lines)
        if kind in ("tasks", "任务"):
            rw = self.renwu()
            lines = ["# XTGL 导出 · 任务留档普查", "",
                     "扫描根：%s" % "、".join(r["display"] for r in rw.get("roots") or []),
                     "目录 %d ｜ 有留档 %d ｜ 无留档 %d ｜ 勾完成 %d" % (
                         rw["counts"]["dirs"], rw["counts"]["with_record"],
                         rw["counts"]["without_record"], rw["counts"]["manual_done"]),
                     "时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"), ""]
            for x in (rw.get("list") or []):
                lines.append("## %s（%d 文件）" % (x["name"], x["files"]))
                if not x["records"]:
                    lines.append("- 无留档（B42 类缺口）")
                for rr in x["records"]:
                    lines.append("- %s ｜ %s ｜ %d B ｜ 正文档位：%s ｜ 覆盖：%s ｜ 日志已登记：%s" % (
                        rr["kind"], rr["name"], rr["bytes"],
                        rr["declared_stage"] or "未写", rr["manual"] or "未勾",
                        "是" if rr["logged"] else "否"))
                lines.append("")
            if rw.get("unlogged"):
                lines += ["## 有实体无留档", ""]
                lines += ["- %s（%d 文件）" % (u["name"], u["files"]) for u in rw["unlogged"]]
            return "\n".join(lines)
        if kind in ("projects", "项目"):
            d = self.projects()
            lines = ["# XTGL 导出 · 项目清单", "",
                     "清单：%s" % d.get("list_display"),
                     "共 %d 条，其中人工覆盖 %d 条" % (d.get("total"), d.get("manual_count")),
                     "时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"), ""]
            for r in (d.get("list") or []):
                lines.append("## %s %s（%s）" % (r["icon"], r["name"], r["abbr"]))
                lines.append("- 档位：%s %s（基线 %s，%s）" % (
                    r["stage"], r["stage_name"], r["baseline_stage"],
                    "用户覆盖" if r["is_manual"] else "系统判定"))
                lines.append("- 成品：%d/%d 在位 ｜ 材料：%s ｜ 记录：%s ｜ 根：%s" % (
                    r["artifact_hit"], r["artifact_total"],
                    "在" if any(m["exists"] for m in r["material"]) else "无",
                    "在" if r["record_exists"] else "无",
                    "在" if r["root_exists"] else "不在"))
                if r["note"]:
                    lines.append("- 说明：%s" % r["note"])
                lines.append("")
            return "\n".join(lines)
        if kind in ("anomalies", "yichang_qingdan"):
            return self.anomalies_export(payload)
        if kind in ("ai", "ai_zhenduan"):
            return self.ai_report_export()
        if kind == "handover":
            return self.handover_text(payload or {})
        raise ConfigError("kind 只能是 goals／defects／tasks／projects／anomalies／handover／ai：%s" % kind)

    # ==================== 健康：A 电脑健康 ／ B Agent 系统健康 ====================
    # 准则 11.54（1）：两条健康分开记、分开判，禁止合成一个总分；前端左右分栏。
    def _health_cfg(self):
        return self.cfg.get("health") or {}

    def _hr_path(self):
        spec = str(self._health_cfg().get("rules_file") or "").strip()
        return self._cfg_path(spec) if spec else HEALTH_RULES_PATH

    def health_rules(self):
        p = self._hr_path()
        val = dict(HEALTH_DEFAULTS)
        err, upd = "", ""
        if p.is_file():
            try:
                doc = _read_json(p)
                if isinstance(doc.get("disk_min_free_gb"), (int, float)):
                    val["disk_min_free_gb"] = float(doc["disk_min_free_gb"])
                if isinstance(doc.get("task_archive_days"), (int, float)):
                    val["task_archive_days"] = int(doc["task_archive_days"])
                upd = str(doc.get("updated") or "")
            except Exception as e:  # noqa: BLE001
                err = "阈值件解析失败：%s（本轮按默认 80 GB 判，不猜）" % e
        return {"ok": not err, "path": str(p), "display": self._tilde(p),
                "exists": p.is_file(), "disk_min_free_gb": val["disk_min_free_gb"],
                "task_archive_days": val["task_archive_days"], "updated": upd,
                "error": err,
                "note": "阈值写在仓库外的 ~/.xtgl/health_rules.json，三端共读；"
                        "改阈值只改判定口径，不改取数。"}

    def save_health_rules(self, payload):
        """改阈值：先验参数再碰盘，然后 .bak → tmp → 回读 → os.replace；回读不符就放弃。"""
        payload = payload or {}
        try:
            gb = float(payload.get("disk_min_free_gb"))
        except (TypeError, ValueError):
            raise ConfigError("磁盘阈值必须是数字（GB）：%r"
                              % (payload.get("disk_min_free_gb"),))
        if not 0 < gb <= 100000:
            raise ConfigError("磁盘阈值不合理：%s GB（须大于 0、不超过 100000）" % gb)
        raw_days = payload.get("task_archive_days")
        days = None
        if raw_days is not None and str(raw_days).strip() != "":
            try:
                days = int(float(raw_days))
            except (TypeError, ValueError):
                raise ConfigError("归档天数必须是整数：%r" % (raw_days,))
            if not 0 <= days <= 3650:
                raise ConfigError("归档天数不合理：%s（应在 0—3650）" % days)
        p = self._hr_path()
        old, note = {}, ""
        if p.is_file():
            shutil.copy2(str(p), "%s.%s.bak" % (p, time.strftime("%Y%m%d-%H%M%S")))
            try:
                old = _read_json(p)
                note = str(old.get("note") or "")
            except Exception:  # noqa: BLE001
                old, note = {}, ""
        if days is None:
            # 界面只改 GB 时不能顺手把归档天数清零：那是另一条政策，没被点名就原样留着。
            keep = old.get("task_archive_days")
            days = int(keep) if isinstance(keep, (int, float)) else 0
        if not note:
            note = ("disk_min_free_gb：盘剩余低于此值（GB）算不够用；"
                    "task_archive_days：任务完成满几天后自动归档（0＝下次定时任务就归档）")
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ConfigError("阈值目录建不出来：%s（%s）" % (p.parent, e))
        doc = {"disk_min_free_gb": gb, "task_archive_days": days,
               "updated": time.strftime("%Y-%m-%d %H:%M:%S"), "note": note}
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=4) + "\n",
                       encoding="utf-8")
        try:
            back = _read_json(tmp)
        except Exception as e:  # noqa: BLE001
            _safe_unlink(tmp)
            raise ConfigError("阈值写后回读失败：%s" % e)
        if (float(back.get("disk_min_free_gb") or -1) != gb
                or int(back.get("task_archive_days") or -1) != days):
            _safe_unlink(tmp)
            raise ConfigError("阈值写入后回读不一致，已放弃")
        os.replace(str(tmp), str(p))
        out = self.health_rules()
        out["saved"] = True
        return out

    # ---- 深探针：PowerShell 子进程（驱动·服务·桌面快捷方式）----
    @staticmethod
    def _ps_decode(b):
        for enc in ("utf-8", "gbk"):
            try:
                return b.decode(enc)
            except Exception:  # noqa: BLE001
                continue
        return b.decode("utf-8", errors="replace")

    def _powershell(self):
        return str(self._health_cfg().get("powershell") or
                   shutil.which("powershell.exe") or "powershell.exe")

    def _ps_run(self, script, timeout=None):
        """返回 (跑起来了没有, stdout, 错误说明)。

        「跑不起来／读不懂」一律 ok＝False，调用方标成「未测」——把没测到渲染成
        红色的「坏了」正是 2026-11-02 用户反复报的那件事（lrtp 曾被误判成拦截）。
        """
        import base64
        cfg = self._health_cfg()
        if not bool(cfg.get("probe", True)):
            return False, "", "本端配置关了深探针（health.probe＝false）"
        if not sys.platform.startswith("win"):
            return False, "", "非 Windows，深探针不可用"
        exe = self._powershell()
        if not Path(exe).is_file():
            return False, "", "PowerShell 不存在：%s" % exe
        try:
            enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
            r = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-EncodedCommand", enc],
                               capture_output=True,
                               timeout=int(timeout or cfg.get("probe_timeout") or 25))
        except Exception as e:  # noqa: BLE001
            return False, "", "%s：%s" % (type(e).__name__, str(e)[:160])
        out = self._ps_decode(r.stdout or b"").strip()
        err = self._ps_decode(r.stderr or b"").strip()
        if r.returncode != 0:
            return False, out, "退出码 %s：%s" % (r.returncode, (err or out)[:180])
        return True, out, err

    def _ps_json(self, script, timeout=None):
        ok, out, err = self._ps_run(script, timeout)
        if not ok:
            return False, None, err
        for line in (out or "").splitlines():
            s = line.strip()
            if s[:1] in ("{", "["):
                try:
                    return True, json.loads(s), err
                except Exception as e:  # noqa: BLE001
                    return False, None, "输出读不懂：%s" % e
            if s:
                err = (err + "｜" if err else "") + s[:120]
        return False, None, "输出里没有 JSON%s" % ("（最后输出：%s）" % err[:120] if err else "")

    def _probe_services(self, names):
        # 服务名只留 Windows 服务名里可能出现的字符；中文点位名／空名一律丢掉。
        # 不丢就会拿空串去查注册表，读回来是「注册表里没有这一项」——
        # 那是一条假红：查的本来就不是任何东西。
        esc = ",".join('"%s"' % x for x in
                       [re.sub(r"[^A-Za-z0-9_.-]", "", str(n)) for n in names] if x)
        if not esc:
            return False, [], "配置里的服务名没有一个可查（只支持字母数字与 _ . -）"
        script = ('$names = @(%s); $arr = @(); foreach ($n in $names) { '
                  '$e = Get-ItemProperty "HKLM:\\SYSTEM\\CurrentControlSet\\Services\\$n" '
                  '-ErrorAction SilentlyContinue; '
                  '$s = Get-Service $n -ErrorAction SilentlyContinue; '
                  '$arr += [pscustomobject]@{ name = $n; exists = ($e -ne $null); '
                  'start = if ($e) { $e.Start } else { -1 }; '
                  'status = if ($s) { "" + $s.Status } else { "Absent" }; '
                  'running = ($s -ne $null -and $s.Status -eq "Running") } }; '
                  'ConvertTo-Json -InputObject $arr -Compress') % esc
        ok, data, err = self._ps_json(script)
        if not ok:
            return False, [], err
        rows = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        return True, rows, err

    def _probe_lnks(self, desktop):
        d = str(desktop).replace("'", "''")
        script = ("$sh = New-Object -ComObject WScript.Shell; $arr = @(); "
                  "if (Test-Path -LiteralPath '%s') { "
                  "foreach ($f in Get-ChildItem -LiteralPath '%s' -Filter *.lnk) { "
                  "$sc = $sh.CreateShortcut($f.FullName); $t = $sc.TargetPath; "
                  "$arr += [pscustomobject]@{ name = $f.BaseName; target = $t; "
                  "valid = [bool]($t -and (Test-Path -LiteralPath $t)) } } }; "
                  "ConvertTo-Json -InputObject $arr -Compress") % (d, d)
        ok, data, err = self._ps_json(script, timeout=self._health_cfg().get("lnk_timeout"))
        if not ok:
            return False, [], err
        rows = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        return True, rows, err

    def computer_health(self, payload=None):
        """A 段＝操作系统层：磁盘、内存、开机时长、电量、端口、驱动／服务、
        桌面快捷方式、被占用文件、已知乱放点。逐项现读，读不到就标未测。

        深探针（PowerShell）慢，只在 deep＝1 时跑（POST 按需）；GET 默认给标准库那些。
        """
        cfg = self._health_cfg()
        payload = payload or {}
        deep = bool(payload.get("deep"))
        th = self.health_rules()
        min_gb = float(th.get("disk_min_free_gb") or 80)
        items = []

        def add(key, label, sev, state, value, detail):
            items.append({"key": key, "label": label, "severity": sev, "state": state,
                          "value": value, "detail": detail})

        for dr in (cfg.get("drives") or ["C:", "D:"]):
            name = str(dr).strip()
            if not name:
                continue
            mount = name if name.endswith("\\") else name + "\\"
            try:
                u = shutil.disk_usage(mount)
            except Exception as e:  # noqa: BLE001
                add("disk_%s" % _slug_id(name), "磁盘 %s 剩余" % name, "unknown", "未测", None,
                    "读不到：%s" % str(e)[:120])
                continue
            free_gb = u.free / 1024.0 / 1024.0 / 1024.0
            dm = cfg.get("drive_min_free_gb")
            limit = dm.get(name) if isinstance(dm, dict) else None
            limit = float(limit) if isinstance(limit, (int, float)) else min_gb
            sev = "ok" if free_gb >= limit else ("warn" if free_gb >= limit * 0.6 else "fail")
            add("disk_%s" % _slug_id(name), "磁盘 %s 剩余" % name, sev,
                "够用" if sev == "ok" else ("偏紧" if sev == "warn" else "不够用"),
                round(free_gb, 1),
                "总 %.0f GB｜剩余 %.1f GB（%.1f%%）｜阈值 ≥%.0f GB"
                % (u.total / 1073741824.0, free_gb,
                   (u.free * 100.0 / u.total) if u.total else 0, limit))
        if not (cfg.get("drives") or ["C:", "D:"]):
            add("disk", "磁盘", "unconfigured", "未配", None, "health.drives 为空")

        mem_ok, mem_detail, mem_pct = False, "", None
        try:
            if not sys.platform.startswith("win"):
                raise OSError("非 Windows")

            class _MEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            m = _MEX()
            m.dwLength = ctypes.sizeof(_MEX)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                raise OSError("GlobalMemoryStatusEx 返回 0")
            mem_pct = int(m.dwMemoryLoad)
            mem_detail = "已用 %d%%｜总量 %.1f GB｜可用 %.1f GB" % (
                mem_pct, m.ullTotalPhys / 1073741824.0, m.ullAvailPhys / 1073741824.0)
            mem_ok = True
        except Exception as e:  # noqa: BLE001
            mem_detail = "读不到：%s" % str(e)[:120]
        add("memory", "物理内存占用", "info" if mem_ok else "unknown",
            "已读到（无判据，不判好坏）" if mem_ok else "未测", mem_pct, mem_detail)

        up_ok, up_detail, up_h = False, "", None
        try:
            if not sys.platform.startswith("win"):
                raise OSError("非 Windows")
            ms = int(ctypes.windll.kernel32.GetTickCount64())
            up_h = round(ms / 3600000.0, 1)
            up_detail = "开机约 %.1f 小时（%d 天 %d 小时）" % (up_h, ms // 86400000, (ms % 86400000) // 3600000)
            up_ok = True
        except Exception as e:  # noqa: BLE001
            up_detail = "读不到：%s" % str(e)[:120]
        add("uptime", "开机时长", "info" if up_ok else "unknown",
            "已读到" if up_ok else "未测", up_h, up_detail)

        pw = _power_read()
        add("power", pw[0], "info" if pw[3] else "unknown",
            "已读到" if pw[3] else "未读到", pw[2], pw[1])

        ports = cfg.get("ports") or []
        for x in ports:
            try:
                port = int(x.get("port"))
            except (TypeError, ValueError):
                continue
            label = str(x.get("label") or ("端口 %s" % port))
            host = str(x.get("host") or "127.0.0.1")
            st, why = _port_open(host, port, float(x.get("timeout") or 0.35))
            add("port_%s" % port, "%s（%s:%s）" % (label, host, port),
                ("ok" if st else "warn"), "在监听" if st else "没监听",
                port if st else None,
                why if st else "%s——本端没起不等于坏了，但要用它得先起服务" % why)
        if not ports:
            add("ports", "本机端口监听", "unconfigured", "未配", None,
                "health.ports 没填，一个都没测")

        desktop = str(cfg.get("desktop") or "").strip()
        if deep and desktop:
            okp, rows, err = self._probe_lnks(desktop)
            if not okp:
                add("lnk", "桌面快捷方式", "unknown", "未测", None,
                    "探针没跑通：%s" % (err or "")[:160])
            else:
                bad = [r for r in rows if not r.get("valid")]
                add("lnk", "桌面快捷方式", "warn" if bad else "ok",
                    "%d 个失效" % len(bad) if bad else "全部有效",
                    len(rows),
                    "共 %d 个快捷方式；失效：%s" % (len(rows), "、".join(
                        str(r.get("name")) for r in bad[:6]) or "无"))
        elif desktop:
            add("lnk", "桌面快捷方式", "unknown", "未测", None,
                "深探针按需：勾「深查」才跑（COM 读一次要几秒）")
        else:
            add("lnk", "桌面快捷方式", "unconfigured", "未配", None, "health.desktop 没填")

        svcs = [str(x).strip() for x in (cfg.get("services") or []) if str(x).strip()]
        if deep and svcs:
            okp, rows, err = self._probe_services(svcs)
            if not okp:
                add("services", "驱动／服务", "unknown", "未测", None,
                    "探针没跑通：%s" % (err or "")[:160])
            else:
                for r in rows:
                    nm = str(r.get("name") or "?")
                    if r.get("exists") and r.get("running"):
                        sev, st = "ok", "在运行"
                    elif r.get("exists"):
                        sev, st = "warn", "装了但没跑（状态 %s）" % r.get("status")
                    else:
                        sev, st = "fail", "注册表里没有这一项"
                    add("svc_%s" % _slug_id(nm), "驱动／服务 %s" % nm, sev, st,
                        r.get("start"),
                        "Start=%s（0 启动／1 系统／2 自动／3 手动／4 禁用）｜服务状态 %s"
                        % (r.get("start"), r.get("status")))
        elif svcs:
            add("services", "驱动／服务", "unknown", "未测", None,
                "深探针按需：勾「深查」才跑（配置里点名 %s）" % "、".join(svcs[:6]))
        else:
            add("services", "驱动／服务", "unconfigured", "未配", None,
                "health.services 没填——不猜要查哪个驱动")

        occ = [str(x).strip() for x in (cfg.get("occupied") or []) if str(x).strip()]
        for pth in occ[:12]:
            try:
                pp = self._cfg_path(pth) if not Path(pth).is_absolute() else Path(pth)
            except Exception as e:  # noqa: BLE001
                add("occ_%s" % _slug_id(pth), "被占用检查 %s" % Path(str(pth)).name,
                    "unknown", "未测", None, "路径解不开：%s" % e)
                continue
            if not pp.is_file():
                add("occ_%s" % _slug_id(pp.name), "被占用检查 %s" % pp.name,
                    "info", "文件不在", None, "%s 盘上没有，无从占用" % self._tilde(pp))
                continue
            busy, why = _file_busy(str(pp))
            add("occ_%s" % _slug_id(pp.name), "被占用检查 %s" % pp.name,
                "warn" if busy else "info", "被占用" if busy else "没被占用",
                None, "%s｜%s" % (self._tilde(pp), why))
        if not occ:
            add("occupied", "被占用文件", "unconfigured", "未配", None,
                "health.occupied 没填（填了也只在深查时逐个试开）")

        mis = cfg.get("misplaced") or []
        for x in mis:
            pth = str(x.get("path") or "").strip()
            if not pth:
                continue
            ex = Path(pth).exists()
            add("mis_%s" % _slug_id(pth), "乱放点 %s" % Path(pth).name,
                "warn" if ex else "ok", "还在" if ex else "已不在",
                None, "%s｜%s" % (pth, str(x.get("reason") or "")))
        if not mis:
            add("misplaced", "已知乱放点", "unconfigured", "未配", None,
                "health.misplaced 没填（总纲第三章 B/C/D 组点位应写在配置里，不写进代码）")

        cnt = {}
        for it in items:
            cnt[it["severity"]] = cnt.get(it["severity"], 0) + 1
        return {"ok": True, "side": "A", "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "deep": bool(deep), "items": items, "count": len(items),
                "counts": {"fail": cnt.get("fail", 0), "warn": cnt.get("warn", 0),
                           "ok": cnt.get("ok", 0), "unknown": cnt.get("unknown", 0),
                           "info": cnt.get("info", 0), "unconfigured": cnt.get("unconfigured", 0)},
                "thresholds": {"disk_min_free_gb": min_gb,
                               "rules_updated": th.get("updated") or "",
                               "rules_error": th.get("error") or ""},
                "note": "A 段＝操作系统层，只描述本机现在读到什么；没配的标未配、"
                        "没测到的标未测，都不判成红，也不与 B 段合成总分（准则 11.54（1））。"}

    def agent_health(self):
        """B 段＝中枢层，按 11.54（1）点名的六项各读各的真数据源。

        判据一律现读：不用「有条款就算台账干净」这类代理条件——那种写法永远 100%，是假绿。
        """
        _man = self.manual()
        mmap = _man.get("map", {})
        mver = {i["key"]: i.get("verdict", "auto") for i in _man.get("items", [])}
        mk = self.meta()
        rl = self.rules()
        lc = self.last_check()
        dft = self.defects()
        db = self.daiban()
        lg = self.logs(limit=2000)
        today = time.strftime("%Y-%m-%d")
        rows_today = sum(1 for x in (lg.get("list") or []) if str(x.get("date")) == today)
        dead = self.log_dead_links(lg)
        over = 0
        for x in (db.get("list") or []):
            nxt = str(x.get("next") or "")[:10]
            if nxt and nxt < today and "完成" not in str(x.get("status") or ""):
                over += 1
        items = []

        def add(key, label, machine, detail, known=True):
            """machine＝机器判据结论；人工勾选压过它，两个方向都压。"""
            over_ok = bool(mmap.get(key))
            verdict = mver.get(key, "auto")
            items.append({"key": key, "label": label,
                          "machine": (machine if known else None),
                          "known": bool(known),
                          "manual": over_ok,
                          "verdict": verdict,
                          "ok": bool((machine if known else False) or over_ok),
                          "detail": detail})

        v = mk.get("version") if isinstance(mk, dict) else None
        add("b_version", "准则版本可读（00_meta/meta.json）",
            bool(v), ("v%s（%s）" % (v, mk.get("name") or "")) if v
            else "读不到：%s" % str((mk or {}).get("error") or "meta.json 没有 version")[:160],
            known=bool(v))
        n_cl = len(rl.get("clauses") or [])
        add("b_clauses", "条款总数（三层合并后）",
            n_cl > 0 and not (rl.get("errors") or []),
            "条款 %d ｜ 规则文件 %d ｜ 冲突 %d ｜ 格式错误 %d"
            % (n_cl, len(rl.get("file_rows") or []), len(rl.get("conflicts") or []),
               len(rl.get("errors") or [])),
            known=True)
        add("b_check", "最近自检已人工核实", bool(lc.get("ok")),
            (lc.get("conclusion") or lc.get("error") or "")[:200], known=bool(lc.get("ok") or lc.get("conclusion")))
        add("b_defect", "缺陷台账已人工核实", bool(dft.get("clean")),
            ("%d/%d 未闭环" % (dft.get("open", 0), dft.get("total", 0)))
            if dft.get("configured") else (dft.get("error") or ""),
            known=bool(dft.get("configured")))
        add("b_daiban", "周期待办按周期在跑", bool(db.get("ok")) and over == 0,
            "共 %d 行 ｜ 已过下一步日期 %d 行" % (db.get("count", 0), over)
            if db.get("ok") else (db.get("error") or ""), known=bool(db.get("ok")))
        add("b_log", "当日日志已人工核实", rows_today > 0,
            "今日 %d 条 ｜ 死链 %d 条" % (rows_today, len(dead)), known=True)
        passed = sum(1 for i in items if i["ok"])
        return {"ok": True, "side": "B", "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "items": items, "total": len(items), "passed": passed,
                "unknown": sum(1 for i in items if i["machine"] is None),
                "core_version": CORE_VERSION,
                "manual_path": _man.get("path") or "",
                "note": "B 段＝核心引擎层，六项各读各的源；人工勾选只压这两条判据，"
                        "不压 A 段的实测数。"}

    def health_page(self, payload=None):
        """健康页一次给齐两栏：左 A 电脑健康，右 B 系统健康。各说各话，不分高下。"""
        a = self.computer_health(payload)
        b = self.agent_health()
        r = self.health_rules()
        return {"ok": True, "at": a["at"], "computer": a, "agent": b, "rules": r,
                "deep": a["deep"],
                "note": "两条健康分开判：左＝电脑健康（操作系统层），右＝Agent 系统健康（中枢层）。"
                        "两边各报各的数，不合成总分（准则 11.54（1））。"}

    # ==================== 接入执行监控：check_*.log 的真实跑批记录 ====================
    def jieru_runs(self, keep=20):
        spec = str(self.cfg.get("check_log_dir") or "").strip()
        if not spec:
            return {"ok": False, "error": "未配置自检日志目录（check_log_dir）",
                    "runs": [], "total_log": 0, "today_count": 0,
                    "streak_days": 0, "avg_seconds": 0}
        d = self._cfg_path(spec)
        if not d.is_dir():
            return {"ok": False, "error": "目录不存在：%s" % self._tilde(d),
                    "runs": [], "total_log": 0, "today_count": 0,
                    "streak_days": 0, "avg_seconds": 0, "display": self._tilde(d)}
        all_rows = []
        try:
            listing = list(d.iterdir())
        except OSError as e:
            return {"ok": False, "error": "目录读不了：%s" % e, "runs": [],
                    "total_log": 0, "today_count": 0, "streak_days": 0, "avg_seconds": 0}
        for p in listing:
            m = re.match(r"^check_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})\.log$", p.name)
            if not (p.is_file() and m):
                continue
            g = [int(x) for x in m.groups()]
            try:
                at = datetime.date(g[0], g[1], g[2])
            except ValueError:
                continue
            stamp = "%04d-%02d-%02d %02d:%02d:%02d" % tuple(g)
            try:
                body = p.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:  # noqa: BLE001
                all_rows.append({"at": stamp, "file": p.name, "ok": False,
                                 "conclusion": "读取失败：%s" % str(e)[:80],
                                 "fail_count": 1, "seconds": None})
                continue
            cm = re.search(r"\[结论\]\s*([^\n]*)", body)
            concl = (cm.group(1).strip() if cm else "未读到结论")
            sm = re.findall(r"\[(\d+(?:\.\d+)?)s\]", body)
            secs = round(float(sm[-1])) if sm else None
            fails = len(re.findall(r"FAIL", body))
            all_rows.append({
                "at": stamp, "file": p.name,
                "date": "%04d-%02d-%02d" % (g[0], g[1], g[2]),
                "ok": "ALL PASS" in concl,
                "conclusion": concl[:200],
                "fail_count": 0 if "ALL PASS" in concl else (fails or 1),
                "seconds": secs, "display": self._tilde(p)})
        all_rows.sort(key=lambda r: r["at"], reverse=True)
        today = datetime.date.today()
        tc = sum(1 for r in all_rows
                 if _parse_date(r.get("at")) == today)
        days = set()
        for r in all_rows:
            dd = _parse_date(r.get("at"))
            if dd:
                days.add(dd)
        streak, cur = 0, today
        while cur in days:
            streak += 1
            cur = cur - datetime.timedelta(days=1)
        with_sec = [r["seconds"] for r in all_rows if r.get("seconds")]
        avg = round(sum(with_sec[:20]) / float(len(with_sec[:20])), 1) if with_sec else 0
        return {"ok": True, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "display": self._tilde(d), "runs": all_rows[:max(1, int(keep))],
                "total_log": len(all_rows), "today_count": tc, "streak_days": streak,
                "avg_seconds": avg,
                "fail_last": next((r["conclusion"] for r in all_rows if not r["ok"]), ""),
                "note": "接入与自检只由 check 日志与留档登记证明；"
                        "结论行里没有 ALL PASS 就按未通过报，不补绿。"}

    # ==================== 汇入凭据面（只报状态，不回传密钥）====================
    def access(self):
        cfg = self.cfg.get("access") or {}
        sub = str(cfg.get("subpath") or "").strip()
        if not sub:
            return {"ok": False, "error": "未配置汇入记录面（web_config.json 的 access.subpath）",
                    "list": [], "count": 0}
        rows = []
        for e in ((self.cfg.get("oss") or {}).get("ends") or []):
            abbr = str(e.get("abbr") or "?")
            try:
                d = self._cfg_path(str(e.get("root") or ".")) / sub
            except Exception as ex:  # noqa: BLE001
                rows.append({"end": abbr, "label": str(e.get("label") or self.label(abbr)),
                             "path": "", "exists": False, "files": [],
                             "error": "路径解不开：%s" % ex})
                continue
            row = {"end": abbr, "label": str(e.get("label") or self.label(abbr)),
                   "path": str(d), "display": self._tilde(d), "exists": d.is_dir(),
                   "files": [], "probed_count": 0, "pass_count": 0, "fail_count": 0,
                   "no_result_count": 0}
            if d.is_dir():
                try:
                    fl = sorted([f for f in d.iterdir() if f.is_file()])
                except OSError as ex:
                    row["error"] = "目录读不了：%s" % str(ex)[:120]
                    fl = []
                for f in fl:
                    one = {"name": f.name, "bytes": f.stat().st_size,
                           "mtime": time.strftime("%Y-%m-%d %H:%M",
                                                  time.localtime(f.stat().st_mtime)),
                           "has_secret_mark": False, "result": "无结论行", "ok": False,
                           "display": self._tilde(f)}
                    try:
                        body = f.read_text(encoding="utf-8-sig", errors="replace")
                    except Exception as ex:  # noqa: BLE001
                        one["result"] = "读取失败：%s" % str(ex)[:60]
                        row["files"].append(one)
                        continue
                    if re.search(r"(?i)(api[_ -]?key|secret|token|sk-[A-Za-z0-9]{6,})", body):
                        one["has_secret_mark"] = True
                    if "ALL PASS" in body or "接入成功" in body:
                        one["result"], one["ok"] = "已接入（ALL PASS）", True
                        row["pass_count"] += 1
                    elif re.search(r"\bFAIL\b", body) or "未通过" in body or "失败" in body:
                        one["result"], one["ok"] = "未通过", False
                        row["fail_count"] += 1
                    else:
                        one["result"] = "无结论行"
                        row["no_result_count"] += 1
                    row["probed_count"] += 1
                    row["files"].append(one)
            else:
                row["error"] = row.get("error") or "目录不存在"
            rows.append(row)
        tot = sum(len(r["files"]) for r in rows)
        return {"ok": True, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "subpath": sub, "list": rows, "end_count": len(rows),
                "count": tot,
                "pass_count": sum(r["pass_count"] for r in rows),
                "fail_count": sum(r["fail_count"] for r in rows),
                "no_result_count": sum(r["no_result_count"] for r in rows),
                "note": "只报「有没有结论行、结论是什么」，文件正文与密钥一律不回传；"
                        "无结论行不等于通，也不等于不通，如实标出来让人去看。"}

    # ==================== 条款全文检索 ====================
    def clause_search(self, q, limit=60):
        q = str(q or "").strip()
        if len(q) < 2:
            raise ConfigError("检索词至少 2 个字：%s" % q)
        if len(q) > 60:
            raise ConfigError("检索词过长（不超过 60 字）")
        r = self.rules()
        needle = q.lower()
        rows = []
        for c in (r.get("clauses") or []):
            body = c.get("body") or []
            hay = " ".join([str(c.get("id") or ""), str(c.get("title") or "")] +
                           [str(x) for x in body]).lower()
            if needle not in hay:
                continue
            hits = hay.count(needle)
            where, snip = "", ""
            if needle in str(c.get("id") or "").lower():
                where = "编号"
            elif needle in str(c.get("title") or "").lower():
                where, snip = "标题", str(c.get("title"))[:160]
            else:
                for ln in body:
                    s = str(ln)
                    if needle in s.lower():
                        i = s.lower().find(needle)
                        where = "正文"
                        snip = s[max(0, i - 60):i + 140]
                        break
            rows.append({"id": c.get("id"), "title": c.get("title"),
                         "layer": c.get("layer"), "layer_label": LAYER_LABEL.get(
                             c.get("layer"), c.get("layer")),
                         "file": c.get("file"), "hits": hits,
                         "match_in": where, "snippet": snip.strip()})
            if len(rows) >= limit:
                break
        rows.sort(key=lambda x: (-x["hits"], str(x["id"])))
        return {"ok": True, "q": q, "list": rows, "count": len(rows),
                "scanned": len(r.get("clauses") or []),
                "truncated": len(rows) >= limit,
                "rule_errors": len(r.get("errors") or []),
                "note": "只搜本端已启用的三层条款合并结果（内核层不可覆盖）；"
                        "命中按出现次数排，片段只给上下文不整段搬运。"}

    # ==================== 导出：文本 + 落盘（留 20 份，溢出只迁不删）====================
    def anomalies_export(self, payload=None):
        sc = self.anomaly_scan(payload or {})
        items = sc.get("items") or []
        rank = {"高": 0, "中": 1, "低": 2}
        hi = sum(1 for x in items if x.get("level") == "高")
        mid = sum(1 for x in items if x.get("level") == "中")
        lo = sum(1 for x in items if x.get("level") == "低")
        lines = ["# 文件异常清单（可外发）", "",
                 "- 导出时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"),
                 "- 导出工具：Bumao XTGL 控制台（本端 %s）" % (self.cfg.get("product_edition") or "?"),
                 "- 用途：把「乱存、重复、疑似顺手存」的东西列清楚，交给别人清理",
                 "", "> 这份文件是自包含的：拿到它的人不需要登录本机系统，也不需要会跑脚本。",
                 "> 每条都写了「是什么／为什么算异常／建议动作」，照最后一张表做即可。", "",
                 "## 一、总量", "", "| 指标 | 数量 |", "| --- | --- |",
                 "| 扫描根 | %s |" % "、".join("`%s`" % x for x in (sc.get("roots") or []) or ["—"]),
                 "| 已扫条目 | %s |" % sc.get("scanned", 0),
                 "| 异常总数 | %d |" % len(items),
                 "| 高（建议立刻处理） | %d |" % hi,
                 "| 中（本轮内处理） | %d |" % mid,
                 "| 低（可攒着） | %d |" % lo]
        if sc.get("truncated"):
            lines.append("| 注意 | 已截断：条目超过 %s |" % sc.get("max_entries"))
        if sc.get("error"):
            lines.append("| 状态未知 | %s |" % sc.get("error"))
        lines += ["", "## 二、逐条明细", ""]
        if not items:
            lines += ["（没有发现异常——只说明这一轮这些根里没扫出来，不等于全盘干净。）", ""]
        for i, a in enumerate(items):
            lines += ["### %d. [%s] %s" % (i + 1, a.get("level"), a.get("title")), "",
                      "- 类型：%s" % a.get("kind"),
                      "- 位置：`%s`" % str(a.get("path")).replace("\n", "` ／ `"),
                      "- 为什么算异常：%s" % a.get("why"),
                      "- 建议动作：%s" % a.get("fix"), ""]
        lines += ["## 三、清理纪律（别把好事做成事故）", "",
                  "1. **只迁不删**：可疑文件先移到 90_lishi，观察一轮没人喊缺东西再处理。",
                  "2. **不碰这三类**：正在被进程占用的文件、宿主配置与台账、90_lishi 里的历史。",
                  "3. **同名不同内容**：先比 sha256 再决定留哪个；只按文件名删会删错。",
                  "4. 清完在 30_taizhang 记一笔「清了我，因为 X」。", "",
                  "（本清单由只读扫描生成：扫描本身不删除、不改名、不移动任何文件。）"]
        items.sort(key=lambda x: (rank.get(x.get("level"), 3), str(x.get("kind"))))
        return "\n".join(lines)

    def handover_text(self, payload):
        payload = payload or {}
        spec = str(payload.get("dir") or "").strip()
        if not spec:
            raise ConfigError("交接单要点明交接哪个任务目录")
        d = Path(spec) if Path(spec).is_absolute() else self._cfg_path(spec)
        if not d.is_dir():
            raise ConfigError("任务目录不存在：%s" % d)
        recs = [f for f in sorted(d.iterdir())
                if f.is_file() and self._record_kind(f.name)]
        order = {"任务留档": 0, "本次项目": 1, "项目记录": 2}
        rec = (min(recs, key=lambda f: order.get(self._record_kind(f.name), 9))
               if recs else None)
        body = ""
        stage = ""
        if rec is not None:
            try:
                body = rec.read_text(encoding="utf-8-sig", errors="replace")
            except Exception as e:  # noqa: BLE001
                body = ""
                rec = None
            stage = self._declared_stage(rec) or ""
        done = bool(re.search(r"(全部完成|已完成|已交付|已归档)", body))
        openi = bool(re.search(r"(未完成|待办|下一步|TODO|尚未)", body, re.I))
        if body and done and not openi:
            prog = "留档里写明已完成；建议核对一次产物是否真的在。"
        elif body and done and openi:
            prog = "留档里既有完成项也有未完成项——大概率是「主体已完成、尾巴没收」。先看「下一步」那段。"
        elif body and openi:
            prog = "留档里写明还有未完成项；先看「下一步」那段再动手。"
        elif body:
            prog = "留档没有明确写进度，需要读正文判断。"
        else:
            prog = ("读不到留档正文，无法判断进度。" if rec is None else "留档是空的，进度无从判断。")
        mt = time.strftime("%Y-%m-%d %H:%M", time.localtime(d.stat().st_mtime))
        files = [str(x) for x in (payload.get("files") or []) if str(x).strip()][:30]
        lines = ["# 任务交接单 · %s" % d.name, "",
                 "- 导出时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"),
                 "- 导出工具：Bumao XTGL 控制台（本端 %s）" % (self.cfg.get("product_edition") or "?"),
                 "- 用途：一个人交给另一个人继续干，不需要读完全部留档", "",
                 "> 这份文件是自包含的：拿到它的人不需要登录本机系统，也不需要会跑脚本。", "",
                 "## 一、这是什么事", "", "| 项 | 内容 |", "| --- | --- |",
                 "| 任务 | %s |" % d.name,
                 "| 留档 | %s |" % ("`%s`" % self._tilde(rec) if rec else "**没有留档件**"),
                 "| 留档类型 | %s |" % (self._record_kind(rec.name) if rec else "—"),
                 "| 目录最后改动 | %s |" % mt,
                 "| 留档自评完成度 | %s（%s） |" % (stage or "未标注",
                                                  self.STAGE_NAMES.get(stage, "未判")),
                 "| 目录内文件数 | %d |" % len([f for f in d.iterdir() if f.is_file()]), "",
                 "## 二、现在到哪一步了", "", prog, ""]
        if files:
            lines += ["## 三、关键文件", ""]
            for f in files:
                p2 = Path(f) if Path(f).is_absolute() else self._cfg_path(f)
                lines.append("- `%s`%s" % (f, "" if p2.exists() else "（**已不存在，需确认**）"))
            lines.append("")
        lines += ["## 四、接手先做三件事", "",
                  "1. 打开留档%s，从头读「任务摘要头」和结论两段，中间可以跳。"
                  % ("（`%s`）" % self._tilde(rec) if rec else "（本目录里没有留档，先补骨架）"),
                  "2. 跑一次自检：`python 10_rac\\<本端入口名> whoami`，再跑 `check --strict`，"
                  "不 ALL PASS 先修。",
                  "3. 看未闭环项：本端 30_taizhang 的缺陷台账里状态不含「闭环」的行。", "",
                  "## 五、别踩的坑", "",
                  "- 不要手改 20_view 下的视图，那是渲染产物，改了下一轮就被覆盖还会报漂移。",
                  "- 不要用客户端定时任务顶替周期任务，换机就失效。",
                  "- 改前必须备份（同目录 `.bak`），没有备份的改动按事故处理。",
                  "- 交接不等于验收：接手动完还要原负责人点一次「已验收」才算 S3。", ""]
        return "\n".join(lines)

    def export_slug(self, kind, payload=None):
        k = EXPORT_KIND_ALIAS.get(str(kind or "").strip().lower(), str(kind or "").strip().lower())
        if k == "handover":
            spec = str((payload or {}).get("dir") or "").strip()
            return "jiaojie_%s" % _slug_id(Path(spec.rstrip("/\\")).name or "renwu")
        return EXPORT_PREFIX.get(k, "")

    def save_export(self, payload):
        """落盘到资产目录：tmp→改名→回读→每类留 N 份，溢出只迁不删。"""
        payload = payload or {}
        raw_kind = str(payload.get("kind") or "").strip()
        if not raw_kind:
            raise ConfigError("要点明导出哪一类（kind）")
        kind = EXPORT_KIND_ALIAS.get(raw_kind.lower(), raw_kind.lower())
        text = self.export_markdown(kind, payload)
        cfg = self.cfg.get("export") or {}
        spec = str(cfg.get("dir") or "").strip()
        if not spec:
            raise ConfigError("未配置导出落点（web_config.json 的 export.dir）")
        d = self._cfg_path(spec)
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ConfigError("导出落点建不出来：%s（%s）" % (d, e))
        prefix = self.export_slug(kind, payload) or ("xtgl_%s" % _slug_id(kind))
        name = "%s_%s.md" % (prefix, time.strftime("%Y%m%d_%H%M%S"))
        target = d / name
        tmp = d / (name + ".tmp")
        data = text.encode("utf-8")
        try:
            tmp.write_bytes(data)
            if target.exists():
                raise ConfigError("同名导出件已存在，不覆盖：%s" % target)
            os.replace(str(tmp), str(target))
        except Exception:
            _safe_unlink(tmp)
            raise
        back = target.read_bytes()
        if len(back) != len(data):
            raise ConfigError("导出回验失败：写入 %d 字节，读回 %d 字节" % (len(data), len(back)))
        moved = self._export_prune(d, prefix, int(cfg.get("keep") or EXPORT_KEEP), cfg)
        return {"ok": True, "kind": kind, "path": str(target), "display": self._tilde(target),
                "bytes": len(back), "chars": len(text), "pruned_moved": moved,
                "keep": int(cfg.get("keep") or EXPORT_KEEP),
                "overflow": str(self._cfg_path(cfg.get("overflow_dir"))) if cfg.get("overflow_dir") else "",
                "note": "落盘件与浏览器下载走同一段取数，字节数应当一致；"
                        "每类只留最近 %d 份，多出来的迁到溢出目录，不删。" % int(cfg.get("keep") or EXPORT_KEEP)}

    def _export_prune(self, d, prefix, keep, cfg):
        try:
            fl = [f for f in d.iterdir()
                  if f.is_file() and f.name.startswith(prefix + "_")
                  and not f.name.endswith(".tmp")]
        except OSError:
            return 0
        fl.sort(key=lambda f: (f.stat().st_mtime, f.name), reverse=True)
        if len(fl) <= keep:
            return 0
        spec = str(cfg.get("overflow_dir") or "").strip()
        if not spec:
            return 0
        tgt = self._cfg_path(spec)
        moved = 0
        for f in fl[keep:]:
            try:
                tgt.mkdir(parents=True, exist_ok=True)
                dst = tgt / f.name
                if dst.exists():
                    continue  # 同名已在溢出目录里：原地留着不动，绝不覆盖别人的历史
                shutil.move(str(f), str(dst))
                moved += 1
            except OSError:
                continue
        return moved

    def log_dead_links(self, lg=None):
        """日志死链的唯一取数口：闸门（b_log）与未处理面（anomaly）同调此函数。

        口径＝全部日志（logs(limit=2000)）里登记了留档件、但盘上已不存在的行。
        不得在别处再写一遍同规则（用户立法：治理件数字须同函数复现）。
        """
        lg = lg if isinstance(lg, dict) else self.logs(limit=2000)
        return [r for r in (lg.get("list") or [])
                if r.get("detail") and not r.get("exists")]

    def anomaly(self):
        """未处理面：闸门／缺陷／人工判定／日志死链／客户端／规则冲突，逐项现读。

        读不到就写「状态未知」，不补零、不把「没配置」说成「没有问题」。
        """
        items = []
        lc = self.last_check()
        items.append({"key": "gate", "label": "最近一次闸门自检",
                      "state": ("绿" if lc.get("ok") else "红") if lc.get("configured") else "状态未知",
                      "count": 0 if lc.get("ok") else 1,
                      "detail": (lc.get("conclusion") or lc.get("error") or "")[:200],
                      "at": lc.get("at") or ""})
        d = self.defects()
        items.append({"key": "defects", "label": "缺陷未闭环",
                      "state": "状态未知" if d.get("error") else ("无" if not d.get("open") else "有未闭环"),
                      "count": int(d.get("open") or 0),
                      "detail": "、".join([str(x) for x in (d.get("open_ids") or [])])[:200],
                      "at": ""})
        m = self.manual()
        pend = [str(x.get("label") or x.get("key")) for x in (m.get("items") or []) if not x.get("ok")]
        items.append({"key": "manual", "label": "人工判定未核实",
                      "state": "状态未知" if not m.get("ok") else ("全部已核实" if not pend else "有未核实"),
                      "count": len(pend), "detail": "；".join(pend)[:200],
                      "at": m.get("updated") or ""})
        lg = self.logs(limit=2000)
        dead = self.log_dead_links()
        items.append({"key": "log_dead", "label": "日志死链（登记的留档件已不在）",
                      "state": "状态未知" if not lg.get("ok") else ("无死链" if not dead else "有死链"),
                      "count": len(dead),
                      "detail": "、".join([os.path.basename(str(r.get("detail"))) for r in dead[:6]])[:200],
                      "at": ""})
        cl = self.clients(lg)
        items.append({"key": "clients", "label": "已接入客户端（由日志登记证明）",
                      "state": "状态未知" if not cl.get("ok") else ("有" if cl.get("count") else "无登记"),
                      "count": int(cl.get("count") or 0),
                      "detail": "、".join([str(x.get("name")) for x in (cl.get("list") or [])[:8]])[:200],
                      "at": ""})
        rl = self.rules()
        conf = rl.get("conflicts") or []
        errs = rl.get("errors") or []
        items.append({"key": "rules", "label": "规则冲突 / 格式错误",
                      "state": "有" if (conf or errs) else "无",
                      "count": len(conf) + len(errs),
                      "detail": "；".join([str(x.get("reason") or x) for x in (conf[:3] + errs[:3])])[:200],
                      "at": ""})
        return {"ok": True, "at": time.strftime("%Y-%m-%d %H:%M:%S"), "items": items,
                "total_open": sum(int(x.get("count") or 0) for x in items if x["key"] != "clients")}

    def anomaly_scan(self, payload=None):
        """文件卫生扫描（只读，绝不删、绝不改、绝不移动）：判据与桌面端异常页同一套。

        扫哪些目录由本端配置 anomaly.roots 给（相对项目根或绝对路径），没配就只扫项目根。
        跨目录「同名同字节」默认不算异常：三端核心件本来就该逐字节一致，
        把它报成重复是误报；要用这条只能显式打开 anomaly.duplicates。
        """
        spec = self.cfg.get("anomaly") or {}
        if self.root_error:
            return {"ok": False, "error": self.root_error, "items": [], "scanned": 0}
        base = self.root
        rels = spec.get("roots") or ["."]
        roots = [_as_path(r, base) for r in rels if str(r).strip()]
        tried = [str(p) for p in roots]
        roots = [p for p in roots if p.is_dir()]
        if not roots:
            return {"ok": False, "error": "anomaly.roots 配了但一个都不存在",
                    "items": [], "scanned": 0, "tried": tried}
        try:
            max_entries = int(spec.get("max_entries") or 20000)
            max_depth = int(spec.get("max_depth") or 5)
        except (TypeError, ValueError):
            return {"ok": False, "error": "anomaly 的 max_entries / max_depth 不是整数",
                    "items": [], "scanned": 0}
        bak_allowed = set(str(x) for x in (spec.get("bak_allowed") or ["90_lishi"]))
        try:
            bak_max_age = int(spec.get("bak_max_age_days") or 7)
        except (TypeError, ValueError):
            bak_max_age = 7
        want_dup = bool(spec.get("duplicates"))
        try:
            limit = int((payload or {}).get("limit") or 200)
        except (TypeError, ValueError):
            limit = 200
        limit = max(1, min(1000, limit))
        out, seen, truncated = [], 0, False
        by_key = {}

        def add(kind, level, title, path, why, fix):
            out.append({"kind": kind, "level": level, "title": title, "path": str(path),
                        "why": why, "fix": fix})

        for r in roots:
            try:
                top = sorted(r.iterdir())
            except OSError as e:
                add("不可读", "低", "目录读不了：%s" % r.name, r, str(e), "确认权限。")
                continue
            flat = [p for p in top if p.is_file()]
            if len(flat) > 1:
                add("根级平铺", "高" if len(flat) > 4 else "中",
                    "%s 根下有 %d 个平铺文件" % (r.name, len(flat)), r,
                    "约定容器根下只留一个入口或说明。",
                    "把非入口文件移进对应的台账／历史／任务子目录。")
            stack = [(p, 1) for p in top]
            while stack:
                p, depth = stack.pop()
                if p.name in self._ANOM_SKIP or any(x in self._ANOM_SKIP for x in p.parts):
                    continue
                if seen >= max_entries:
                    truncated = True
                    break
                seen += 1
                if p.is_dir():
                    if self._ANOM_TEMP.match(p.name):
                        add("临时目录", "中", "疑似临时目录：%s" % p.name, p,
                            "这种名字通常是「先放这儿回头收拾」的产物。",
                            "确认无用整体移入历史目录；有用就改成有意义的名字。")
                    if depth < max_depth:
                        try:
                            stack.extend([(c, depth + 1) for c in sorted(p.iterdir())])
                        except OSError:
                            pass
                    continue
                if not p.is_file():
                    continue
                name = p.name
                if self._ANOM_COPY.search(name) and "90_lishi" not in p.parts:
                    pos = name
                    for t in (" - 副本", "（1）", "(1)", "副本", "拷贝", "_old", "_旧",
                              "最终版", "最新版", "未命名", "备份"):
                        pos = pos.replace(t, "")
                    pos = pos.strip()
                    has_twin = bool(pos) and pos != name and (p.parent / pos).is_file()
                    add("疑似副本", "中" if has_twin else "低", name, p,
                        ("同目录里能对上正名，基本就是重复。" if has_twin
                         else "命名像副本，但同目录没有正名，只算命名习惯。"),
                        "对上正名的走删除对账，不手删；其余改名。")
                if name.endswith(".bak") and not any(x in p.parts for x in bak_allowed):
                    # 位置不是判据（改前件与源件同目录是约定），陈旧才是。
                    try:
                        age_days = (time.time() - p.stat().st_mtime) / 86400.0
                    except OSError:
                        age_days = 0
                    if age_days > bak_max_age:
                        add(".bak 陈旧", "中" if age_days <= 30 else "高", name, p,
                            "改前件放在源件同目录是约定，但超过 %d 天没归档，"
                            "说明那一轮没收口。" % bak_max_age,
                            "确认对应用已闭环后归档或按删除对账处理，不手删。")
                if want_dup:
                    try:
                        by_key.setdefault("%s|%s" % (name, p.stat().st_size), []).append(str(p))
                    except OSError:
                        pass
        if want_dup:
            for key, paths in list(by_key.items())[:40]:
                if len(paths) > 1:
                    add("同名同字节", "中" if len(paths) > 2 else "低",
                        "%s ×%d" % (key.split("|")[0], len(paths)), paths[0],
                        "已显式打开 duplicates：同名同字节数的多份按重复对待。",
                        "人工确认留哪一份，其余走删除对账。")
                    out[-1]["path"] = "\n".join(paths[:6])
        rank = {"高": 0, "中": 1, "低": 2}
        out.sort(key=lambda x: (rank.get(x["level"], 3), x["kind"], x["title"]))
        return {"ok": True, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "roots": [str(p) for p in roots], "scanned": seen,
                "max_entries": max_entries, "truncated": truncated,
                "count": len(out), "shown": min(len(out), limit),
                "duplicates": want_dup, "items": out[:limit],
                "note": "只读扫描：本接口不删除、不改名、不移动任何文件"}

    # ---------- 汇总 ----------
    @staticmethod
    def _tilde(p):
        """把用户主目录换成 ~，页面/导出都不出现本机绝对路径。"""
        try:
            rel = Path(p).resolve().relative_to(Path.home().resolve())
            return "~\\" + str(rel)
        except Exception:  # noqa: BLE001
            return Path(p).name

    def overview(self, run_gates=True):
        src = self.root_source or ""
        src_short = ("默认" if src.startswith("默认") else
                     "配置" if src.startswith("web_config") else
                     "命令行" if src.startswith("命令行") else
                     "环境变量" if src.startswith("环境变量") else
                     "演示" if src.startswith("内置") else src)
        # 日志读一次，客户端汇总复用同一份，避免两次磁盘读。
        # 这里必须取全量：页面按「天 → 客户端 → 项目」整棵渲染，只给最近 30 条会让
        # 早期日期整段消失，且「已接入客户端」的条数会少算（曾出现 30 条 vs 文件 66 条）。
        # 2000 条封顶，防超大日志把页面拖死。
        _logs = self.logs(limit=2000)
        base = {
            "core_version": CORE_VERSION,
            "edition": str(self.cfg.get("product_edition") or ""),
            "labels": self.labels(),
            "title": display_title(self.cfg),
            "subtitle": self.cfg.get("subtitle"),
            "subtitle_en": self.cfg.get("subtitle_en") or "",
            "root": str(self.root) if self.root else "",
            "root_name": self.root.name if self.root else "",
            "root_source": self.root_source,
            "root_source_short": src_short,
            "demo": self.demo,
            "setup_required": bool(self.root_error),
            "setup_reason": self.root_error or "",
            "python": self.python_version(),
            "config_error": self.config_error or "",
            "port_config": self.cfg.get("port"),
            "modules": self.modules(),
            "goals": self.goals(),
            "short_tasks": self.short_tasks(),
            "daiban": self.daiban(),
            "logs": _logs,
            "clients": self.clients(_logs),
            "manual": self.manual(),
        }
        if self.root_error:
            base.update({"meta": {}, "rules": [], "clauses": [], "conflicts": [],
                         "errors": [self.root_error], "gates": None})
            return base
        base["meta"] = self.meta()
        r = self.rules()
        base.update({k: r[k] for k in ("rules", "file_rows", "clauses", "conflicts", "errors")})
        tasks = self.tasks()
        _man = self.manual()
        manual_map = _man.get("map", {})
        manual_verdict = {i["key"]: i.get("verdict", "auto") for i in _man.get("items", [])}
        # 统一健康检查 key：与桌面端同一口径（b_check / b_defect / b_log）。
        # 三条一律读真数据源：最后一次 check 的结论、缺陷台账未闭环数、当日日志条数。
        # 不用「有条款就算台账干净」这类代理条件——那种写法永远 100%，是假绿。
        _dft = self.defects()
        _chk = self.last_check()
        _today = time.strftime("%Y-%m-%d")
        _lg = self.logs(limit=500)
        _today_logs = sum(1 for x in (_lg.get("list") or []) if str(x.get("date")) == _today)
        checks = [
            {"key": "b_check", "machine": bool(_chk.get("ok")),
             "label": "最近自检已人工核实",
             "detail": _chk.get("conclusion") or _chk.get("error") or ""},
            {"key": "b_defect", "machine": bool(_dft.get("clean")),
             "label": "缺陷台账已人工核实",
             "detail": ("%d/%d 未闭环" % (_dft.get("open", 0), _dft.get("total", 0)))
                       if _dft.get("configured") else (_dft.get("error") or "")},
            {"key": "b_log", "machine": _today_logs > 0,
             "label": "当日日志已人工核实",
             "detail": "今日 %d 条" % _today_logs},
        ]
        for c in checks:
            over = bool(manual_map.get(c["key"]))
            c["manual"] = over
            c["verdict"] = manual_verdict.get(c["key"], "auto")
            c["ok"] = c["machine"] or over
        passed = sum(1 for c in checks if c["ok"])
        base["health"] = {"score": round(passed * 100 / len(checks)),
                          "passed": passed, "total": len(checks), "checks": checks,
                          "note": "人工勾选可覆盖机器判据；被覆盖项标「人工」"}
        base["gates"] = self.run_engine() if run_gates else None
        return base


# ------------------------------------------------------------------
# HTTP
# ------------------------------------------------------------------
class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    console: Console = None  # 由 serve 注入

    def log_message(self, *a):  # 静默：不让访问日志淹没终端
        pass

    # ---------- 工具 ----------
    def _send(self, code, body: bytes, ctype="text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _download(self, text, filename):
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", 'attachment; filename="%s"' % filename)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _static(self, name):
        p = HERE / name
        if name not in STATIC_FILES or not p.is_file():
            self._send(404, b"not found")
            return
        ctype = {"html": "text/html; charset=utf-8", "png": "image/png"}.get(
            name.rsplit(".", 1)[-1], "application/octet-stream")
        self._send(200, p.read_bytes(), ctype)

    def _same_origin(self):
        # 只允许本机页面带自定义头调用写接口：浏览器跨站请求会先预检，而我们不回应 CORS
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            return False
        return self.headers.get("X-XTGL-Setup") == "1"

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > 2_000_000:
                return {}
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:  # noqa: BLE001
            return {}

    # ---------- GET ----------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path, q = parsed.path, urllib.parse.parse_qs(parsed.query)
        c = self.console
        try:
            if path == "/api/overview":
                self._json(c.overview(run_gates=not ("fast=1" in self.path)))
            elif path == "/api/env":
                self._json(c.env_report((q.get("root") or [""])[0]))
            elif path == "/api/clauses":
                self._json(c.rules_of_file((q.get("file") or [""])[0], (q.get("layer") or [None])[0]))
            elif path == "/api/doc":
                self._json(c.doc((q.get("name") or [""])[0]))
            elif path == "/api/tasks":
                self._json(c.tasks())
            elif path == "/api/modules":
                self._json(c.modules())
            elif path == "/api/packages":
                self._json(c.packages_view())
            elif path == "/api/goals":
                self._json(c.goals())
            elif path == "/api/ai/config":
                self._json(c.ai_config())
            elif path == "/api/defects":
                self._json(c.defect_rows())
            elif path == "/api/projects":
                self._json(c.projects())
            elif path == "/api/renwu":
                self._json(c.renwu())
            elif path == "/api/metrics":
                self._json(c.metrics())
            elif path == "/api/oss":
                self._json(c.oss())
            elif path == "/api/gates":
                self._json(c.gates_all())
            elif path == "/api/jieru":
                self._json(c.jieru())
            elif path == "/api/paths":
                self._json(c.paths_map())
            elif path == "/api/archive":
                self._json(c.archive())
            elif path == "/api/logdays":
                self._json(c.logdays())
            elif path == "/api/logday":
                self._json(c.logday_read((q.get("date") or [""])[0]))
            elif path == "/api/recent":
                self._json(c.recent())
            elif path == "/api/export":
                k = (q.get("kind") or ["goals"])[0]
                self._download(c.export_markdown(k),
                               "xtgl_export_%s_%s.md" % (re.sub(r"[^A-Za-z0-9_-]", "", k),
                                                        time.strftime("%Y%m%d")))
            elif path == "/api/health":
                self._json(c.health_page({"deep": (q.get("deep") or [""])[0] in ("1", "true", "True")}))
            elif path == "/api/health/rules":
                self._json(c.health_rules())
            elif path == "/api/access":
                self._json(c.access())
            elif path == "/api/search":
                self._json(c.clause_search((q.get("q") or [""])[0]))
            elif path == "/api/jieru/runs":
                self._json(c.jieru_runs())
            elif path == "/api/config":
                self._json(c.settings_view())
            elif path == "/api/anomaly":
                self._json(c.anomaly())
            elif path == "/api/ai/probe":
                self._json(c.ai_probe((q.get("base") or [""])[0]))
            elif path == "/api/ai/export":
                self._download(c.ai_report_export(), "xtgl_ai_report_%s.md" % time.strftime("%Y%m%d_%H%M%S"))
            elif path == "/api/detail":
                self._json(c.detail((q.get("board") or [""])[0], (q.get("id") or [""])[0]))
            elif path == "/api/goals/export":
                self._download(c.goals_export(),
                               "xtgl_goals_%s.md" % time.strftime("%Y%m%d"))
            elif path in ("/setup", "/setup.html"):
                self._static("setup.html")
            elif path in ("/", "/index.html"):
                self._static("index.html")
            elif path == "/favicon.png":
                self._static("favicon.png")
            elif path in ("/tutorial", "/tutorial.html"):
                self._static("tutorial.html")
            elif path == "/api/manual":
                self._json(c.manual())
            elif path == "/api/snapshot":
                import importlib.util as _ilu
                _sp = HERE / "snapshot.py"
                if not _sp.is_file():
                    self._json({"state": u"状态未知",
                                "note": u"缺 snapshot.py（核心件清单里有名、盘上无件）"})
                else:
                    _spec = _ilu.spec_from_file_location("xtgl_snapshot", str(_sp))
                    _m = _ilu.module_from_spec(_spec)
                    _spec.loader.exec_module(_m)
                    self._json(_m.build())
            elif path == "/i18n.js":
                self._static("i18n.js")
            else:
                self._send(404, b"not found")
        except ConfigError as e:
            # 配置类错误是「这里没填对」，不是服务端坏了——400 才不会被前端当成故障
            self._json({"error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001
            self._json({"error": "服务端异常：%s" % e}, 500)

    # ---------- POST ----------
    def do_POST(self):
        if not self._same_origin():
            self._json({"error": "拒绝：写接口仅限本机页面调用"}, 403)
            return
        parsed = urllib.parse.urlparse(self.path)
        payload = self._body()
        c = self.console
        try:
            if parsed.path == "/api/setup/save":
                self._json(c.save_config(payload))
            elif parsed.path == "/api/setup/scaffold":
                self._json(c.scaffold(payload))
            elif parsed.path == "/api/setup/task":
                self._json(c.create_task(payload))
            elif parsed.path == "/api/setup/pick":
                self._json(pick_directory())
            elif parsed.path == "/api/manual":
                self._json(c.set_manual(payload.get("key"), payload.get("ok"),
                                        payload.get("label"), payload.get("verdict")))
            elif parsed.path == "/api/ai/config":
                self._json(c.save_ai_config(payload))
            elif parsed.path == "/api/ai/test":
                self._json(c.ai_test())
            elif parsed.path == "/api/project/status":
                self._json(c.save_project(payload))
            elif parsed.path == "/api/task/status":
                self._json(c.save_task_status(payload))
            elif parsed.path == "/api/task/stub":
                self._json(c.create_liudang_stub(payload))
            elif parsed.path == "/api/health/rules":
                self._json(c.save_health_rules(payload))
            elif parsed.path == "/api/health/computer":
                self._json(c.computer_health(payload))
            elif parsed.path == "/api/export/save":
                self._json(c.save_export(payload))
            elif parsed.path == "/api/oss/check":
                self._json(c.oss_check(payload))
            elif parsed.path == "/api/ai/enable":
                self._json(c.set_ai_enabled(payload.get("enabled")))
            elif parsed.path == "/api/anomaly/scan":
                self._json(c.anomaly_scan(payload))
            elif parsed.path == "/api/ai/diagnose":
                self._json(c.ai_diagnose(payload))
            elif parsed.path == "/api/detail":
                self._json(c.save_detail(payload.get("board"), payload.get("id"),
                                         payload.get("req"), payload.get("prompt"),
                                         payload.get("by")))
            elif parsed.path == "/api/task/add":
                self._json(c.add_task(payload))
            elif parsed.path == "/api/task/delete":
                self._json(c.delete_task(payload))
            else:
                self._json({"error": "未知接口"}, 404)
        except ConfigError as e:
            self._json({"error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001
            self._json({"error": "服务端异常：%s" % e}, 500)


def pick_directory():
    """本机目录选择框；不可用时让用户手填。"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="选择 XTGL 项目目录")
        root.destroy()
        return {"path": path or ""}
    except Exception as e:  # noqa: BLE001
        return {"error": "目录选择框不可用，请手动输入路径：%s" % e}


# ------------------------------------------------------------------
# 启动
# ------------------------------------------------------------------
def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="XTGL 通用控制台")
    ap.add_argument("--root", default=None, help="项目根目录（覆盖配置）")
    ap.add_argument("--demo", action="store_true", help="使用内置演示项目")
    ap.add_argument("--port", type=int, default=None, help="起始端口")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG), help="配置文件路径")
    ap.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = ap.parse_args(argv)

    console = Console(Path(args.config), cli_root=args.root, demo=args.demo)
    Handler.console = console

    start = args.port or (console.cfg.get("port") or 8804)
    httpd = None
    used = None
    for p in range(int(start), int(start) + 40):
        try:
            httpd = http.server.ThreadingHTTPServer(("127.0.0.1", p), Handler)
            used = p
            break
        except OSError:
            continue
    if httpd is None:
        print("端口 %d 起 40 个均被占用" % start)
        return 1
    url = "http://127.0.0.1:%d/" % used
    print("=" * 56)
    print(" %s · 控制台" % console.cfg.get("title"))
    print(" 页面 %s" % url)
    print(" 项目根 %s" % (console.root or "（未配置，请打开页面按向导设置）"))
    print(" 内核 %s · Python %s" % (CORE_VERSION, sys.version.split()[0]))
    print(" 浏览器 %s" % ("Chrome" if find_chrome() else "系统默认"))
    print(" Ctrl+C 退出")
    print("=" * 56)
    if not args.no_browser:
        threading.Timer(0.6, lambda: open_browser(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        httpd.server_close()
    return 0


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
    try: sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
    raise SystemExit(main())
