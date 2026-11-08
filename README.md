# Bumao XTGL · Minimal

Status: maintenance pause
状态：维护暂停，稳定可用

![license](https://img.shields.io/badge/license-Apache--2.0-blue)
![python](https://img.shields.io/badge/python-3.12%2B-blue)
![rules](https://img.shields.io/badge/rules-0-lightgrey)
![checks](https://img.shields.io/badge/checks-28-brightgreen)
![runtime](https://img.shields.io/badge/runtime-stdlib%20only-informational)

> **Two version spaces** — the in-app version in `00_meta/meta.json` is `0.10`; the repository release tag is `v0.16`. They are two independent numbering spaces, not the same number.
> **两个版本空间** — 应用内版本（`00_meta/meta.json`）是 `0.10`；仓库发布 tag 是 `v0.16`。这是两个独立的编号空间，不是同一个数字。
>
> **Cold start** — to resume iteration, start from [`RETURN_HERE.md`](RETURN_HERE.md).
> **冷启动** — 恢复迭代从 [`RETURN_HERE.md`](RETURN_HERE.md) 开始。

Zero-rule skeleton of Bumao XTGL: 28 structural checks, your rules, stdlib only. Start here if you want to write your own rule set.

**What it is** — the smallest edition: structure and verdict engine, no rules.
**Who it's for** — people who already have rules of their own and only want the machinery.
**What it solves** — the cost of building a compliance skeleton from zero.

![check --strict](docs/screens/check-terminal.png)
*Real output of `check --strict` on a fresh clone (1/28 red: A10 — the shipped ledger template has zero entries, so it prints an explicit DENY, FAIL not PASS).*

## Quick start (30 seconds)

```bash
git clone -b v0.16 https://github.com/Bumao-Ai/Bumao-xtgl-minimal.git
cd Bumao-xtgl-minimal/10_rac
python BumaoXTGL_Minimal_v01.py whoami
python BumaoXTGL_Minimal_v01.py check --strict   # exit code is the verdict
```

Add your rules by dropping chapter files into `10_rac/` and following the loader in `rules_db.py`; `render.py` regenerates the views. `zero_rules` is declared in `00_meta/meta.json`, so the skeleton passes without inventing content.

`v0.16` is the tag this README was released with; see Releases and verify the zip with `SHA256SUMS`.

## Proof of work

| Item | Value | Source |
|---|---|---|
| Commits at `v0.16` | 15 | `git rev-list --count v0.16` |
| Last commit | 2026-11-09 | `git log -1 --date=short` |
| Rules | 0 (declared) | `check --strict` → `0 ch / 0 cls (zero_rules declared)` |
| Check items | 28 | `check --strict` conclusion (`1/28 gates red`) |
| Reverse cases | 5 | `10_rac/tests/test_reverse.py`; last run 5/5 pass |
| Defect ledger | 0 real closed items | `30_taizhang/quexian_taizhang.txt` holds 2 sanitized sample rows |
| Adapter cases | 10 | `10_rac/tests/test_pretool.py`; last run 10/10 pass (incl. bound-token refusal) |
| Releases | 8 tags, `v0.1` → `v0.16`, 2026-11-08 → 2026-11-09 | `git tag` |
| Changelog | [CHANGELOG.md](CHANGELOG.md) | — |

`A10` is red on a public clone by design: it needs a same-day authorized entry in `30_taizhang/shenpi_jilu.txt`, and this edition ships that file as a **structure template with zero entries**. With no parseable entry the gate is **explicitly denied (DENY)** — the result is FAIL, never PASS. "Red by design" means no same-day authorization credential ships here; it is not a waiver. The detail line now starts with `A10 判定=DENY` and names the policy (`deny`).

## 中文

- **是什么**：不带规则的最小发行版（骨架）。
- **给谁用**：已有自己的规矩、只要判定引擎与结构的人。
- **解决什么**：从零搭一套合规骨架的成本。

快速开始沿用上方命令块。`A10` 在没有当日授权条目时**显式判拒（DENY）**：本版随包的审批册是零条目结构模板，所以它红着，结果是 FAIL 而不是 PASS；「按设计红」只指公开仓不随附当日授权凭据，不等于豁免。detail 首段写 `A10 判定=DENY` 并标明策略 `deny`。

## Roadmap (0.2 — in progress)

1. **执行前约束** — 动手前提交意图，由内核先判。设计与沙盒原型已通，**未接入 live**。*（进行中）*
2. **执行中监管** — 过程中持续检查，而不是只在结束时判一次。设计与沙盒原型已通，**未接入 live**。*（进行中）*
3. **执行后审计** — 把操作、依据、结果、异常四者关联成一条可追溯链。设计与沙盒原型已通，**未接入 live**。*（进行中）*

Status: **in progress**。设计与沙盒原型已通，live 尚未接入；本节不声称已交付。

## Architecture

```mermaid
flowchart TB
  M[00_meta/meta.json<br/>zero_rules declared] --> E[10_rac engine]
  E --> R[rules/ · your chapters]
  E --> K[kernel/bumao_core]
  E --> V[20_view text views]
  K --> C{ALL PASS / FAIL}
  R --> C
```

## What gets checked

| Group | Checks | What it proves |
|---|---|---|
| Source structure | A1–A11, A13 | loader runs, IDs unique, blocks contiguous, references resolve, no empty clauses, entry compiles |
| Authorization | A10, A13 | approval ledger and quoted authorization; without a ledger → explicit **DENY** (FAIL), not a waiver |
| Kernel gates | G01–G09 | meta present, semver, rule files parse, IDs unique and consistent, clause shape, blocks, references |
| Views and guards | G10–G16 | views in sync, version injected, render idempotent, L3/L4 guards and adapter behave, reverse fixture detected |

Total: 12 structure checks + 16 kernel checks = **28 checks**.

## Layout

![Shipped tree](docs/screens/layout.png)
*Real tree of the shipped repository.*

```
00_meta/      meta.json (zero_rules, version)
10_rac/       engine entry, render.py, rules_db.py, rules/
20_view/      generated views
30_taizhang/  ledgers and baselines
90_lishi/     history
kernel/       bundled bumao_core
docs/screens/ screenshots used in this README
```

## Docs / License

- Changelog: [`CHANGELOG.md`](CHANGELOG.md)
- Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md) · DCO: [`DCO`](DCO)
- Security: [`SECURITY.md`](SECURITY.md)
- License: Apache-2.0, see [`LICENSE`](LICENSE)
- Trademark boundary: [`TRADEMARK.md`](TRADEMARK.md)

Copyright 2026 Bumao
