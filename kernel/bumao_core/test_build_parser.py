# -*- coding: utf-8 -*-
"""回归用例：build_parser() 曾重复注册 check 子命令。

缺陷（v0.2.0-beta.3／beta.4 均存在）：
    sub.add_parser("check"); check_p = sub.add_parser("check") ...
调用 build_parser() 立即抛：
    argparse.ArgumentError: argument command: conflicting subparser: check
当时 main() 另建了一份解析器，所以 CLI 表面可用，缺陷只在公开 API 上暴露。

本用例锁三件事：
  1. build_parser() 能构建，且 7 个子命令各出现一次（重复注册会直接抛异常）；
  2. 文档声明的参数确实注册到了解析器（--quick／--full／--kernel）；
  3. main() 与 build_parser() 共用同一份解析器（main 能接受 --quick，不抛 SystemExit）。

运行：python test_build_parser.py （退出码 0＝ALL PASS）
"""
import argparse
import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engine  # noqa: E402


def _subcommands(parser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return list(action.choices.keys())
    return []


class BuildParserTest(unittest.TestCase):
    def test_build_parser_has_no_duplicate_subcommand(self):
        parser = engine.build_parser()  # 旧代码在这一行抛 ArgumentError
        names = _subcommands(parser)
        self.assertEqual(sorted(names), sorted(
            ["whoami", "check", "audit", "bump", "show", "selftest", "refresh"]))
        self.assertEqual(len(names), len(set(names)), "存在重复子命令：%s" % names)

    def test_documented_flags_are_registered(self):
        p = engine.build_parser()
        self.assertTrue(p.parse_args(["check", "--quick"]).quick)
        self.assertTrue(p.parse_args(["check", "--strict"]).strict)
        self.assertTrue(p.parse_args(["whoami", "--full"]).full)
        self.assertTrue(p.parse_args(["selftest", "--kernel"]).kernel)
        self.assertEqual(p.parse_args(["bump"]).level, "L1")
        self.assertEqual(p.parse_args(["show", "0.1"]).cid, "0.1")

    def test_main_accepts_quick_flag(self):
        """main() 若另建解析器，--quick 会被 argparse 判非法并以 SystemExit(2) 退出。"""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = engine.main(["check", "--quick"])
        self.assertIn("[ERROR]", buf.getvalue())
        self.assertEqual(rc, 1)  # 未注入 rules_db，命令失败但参数解析成功

    def test_main_without_command_prints_help(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = engine.main([])
        self.assertEqual(rc, 2)
        self.assertIn("whoami", buf.getvalue())


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BuildParserTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("ALL PASS" if result.wasSuccessful() else "FAILED")
    sys.exit(0 if result.wasSuccessful() else 1)
