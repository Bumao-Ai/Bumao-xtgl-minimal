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

"""Reverse test — 反证：坏规则集必须让已注册闸门转红，恢复后必须转绿。

零规则版（裁定04）本机 10_rac/rules/ 为空，没有可损坏的真件；旧版直接改写
rules/r01_core.json 的做法因此失效（目标文件不存在），且 engine 已随 D1 外迁到
HX/kernel/bumao_core。本版改为：把 examples/r01_core.json 复制进临时目录，
让子进程把 rules_db.RULES_DIR 指到那里再导入 wrapper，取真注册的 G04 判定。
全程不碰本仓任何文件，损坏只发生在沙箱里。
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

import harness  # noqa: F401  （harness 已把 10_rac 放进 sys.path）
import rules_db as dbm

_RAC = os.path.dirname(os.path.abspath(dbm.__file__))
SRC = os.path.join(_RAC, "examples", "r01_core.json")

_CHILD = (
    "import json,sys,os;"
    "sys.path.insert(0, %r);"
    "import rules_db as dbm;"
    "dbm.RULES_DIR = %r;"
    "import BumaoXTGL_Minimal_v01 as w;"
    "import engine as core;"
    "g = dict((gid, fn) for gid, fn, _ in core._get_b_gates());"
    "ok, note = g['G04']();"
    "print(json.dumps({'ok': bool(ok), 'note': note}))"
)


def _g04(rules_dir):
    """在子进程里以 rules_dir 为规则目录跑一次真闸门，返回 (ok, note)。"""
    code = _CHILD % (_RAC, rules_dir)
    p = subprocess.run([sys.executable, "-c", code], cwd=_RAC,
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if p.returncode != 0:
        return False, "child rc=%d %s" % (p.returncode, (p.stderr or "").strip()[-200:])
    try:
        d = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        return False, "child output unparsable: %r" % p.stdout[-200:]
    return d["ok"], d["note"]


def _corrupt(dst):
    """在沙箱副本里造一个重复条款号——与旧版同样的坏法，但只坏在临时目录。"""
    with io.open(dst, encoding="utf-8") as f:
        z = json.loads(f.read())
    dup = dict(z["clauses"][1])
    dup["id"] = z["clauses"][0]["id"]
    dup["root"] = dup["id"].split("(")[0]
    z["clauses"].append(dup)
    with io.open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(z, ensure_ascii=False, indent=1))


def main():
    r = harness.Runner("reverse test (corrupt -> red -> restore -> green)")
    tmp = tempfile.mkdtemp(prefix="xtgl_reverse_")
    dst = os.path.join(tmp, "r01_core.json")
    try:
        shutil.copyfile(SRC, dst)
        original = io.open(dst, "rb").read()

        ok, note = _g04(tmp)
        r.case("baseline pristine -> G04 GREEN", lambda: (ok, note))

        _corrupt(dst)
        ok, note = _g04(tmp)
        r.case("corrupt duplicate-id -> G04 RED", lambda: ((not ok), note))

        shutil.copyfile(SRC, dst)
        ok, note = _g04(tmp)
        r.case("after restore -> GREEN again", lambda: (ok, note))

        r.case("sandbox restored byte-identical",
               lambda: (io.open(dst, "rb").read() == original, "bytes match"))

        r.case("repo files untouched by this suite",
               lambda: (not os.path.exists(os.path.join(_RAC, "rules", "r01_core.json")),
                        "10_rac/rules 仍为空"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    n, npass, nf = r.counts()
    print("\n%d cases / %d pass / %d fail" % (n, npass, nf))
    sys.exit(1 if nf else 0)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
