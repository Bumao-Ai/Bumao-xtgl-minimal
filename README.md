# Bumao XTGL · Minimal

![license](https://img.shields.io/badge/license-Apache--2.0-blue)
![python](https://img.shields.io/badge/python-3.12%2B-blue)
![rules](https://img.shields.io/badge/rules-0-lightgrey)
![checks](https://img.shields.io/badge/checks-28-brightgreen)
![runtime](https://img.shields.io/badge/runtime-stdlib%20only-informational)

Zero-rule skeleton of Bumao XTGL: 28 structural checks, your rules, stdlib only. Start here if you want to write your own rule set.

**What it is** — the smallest edition: structure and verdict engine, no rules.
**Who it's for** — people who already have rules of their own and only want the machinery.
**What it solves** — the cost of building a compliance skeleton from zero.

![check --strict](docs/screens/check-terminal.png)
*Real output of `check --strict` on a fresh clone (2/28 red: A10/A13, not applicable without an approval ledger).*

## Quick start (30 seconds)

```bash
git clone -b <release-tag> https://github.com/Bumao-Ai/Bumao-xtgl-minimal.git
cd Bumao-xtgl-minimal/10_rac
python BumaoXTGL_Minimal_v01.py whoami
python BumaoXTGL_Minimal_v01.py check --strict   # exit code is the verdict
```

Add your rules by dropping chapter files into `10_rac/` and following the loader in `rules_db.py`; `render.py` regenerates the views. `zero_rules` is declared in `00_meta/meta.json`, so the skeleton passes without inventing content.

`<release-tag>` is the tag of the release you install; see Releases and verify with `SHA256SUMS`.

## Proof of work

| Item | Value | Source |
|---|---|---|
| Commits at `v0.12` | 6 | `git rev-list --count v0.12` |
| Last commit | 2026-11-08 | `git log -1 --date=short` |
| Rules | 0 (declared) | `check --strict` → `0 ch / 0 cls (zero_rules declared)` |
| Check items | 28 | `check --strict` conclusion (`2/28 gates red`) |
| Reverse cases | 5 | `10_rac/tests/test_reverse.py`; last run 5/5 pass |
| Defect ledger | 0 real closed items | `30_taizhang/quexian_taizhang.txt` holds 2 sanitized sample rows |
| Releases | 4 tags, `v0.1` → `v0.12`, all 2026-11-08 | `git tag` |
| Changelog | [CHANGELOG.md](CHANGELOG.md) | — |

`A10` and `A13` are red on a public clone by design: they check an approval ledger and a quoted authorization, and this edition ships no approval samples. They are marked *not applicable*, not passed.

## 中文

- **是什么**：不带规则的最小发行版（骨架）。
- **给谁用**：已有自己的规矩、只要判定引擎与结构的人。
- **解决什么**：从零搭一套合规骨架的成本。

快速开始沿用上方命令块。`A10／A13` 在公开仓按「不适用」处理：本版不带审批样本，所以它们红着，而不是被算作通过。

## Roadmap (0.2 — in progress)

1. **执行前约束** — 动手前提交意图，由内核先判。
2. **执行中监管** — 过程中持续检查，而不是只在结束时判一次。
3. **执行后审计** — 把操作、依据、结果、异常四者关联成一条可追溯链。

Status: **in progress**. Nothing here is claimed as shipped.

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
| Authorization | A10, A13 | approval ledger and quoted authorization; **not applicable** in the public edition |
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
assets/       logos
docs/screens/ screenshots used in this README
```

## Docs / License

- Changelog: [`CHANGELOG.md`](CHANGELOG.md)
- Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md) · DCO: [`DCO`](DCO)
- Security: [`SECURITY.md`](SECURITY.md)
- License: Apache-2.0, see [`LICENSE`](LICENSE)
- Trademark boundary: [`TRADEMARK.md`](TRADEMARK.md)

Copyright 2026 Bumao
