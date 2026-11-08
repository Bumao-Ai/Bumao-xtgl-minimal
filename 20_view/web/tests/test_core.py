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

"""XTGL 内核测试（标准库 unittest，零依赖）

覆盖评审建议的七类场景：
1. 空配置启动            5. 文件损坏后的恢复
2. 错误配置恢复          6. 任务状态持久化
3. 任意路径读取          7. 引擎不可用时的降级
4. 规则修改后重新判定
外加：路径优先级、三层合并、内核层防覆盖、中文/空格路径、配置保存、演示模式、清单一致性。
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

os.environ["XTGL_NO_LOCAL_OVERLAY"] = "1"

WEB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WEB))
import xtgl_core as core  # noqa: E402


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_project(base: Path, name="工作 区（测试）", with_engine=False):
    root = base / name
    write_json(root / "00_meta" / "meta.json",
               {"schema": 1, "name": name, "version": "0.2", "effective": "2026-11-02"})
    write_json(root / "rules" / "r01.json",
               {"clauses": [{"id": "D1", "title": "D1 默认条款", "body": ["正文"]}]})
    (root / "40_renwu" / "t1").mkdir(parents=True)
    (root / "40_renwu" / "t1" / "benci_gongcheng.txt").write_text(
        "任务：测试任务\n执行者：unit-test\n【索引尾开始】\n【索引尾结束】\n", encoding="utf-8")
    (root / "10_rac").mkdir(exist_ok=True)
    if with_engine:
        (root / "10_rac" / "engine.py").write_text("print('PASS demo')\n", encoding="utf-8")
    return root


def make_config(path: Path, root: Path = None, goals=None, health_fixture=False, **kw):
    # 下面的 cmd 只服务夹具：make_project(with_engine=True) 会在临时目录里生成同名的
    # 假引擎。它不是可照抄的命令——现行真实入口见 10_rac/README.md 与门面文档。
    cfg = {
        "schema": 2,
        "title": "T",
        "subtitle": "",
        "project_root": "" if root is None else str(root),
        "goals": "" if goals is None else str(goals),
        "port": 8890,
        "engine": {"cwd": "10_rac", "cmd": ["python", "engine.py"], "timeout": 10},
        "rules": {
            "core": {"dir": "core_rules", "enabled": kw.get("core", False)},
            "default": {"dir": "rules", "enabled": True},
            "user": {"dir": "rules_user", "enabled": kw.get("user", False)},
        },
    }
    if health_fixture:
        # 健康三项的机器判据各有真数据源，夹具把它们做成绿的：
        # 自检日志目录里放一份写明 ALL PASS 的夹具日志，台账夹具只含已闭环行。
        chk = path.parent / "checklogs"
        chk.mkdir(parents=True, exist_ok=True)
        (chk / ("check_%s_120000.log" % time.strftime("%Y%m%d"))).write_text(
            "[结论] ALL PASS（测试夹具，非真实自检记录）\n", encoding="utf-8")
        dft = path.parent / "defects_fixture.txt"
        dft.write_text("| Q9001 | 2026-11-07 | 夹具 | 夹具条款 | 测试夹具 | 低 | 无 | 已闭环 | 丁 |\n",
                      encoding="utf-8")
        cfg["check_log_dir"] = str(chk)
        cfg["defects"] = str(dft)
    write_json(path, cfg)
    return path


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()


class TestPath(Base):
    def test_cli_root_wins(self):
        p = make_project(self.base)
        cfg = self.base / "cfg.json"
        make_config(cfg, self.base / "other")
        c = core.Console(cfg, cli_root=str(p))
        self.assertEqual(c.root, p.resolve())
        self.assertIsNone(c.root_error)

    def test_env_beats_config(self):
        p = make_project(self.base)
        cfg = self.base / "cfg.json"
        make_config(cfg, self.base / "other")
        old = os.environ.get("XTGL_PROJECT_ROOT")
        os.environ["XTGL_PROJECT_ROOT"] = str(p)
        try:
            c = core.Console(cfg)
            self.assertEqual(c.root, p.resolve())
        finally:
            if old is None:
                os.environ.pop("XTGL_PROJECT_ROOT", None)
            else:
                os.environ["XTGL_PROJECT_ROOT"] = old

    def test_relative_config_root(self):
        p = make_project(self.base)
        cfg = self.base / "cfg.json"
        make_config(cfg, p)
        c = core.Console(cfg)
        self.assertEqual(c.root, p.resolve())

    def test_chinese_and_space_path(self):
        p = make_project(self.base, name="中文 目录 带空格")
        cfg = self.base / "cfg.json"
        make_config(cfg, p)
        c = core.Console(cfg)
        self.assertIsNone(c.root_error)
        o = c.overview(run_gates=False)
        self.assertFalse(o["setup_required"])
        self.assertEqual(o["meta"]["version"], "0.2")

    def test_empty_config_gives_setup_required(self):
        cfg = self.base / "missing.json"
        c = core.Console(cfg, cli_root=str(self.base / "nope"))
        self.assertTrue(c.root_error)
        o = c.overview(run_gates=False)
        self.assertTrue(o["setup_required"])
        self.assertIn("不存在", o["setup_reason"])


class TestConfig(Base):
    def test_corrupt_config_does_not_crash(self):
        cfg = self.base / "cfg.json"
        cfg.write_text("{ this is not json", encoding="utf-8")
        p = make_project(self.base)
        c = core.Console(cfg, cli_root=str(p))
        self.assertTrue(c.config_error)
        o = c.overview(run_gates=False)
        self.assertFalse(o["setup_required"])  # 命令行根可用，仍然能工作

    def test_corrupt_meta_reports_error(self):
        p = make_project(self.base)
        (p / "00_meta" / "meta.json").write_text("{bad", encoding="utf-8")
        cfg = self.base / "cfg.json"
        make_config(cfg, p)
        c = core.Console(cfg)
        self.assertIsNotNone(c.root_error)
        o = c.overview(run_gates=False)
        self.assertTrue(o["setup_required"])

    def test_save_config_and_reload(self):
        fake_web = self.base / "proj" / "20_view" / "web"
        fake_web.mkdir(parents=True)
        p = fake_web.parent.parent
        write_json(p / "00_meta" / "meta.json",
                   {"schema": 1, "name": "项目A", "version": "0.1"})
        (p / "rules").mkdir(exist_ok=True)
        (p / "40_renwu").mkdir(exist_ok=True)
        cfg = fake_web / "web_config.json"
        # Q121 起 normalize_config 不再猜入口：夹具先落一份合法配置，
        # 本例要验的是 save_config 写回与重载，不是缺配置的降级路径。
        make_config(cfg, p)
        old = core.HERE
        core.HERE = fake_web
        try:
            c = core.Console(cfg, cli_root=str(p))
            res = c.save_config({"root": str(p), "rules": {
                "core": {"dir": "core_rules", "enabled": True},
                "default": {"dir": "rules", "enabled": True},
                "user": {"dir": "", "enabled": False}}})
            self.assertTrue(res["ok"])
            # 项目根在自身树内 → 配置记空串，可整体搬家
            self.assertEqual(res["project_root"], "")
            saved = json.loads(cfg.read_text(encoding="utf-8"))
            self.assertEqual(saved["schema"], 2)
            self.assertTrue(saved["rules"]["core"]["enabled"])
            self.assertIsNone(c.root_error)
        finally:
            core.HERE = old


class TestRules(Base):
    def _console(self):
        p = make_project(self.base)
        write_json(p / "core_rules" / "core.json",
                   {"clauses": [{"id": "C1", "title": "C1 内核", "body": []}]})
        write_json(p / "rules" / "r02.json",
                   {"clauses": [{"id": "D2", "title": "D2 默认", "body": []}]})
        write_json(p / "rules_user" / "u.json",
                   {"clauses": [
                       {"id": "C1", "title": "C1 用户越权", "body": []},
                       {"id": "U1", "title": "U1 用户新增", "body": []},
                       {"id": "D2", "title": "D2 用户覆盖", "body": []},
                   ]})
        cfg = self.base / "cfg.json"
        make_config(cfg, p, core=True, user=True)
        return core.Console(cfg), p

    def test_core_cannot_be_overridden(self):
        c, _ = self._console()
        r = c.rules()
        by_id = {x["id"]: x for x in r["clauses"]}
        self.assertEqual(by_id["C1"]["title"], "C1 内核")
        self.assertEqual(by_id["C1"]["layer"], "core")
        self.assertTrue(any(x["id"] == "C1" and x["layer"] == "user" for x in r["conflicts"]))

    def test_user_overrides_default(self):
        c, _ = self._console()
        by_id = {x["id"]: x for x in c.rules()["clauses"]}
        self.assertEqual(by_id["D2"]["layer"], "user")
        self.assertEqual(by_id["D2"]["title"], "D2 用户覆盖")

    def test_user_adds_new_clause(self):
        c, _ = self._console()
        by_id = {x["id"]: x for x in c.rules()["clauses"]}
        self.assertIn("U1", by_id)

    def test_rules_change_is_seen_next_call(self):
        c, p = self._console()
        self.assertIn("U1", [x["id"] for x in c.rules()["clauses"]])
        write_json(p / "rules_user" / "u.json",
                   {"clauses": [{"id": "U2", "title": "U2 改过了", "body": []}]})
        ids = [x["id"] for x in c.rules()["clauses"]]
        self.assertIn("U2", ids)
        self.assertNotIn("U1", ids)

    def test_rules_of_file(self):
        c, _ = self._console()
        d = c.rules_of_file("core.json", "core")
        self.assertEqual(d["clauses"][0]["id"], "C1")
        self.assertEqual(c.rules_of_file("../secret.json")["clauses"], [])


class TestEngineAndTasks(Base):
    def test_missing_engine_degrades(self):
        p = make_project(self.base)
        cfg = self.base / "cfg.json"
        make_config(cfg, p)
        c = core.Console(cfg)
        g = c.run_engine()
        self.assertFalse(g["ok"])
        self.assertTrue(g["lines"])
        o = c.overview(run_gates=True)
        self.assertIsNotNone(o["gates"])
        self.assertEqual(o["meta"]["version"], "0.2")

    def test_engine_uses_sys_executable(self):
        p = make_project(self.base, with_engine=True)
        (p / "10_rac" / "engine.py").write_text(
            "print('  PASS  A1  ok')\n", encoding="utf-8")
        cfg = self.base / "cfg.json"
        make_config(cfg, p)
        c = core.Console(cfg)
        g = c.run_engine()
        self.assertEqual(g["exit_code"], 0)
        self.assertIn("PASS", g["lines"][0])

    def test_create_task_persists(self):
        p = make_project(self.base)
        cfg = self.base / "cfg.json"
        make_config(cfg, p)
        c = core.Console(cfg)
        r1 = c.create_task({"root": str(p), "name": "新任务 一", "goal": "跑通"})
        self.assertFalse(r1["existed"])
        self.assertTrue(Path(r1["path"]).is_file())
        r2 = core.Console(cfg).create_task({"root": str(p), "name": "新任务 一"})
        self.assertTrue(r2["existed"])
        names = [t["name"] for t in c.tasks()]
        self.assertIn("新任务 一", names)

    def test_scaffold_creates_minimal_project(self):
        target = self.base / "新 工作区"
        cfg = self.base / "cfg.json"
        make_config(cfg, target)
        c = core.Console(cfg, cli_root=str(target))
        r = c.scaffold({"root": str(target), "name": "新工作区"})
        self.assertIn("00_meta/meta.json", r["created"])
        self.assertTrue((target / "rules" / "r01_default.json").is_file())
        c2 = core.Console(cfg, cli_root=str(target))
        self.assertIsNone(c2.root_error)
        self.assertEqual(len(c2.rules()["clauses"]), 2)


class TestDemo(Base):
    def test_demo_mode(self):
        c = core.Console(demo=True)
        self.assertEqual(c.root, core.DEMO_DIR.resolve())
        self.assertIsNone(c.root_error)
        o = c.overview(run_gates=True)
        self.assertTrue(o["demo"])
        layers = {x["layer"]: x for x in o["rules"]}
        self.assertTrue(layers["core"]["enabled"])
        self.assertTrue(layers["user"]["enabled"])
        self.assertGreaterEqual(len(o["conflicts"]), 1)
        self.assertEqual(o["gates"]["exit_code"], 0)


class TestGoals(Base):
    TEXT = ("说明\n[G1]\n目标：测试目标\n阶段：阶段1\n状态：进行中\n进度：60\n"
            "关联项目：A、B\n关联文件：%s；%s\n下一步：做点什么\n")

    def test_parse(self):
        gs = core.parse_goals(self.TEXT % ("x", "y"))
        self.assertEqual(len(gs), 1)
        self.assertEqual(gs[0]["id"], "G1")
        self.assertEqual(gs[0]["目标"], "测试目标")

    def test_missing_file(self):
        cfg = self.base / "cfg.json"
        make_config(cfg, make_project(self.base))
        g = core.Console(cfg).goals()
        self.assertFalse(g["ok"])

    def test_load_and_export(self):
        f = self.base / "mubiao.txt"
        f.write_text(self.TEXT % (str(f), str(self.base / "nope.txt")), encoding="utf-8")
        cfg = self.base / "cfg.json"
        make_config(cfg, make_project(self.base), goals=f)
        c = core.Console(cfg)
        g = c.goals()
        self.assertTrue(g["ok"])
        self.assertEqual(g["count"], 1)
        self.assertEqual(g["list"][0]["progress"], 60)
        self.assertEqual(g["list"][0]["projects"], ["A", "B"])
        self.assertTrue(g["list"][0]["files"][0]["exists"])
        self.assertFalse(g["list"][0]["files"][1]["exists"])
        text = c.goals_export()
        self.assertIn("源文件", text)
        self.assertIn("G1", text)
        self.assertIn("缺失", text)


class TestManual(Base):
    def test_toggle_and_persist(self):
        old = core.MANUAL_PATH
        core.MANUAL_PATH = self.base / "manual.json"
        try:
            c = core.Console(demo=True)
            m = c.manual()
            self.assertTrue(m["ok"])
            # 夹具位 manual.json 不存在 → 回落 MANUAL_DEFAULT 的四项标准 key
            self.assertEqual(sorted(x["key"] for x in m["items"]),
                             sorted(["b_check", "b_defect", "b_log", "ack_open"]))
            # review_a 属历史 key，manual() 读时即丢弃；勾选要用现行 key
            c.set_manual("ack_open", True)
            m2 = c.manual()
            hit = [x for x in m2["items"] if x["key"] == "ack_open"][0]
            self.assertTrue(hit["ok"])
            self.assertTrue((self.base / "manual.json").is_file())
        finally:
            core.MANUAL_PATH = old

    def test_manual_overrides_machine(self):
        p = make_project(self.base)
        shutil.rmtree(p / "40_renwu")
        cfg = self.base / "cfg.json"
        make_config(cfg, p, health_fixture=True)
        old = core.MANUAL_PATH
        core.MANUAL_PATH = self.base / "manual2.json"
        try:
            c = core.Console(cfg)
            before = c.overview(run_gates=False)["health"]["score"]
            self.assertLess(before, 100)
            c.set_manual("b_log", True, "当日日志已人工核实")
            after = c.overview(run_gates=False)
            self.assertEqual(after["health"]["score"], 100)
            hit = [x for x in after["health"]["checks"] if x["key"] == "b_log"][0]
            self.assertTrue(hit["manual"])
        finally:
            core.MANUAL_PATH = old


class TestModules(Base):
    def test_manifest_passes(self):
        import module_check
        errs, mods = module_check.validate()
        self.assertEqual(errs, [])
        self.assertGreaterEqual(len(mods), 4)

    def test_overview_exposes_modules(self):
        c = core.Console(demo=True)
        o = c.overview(run_gates=False)
        self.assertTrue(o["modules"]["ok"])
        ids = [m["id"] for m in o["modules"]["modules"]]
        self.assertIn("gate", ids)

    def test_incompatible_module_is_flagged(self):
        self.assertTrue(core.core_compatible("^0.10"))
        self.assertFalse(core.core_compatible("^3.0"))


class TestManifest(unittest.TestCase):
    def test_manifest_matches_files(self):
        manifest = WEB / "core_manifest.json"
        self.assertTrue(manifest.is_file(), "缺 core_manifest.json")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(data["core_version"], core.CORE_VERSION)
        for name, digest in data["files"].items():
            fp = WEB / name
            self.assertTrue(fp.is_file(), "清单里的文件不存在：" + name)
            actual = hashlib.sha256(fp.read_bytes()).hexdigest()
            self.assertEqual(actual, digest, "内核文件与清单不一致：" + name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
