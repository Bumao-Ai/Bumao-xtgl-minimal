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

"""三端日志分组一致性核对：控制台接口 vs 桌面读取逻辑。

用法：
    python verify_log_grouping.py            # 核对 8804
    python verify_log_grouping.py --port 8804
"""
import argparse
import json
import re
import sys
import io
import urllib.request

# 强制 UTF-8 输出（Windows 终端默认 GBK）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

LOGKEY_RE = re.compile(r"/40_renwu/([^/]+)/")


def log_key(detail: str) -> str:
    """与控制台 index.html 的 logKey()、桌面 _logKey() 同一口径。"""
    p = (detail or "").replace("\\", "/")
    p = re.sub(r"/+", "/", p)
    m = LOGKEY_RE.search(p)
    return m.group(1) if m else "其他记录"


def client_name(who: str) -> str:
    """与控制台 clientName()、桌面 _clientName() 同一口径。"""
    s = (who or "").strip()
    if not s:
        return "未标注"
    s = re.sub(r"（.*$", "", s).strip()
    s = re.sub(r"\s+deepseek.*$", "", s, flags=re.I).strip()
    return s or "未标注"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8804)
    args = ap.parse_args()

    url = "http://127.0.0.1:%d/api/overview?fast=1" % args.port
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    logs = (data.get("logs") or {}).get("list") or []
    if not logs:
        print("没有日志数据（logs.list 为空）")
        return 1

    tree: dict[str, dict[str, list[dict]]] = {}
    for r in logs:
        proj = log_key(r.get("detail", ""))
        who = client_name(r.get("who", ""))
        tree.setdefault(proj, {}).setdefault(who, []).append(r)

    print("端口 %d · 共 %d 条登记 · %d 个项目" % (args.port, len(logs), len(tree)))
    print("=" * 66)
    for proj in sorted(tree):
        who_map = tree[proj]
        total = sum(len(v) for v in who_map.values())
        flag = "  <<< 未归入 40_renwu" if proj == "其他记录" else ""
        print("\n[项目] %s  （%d 条）%s" % (proj, total, flag))
        for who in sorted(who_map):
            rows = sorted(who_map[who], key=lambda x: (x.get("date", ""), x.get("time", "")))
            print("  └─ 客户端 %s  （%d 条）" % (who, len(rows)))
            for r in rows:
                exists = "[OK]" if r.get("exists") else "[MISSING]"
                print("       %s %s  留档:%s  %s"
                      % (r.get("date", ""), r.get("time", ""), exists,
                         (r.get("what", "") or "")[:34]))

    orphan = tree.get("其他记录")
    print("\n" + "=" * 66)
    if orphan:
        print("FAIL：有 %d 条没归到项目（detail 不含 40_renwu）" % sum(len(v) for v in orphan.values()))
        return 2
    print("PASS：全部 %d 条都归到了 40_renwu 下的项目" % len(logs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
