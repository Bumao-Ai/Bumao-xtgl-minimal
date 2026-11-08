# -*- coding: utf-8 -*-
"""反向用例：结论为 FAIL 时，不带 --strict 也必须返回非 0。

背景（2026-11-08）：个人端 check 在 3 项红时打印 FAIL 却返回 rc=0，
票面 rc 与结论相反。本件造一个必红场景，只调非 strict 入口，断言 rc 非 0。

必红场景：给内核喂一份条款编号重复的假规则库，A2「条款id唯一」必红。
本件不读写任何账本／凭据，只验返回值。
"""
import io
import os
import sys
import tempfile
import contextlib


class _FakeRulesDb(object):
    def __init__(self, rules_dir):
        self.RULES_DIR = rules_dir
        self.ZH = ""
        self.ROOT = rules_dir
        self.HERE = rules_dir
        self.enforce_decl = None

    def load(self):
        return {
            "meta": {"version": "1.0", "name": "reverse-case", "zero_rules": False},
            "chapters": [{"ch": 0, "chapter_title": "0. 反向用例", "n": 2}],
            "clauses": [
                {"id": "0.1", "ch": 0, "title": "重复一", "body": ["甲"], "broken_refs": []},
                {"id": "0.1", "ch": 0, "title": "重复二", "body": ["乙"], "broken_refs": []},
            ],
        }

    def index(self, db):
        return db

    def load_meta(self):
        return self.load()["meta"]

    def dup_ids(self, db):
        ids = [c.get("id") for c in db["clauses"]]
        return sorted({i for i in ids if ids.count(i) > 1})

    def block_broken(self, clauses):
        return []

    def shell_clauses(self, db):
        return []


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import engine

    tmp = tempfile.mkdtemp(prefix="rc_case_")
    with io.open(os.path.join(tmp, "dummy.json"), "w", encoding="utf-8") as f:
        f.write("{}")
    engine.configure(_FakeRulesDb(tmp))
    engine.register("B99", lambda: (False, "反向用例：本闸恒红"), "反向用例恒定红闸")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = engine.cmd_check(strict=False)
    out = buf.getvalue()

    ok_fail_line = "FAIL (" in out
    if rc != 0 and ok_fail_line:
        print("PASS 反向用例：非 strict 恒红场景 rc=%d，结论行含 FAIL (" % rc)
        return 0
    print("FAIL 反向用例：rc=%r，结论行含 FAIL (=%s)" % (rc, ok_fail_line))
    print(out[-600:])
    return 1


if __name__ == "__main__":
    sys.exit(main())
