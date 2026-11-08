# Changelog

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
