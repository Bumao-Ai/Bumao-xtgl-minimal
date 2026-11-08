# Changelog

## 0.14 — 2026-11-08

本版是功能版：编码修复与启动器兼容。This release ships real behaviour changes: encoding-safe entry points and a portable launcher.

- **编码修复** — `10_rac/BumaoXTGL_Minimal_v01.py`、`20_view/web/serve.py`、`20_view/web/xtgl_core.py` 的 `__main__` 现在对 `stdout`／`stderr` 都做 `reconfigure(encoding="utf-8", errors="replace")`，与内核 `serve.py`／`xtgl_core.py` 同款。改前：控制台在 cp936 或缺少字形时遇到罕见字符会抛 `UnicodeEncodeError` 中断检查；改后：降级为替换字符，继续跑完。Before: a rare glyph could abort the run with `UnicodeEncodeError`. Now: it is replaced instead of raising.
- **启动器** — `20_view/web/qidong_kongzhitai.bat` 在调用任何解释器之前设置 `PYTHONUTF8=1`／`PYTHONIOENCODING=utf-8`；位置探测顺序改为 `py -3 → python3 → python → python_path.txt`（本地覆盖放在最后），每个候选都用 `-c "import sys"` 实跑，Windows Store 的假 `python.exe`（退出码 9009）被跳过。The launcher probes `py -3 → python3 → python → python_path.txt`, runs each candidate, and rejects the Store stub.
- **未变** — 0 条生效规则、28 个闸门、应用内版本 `0.10`、目录结构与视图均未改动。Rules, gate count, in-app version and layout are unchanged.
- **文档与维护状态** — README 顶部加 `Status: maintenance pause`／「状态：维护暂停，稳定可用」；新增 `RETURN_HERE.md` 作为恢复迭代的冷启动入口（先看三样、先动 `CHANGELOG.md`）。README status line and `RETURN_HERE.md` added.
- **R6／R8 不在本仓** — 本仓没有 `B22` 闸门，反向用例 `10_rac/tests/test_reverse.py` 本来就在沙箱副本上跑（5 例，未改动）。`B22` 的内容哈希划界与 28 例影子副本反向套件属 community／personal，不在本仓虚标。No `B22` here; the 5 reverse cases already run on sandbox copies and are unchanged.
- **已知红项** — `check --strict` 两次运行均为 `2/28`（`A10`、`A13`，公开仓不发审批册，按设计红）。Known reds: `A10`/`A13` by design.

## 0.13 — 2026-11-08

本版为口径与结构对齐，并补上内核契约（无新增界面功能）。This release aligns naming and structure and ships the kernel contract; it adds no UI feature.

- Before: gate `A10` threw `FileNotFoundError` on a fresh clone, because `kernel_contract.json` was not in the repository. Now: `kernel/kernel_contract.json` and `kernel/contract_test.py` ship at the path `engine.py` reads (`kernel/`, one level above `kernel/bumao_core/`), so `A10` reports the missing approval ledger instead of crashing.
- Before: README opened with gate IDs and directory internals. Now: first screen answers what/who/problem, English first, Chinese below.
- Before: no screenshots. Now: two real captures in `docs/screens/` — `check --strict` output and the shipped tree.
- Before: install command followed `main`. Now: pinned to `v0.13` and verified with `SHA256SUMS`.
- Check count corrected to 28 (the `27 gates` line was wrong); a fresh clone reports `2/28 gates red` (A10/A13, not applicable).
- No rule or gate change: `git diff v0.12..HEAD -- 10_rac/ 20_view/` is empty; the only `kernel/` additions are the contract pair above.

## 0.1.1 — 2026-11-08

内置内核。

- 本仓新增 `kernel/bumao_core/`，克隆后无需外部 `bumao-core` 即可运行。
- 入口脚本内核查找路径由 `../../kernel/bumao_core` 改为 `../kernel/bumao_core`。
- 内核维护方式：以 `bumao-core` 为唯一源头，整目录覆盖本仓副本。

## 0.1 — 2026-11-08

首次公开发布。

- 骨架版：0 条生效规则，附 28 条示例模板／5 章结构。
- 六层工作区与真身／视图／台账三层资产。
- 四步改规则流程与全量闸门自检。
- Web 控制台（默认 8804）。
