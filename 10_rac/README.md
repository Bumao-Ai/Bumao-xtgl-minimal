# Bumao XTGL Minimal

![version](https://img.shields.io/badge/version-0.10-blue)
![python](https://img.shields.io/badge/python-3.12.14-blue)
![deps](https://img.shields.io/badge/deps-stdlib%20only-brightgreen)
![gates](https://img.shields.io/badge/gates-28%20passing-brightgreen)

> **The gate kernel is bundled inside this repository.** This repository carries the
> edition layer (entry script, guards, renderer, rules/views) plus the A-block gate
> kernel `engine.py` in `kernel/bumao_core`, as specified by `HOST_CONTRACT.md`.
> The entry script resolves it as `../kernel/bumao_core` relative to `10_rac`, so a
> plain clone runs as-is. If the directory is missing, the entry fails closed with a
> single line `[FATAL] missing gate kernel: no engine.py under ../kernel/bumao_core ...`
> and exit code 2 -- no traceback. Restore it by overwriting `kernel/bumao_core/`
> with the whole directory from the `bumao-core` repository; see
> *Repository layout -> Kernel placement* below.

A **rules-as-code governance layer for AI agents**. You write your agent's
operating rules once, as plain JSON (the single source of truth). Everything
humans and tools read is *derived* from that JSON, edits go through a guarded
block API, and a strict gate suite proves the whole thing is consistent --
including a *reverse test* that deliberately breaks the rules and watches the
gates go red, then green again.

Zero third-party runtime dependencies: **Python 3.12.14, standard library only**.

---

## Privacy & No telemetry

Bumao XTGL Minimal runs **entirely locally**:

- It only reads your local rule files (`rules/` directory).
- It **does not access the network**, does not upload, and does not collect any usage data.
- No telemetry, no crash reporting, no analytics scripts, no phone-home.

---

## What problem this solves

When an AI agent runs unattended, three things tend to go wrong:

1. The "rules" live in scattered markdown and prompts, drift, and nobody knows
   which copy is authoritative.
2. A risky action (shutdown, format, recursive delete, registry write,
   download-and-execute) slips through because the guard code exists but is
   never actually wired onto the execution path.
3. Tests pass by construction -- the suite only ever runs on a healthy repo, so
   it can never tell you whether a gate actually *catches* a break.

Bumao XTGL Minimal addresses all three:

| Module | Idea |
| --- | --- |
| `rules_db.py` | `rules/*.json` is the **single source of truth** — in this edition `rules/` is intentionally empty and `examples/*.json` carries the 28 template clauses. Structural validation (unique ids, contiguous blocks, no empty clauses, refs resolve). |
| `render.py` | Derived views under `views/` are generated, never hand-edited. Rendering twice gives **byte-identical** output. The version number lives only in `meta.json`. |
| `edit.py` | The **only** way to change rules: block-level API (`insert_after_block`, `append_body`, ...). You never touch the clauses list by index. |
| `BumaoXTGL_Minimal_v01.py` + shared kernel | The entry injects this edition's `rules_db` adapter and calls `kernel/bumao_core/engine.py` (one kernel, shared by all editions); `check --strict` runs a **28-check** suite (**A1–A11 + A13 + G01–G16**). A gate that cannot run its check reports **red**, never silent green. |
| `output_guard.py` | L3 high-risk intent review. `enforce()` **hard-blocks** (raises) on an unauthorized dangerous payload. |
| `capability.py` | L4 capability whitelist: read/write/exec tiers, **default deny** for anything unregistered. |
| `pretool/` | A host-side **PreToolUse adapter** (stdio JSON) that runs L4 -> L3 -> an audited one-time escape token before a tool call executes. |

---

## Install

No install needed. Clone and run:

```bash
git clone -b v0.12 https://github.com/Bumao-Ai/bumao-xtgl-minimal.git
cd bumao-xtgl-minimal
python --version        # needs 3.12+
```

There are no required packages. `requirements.txt` is intentionally empty of
runtime deps (you may add optional ones there).

## Quick start

```bash
# 1. render the derived views from the JSON source
python render.py write

# 2. run the strict gate suite (28 gates; A10/A13 are denied without an approval ledger)
python BumaoXTGL_Minimal_v01.py check --strict

# 3. run the tests (unit + reverse test)
python tests/test_output_guard.py
python tests/test_capability.py
python tests/test_pretool.py
python tests/test_render.py
python tests/test_reverse.py
```

The public repository ships no internal approval ledger (`30_taizhang/shenpi_jilu.txt`),
so **A10** and **A13** (version-change authorisation / authorising quote) are
**explicitly denied (DENY)** here — the result is FAIL, not PASS and not a waiver.
"Red by design" only means no same-day authorisation credential is shipped with the
public repository. The gates fail loud rather than being handed an empty approval
sample; all other gates should be green.

`BumaoXTGL_Minimal_v01.py` commands (the entry point injects this edition's
`rules_db` adapter, then dispatches to the shared kernel):

```bash
python BumaoXTGL_Minimal_v01.py whoami           # identity + version + counts
python BumaoXTGL_Minimal_v01.py check            # gate summary
python BumaoXTGL_Minimal_v01.py check --strict   # gates; exit 1 if anything is red
python BumaoXTGL_Minimal_v01.py audit            # clause / chapter inventory
python BumaoXTGL_Minimal_v01.py show 2.1         # print one clause
python BumaoXTGL_Minimal_v01.py bump --level L2  # print the next version
python BumaoXTGL_Minimal_v01.py selftest         # engine-level self check
python BumaoXTGL_Minimal_v01.py refresh          # placeholder in this edition
```

Measured on 2026-11-05 against this zero-rules edition, because "the CLI exists" is not
the same claim as "it does what the line says": `whoami` reports `0 clauses across 0
chapters`; `audit` prints all-zero counters and exits 0; `show 2.1` exits 1 with
`clause 2.1 not found` (nothing is live); `selftest` prints `selftest完成（引擎3/8）` and
still exits 0 (5 of its 8 checks need live clauses); `refresh` prints
`refresh placeholder (no render module)` — re-render here is `python render.py write`;
and `bump` **only prints** the next version, it never writes `meta.json` and never
re-renders, so the version point stays a manual, recorded edit.

---

## 30-second demo: watch the gates go red, then green

The fastest way to trust the gates is to watch one fail on purpose. `rules/` ships empty,
so `demo/break_it.py` first walks the documented injection path -- copies `examples/r*.json`
into `rules/`, re-renders, and only then measures the baseline:

```bash
python demo/break_it.py                              # inject -> ALL PASS -> break clause 2.5
python BumaoXTGL_Minimal_v01.py check --strict      # -> gates red, exit 1
python demo/fix_it.py                                # restore from examples/, re-render
python BumaoXTGL_Minimal_v01.py check --strict      # -> ALL PASS (28 gates), exit 0
python demo/fix_it.py --uninject                     # shipped state again: rules/ empty
```

Measured on 2026-11-05, breaking clause 2.5 turns five gates red: **A2** (duplicate clause
id), **G04** / **G05** (this edition's uniqueness and root-consistency gates), **G10** (views
drift, because `break_it.py` deliberately does not re-render) and **G16** -- with a live
duplicate in the set, the reverse test's "live set stays clean" precondition no longer holds.
Both scripts drive the suite through this edition's entry point; neither imports the kernel,
which lives outside this directory and exposes no `gates()` API. Neither script touches a
`rules/` file that does not match its `examples/` twin -- a rule pack you wrote yourself is
never demo dust.

The in-suite reverse test still runs while `rules/` is empty: `G16` clones a two-clause
fixture in memory, duplicates one id, and requires `duplicate_ids()` to report the break.
`A1` reconciles the `zero_rules` declaration against the filesystem, but only halfway. With
nothing loadable in `rules/`, any stray `.json` there is a FAIL (measured 2026-11-05:
`rules_json=1` -> A1 red, 1/27 gates red). A *loadable* chapter, by contrast, turns A1 back
green through its first branch even though `meta.json` still declares zero rules (measured:
`1 ch / 5 cls`, A1 PASS; the gates that went red were A7 and G10, 2/27). Closing that gap
would be a new gate criterion, not a wording fix, and is tracked as a separate architectural decision.

---

## Rules shipped: none -- `examples/` carries 28 template clauses

No rules ship in `rules/` -- this edition runs with zero effective clauses.
`examples/r*.json` carries **5 chapter files** and **28 clauses** as a
replaceable template pack; copy what you need into `rules/` to inject rules, and
the machinery (render, gates, guard) does not care about the wording, only
about the shape.

| Ch. | File | Chapter title | Clause ids | # clauses |
| --- | --- | --- | --- | --- |
| 1 | `examples/r01_core.json` | 1. Core Principles | 1.1 – 1.6 | 6 |
| 2 | `examples/r02_safety.json` | 2. Safe Execution | 2.1 – 2.5 | 5 |
| 3 | `examples/r03_editing.json` | 3. Editing the Rules | 3.1 – 3.5 | 5 |
| 4 | `examples/r04_verify.json` | 4. Verification Gates | 4.1 – 4.4 | 4 |
| 5 | `examples/r05_working.json` | 5. Working Agreement | 5.1 – 5.8 | 8 |
| | | | | **Total** | **28** |

Derived views (`views/v01_core.txt` … `views/v05_working.txt`, plus
`views/FULL.txt`, `views/CATALOG.txt`, `views/AGENTS.md`) are regenerated by
`render.py` from these JSON files. Never hand-edit them.

---

## Gate table: 28 gates (A1–A11 + A13 + G01–G16)

`python BumaoXTGL_Minimal_v01.py check --strict` runs 28 gates in order: the shared
kernel contributes the A-block (A1–A11 + A13), this edition's wrapper contributes the G-block
(G01–G16). A gate that cannot run its check reports **red** (fail-loud), never silent green.

| Gate | What it proves |
| --- | --- |
| A1 | **rules loadable** -- chapters and clauses parse, **or** `meta.json` declares `zero_rules` and `rules/` really holds no `.json` file (the declaration is reconciled against the directory, not trusted on its word). |
| A2 | **unique clause ids** -- no duplicate clause id anywhere in the loaded set. |
| A3 | **contiguous blocks** -- child clauses sit directly after their parent block. |
| A4 | **no broken refs** -- every inline cross-reference resolves to a real id or root. |
| A5 | **no shell clauses** -- no clause whose body says nothing. |
| A6 | **version syntax** -- `meta.json` `version` matches `N.N` or `N.N.N`. |
| A7 | **chapter numbering** -- chapter numbers run `0..n-1` with no gap. |
| A8 | **chapter titles** -- each chapter title's leading number equals its chapter number. |
| A9 | **kernel + entry hygiene** -- every kernel `.py` plus this entry script compile, carry no UTF-8 BOM, and every kernel-side `.json` parses. |
| A10 | **version-change authorisation** -- a same-day approval entry carries the authorising quote and the stated version matches the approved one. |
| A11 | **rule source reachable** -- every declared rule source path resolves. |
| G01 | **meta present** -- `name` and `version` exist in `meta.json`. |
| G02 | **semver version** -- `version` matches `major.minor.patch`. |
| G03 | **all rule files parse** -- every `rules/*.json` is valid JSON; this edition ships none, so the gate passes on the `zero_rules` declaration (A1 is what keeps that declaration honest). |
| G04 | **unique clause ids** -- no duplicate clause ids across chapters. |
| G05 | **root/id consistent** -- `root` equals `id` with any child suffix stripped. |
| G06 | **clause shape** -- every clause carries the required keys (`id`, `root`, `title`). |
| G07 | **blocks contiguous** -- child clauses sit directly after their parent; no inserted sibling in between. |
| G08 | **no empty clauses** -- no shell / placeholder clauses that say nothing. |
| G09 | **inline refs resolve** -- inline cross-references point at real clause ids. |
| G10 | **views in sync with SSOT** -- derived `views/` match the rules JSON byte-for-byte. |
| G11 | **version injected** -- the version string from `meta.json` appears in every derived view. |
| G12 | **render idempotent** -- rendering twice produces byte-identical output. |
| G13 | **L3 guard blocks / differentiates** -- `output_guard` blocks a shutdown payload, allows a clean payload, and `enforce()` raises on the blocked one. |
| G14 | **L4 whitelist default-deny** -- unknown tools are denied, read-tier tools allowed, exec-tier blocked. |
| G15 | **PreToolUse adapter** -- the stdio adapter denies bash, allows read, and denies unknown tool names. |
| G16 | **reverse: broken fixture detected** -- a duplicate id fabricated in memory is caught while the live set stays clean (proves the suite is not green-by-construction; the fixture is synthetic here because `rules/` is empty). |

With `rules/` empty, the clause-scoped gates (A2–A5 and G03–G09) evaluate over a zero-clause
set and pass vacuously. That is the honest cost of a zero-rules edition, and it is why
A1 reconciles the declaration against the filesystem and why G16 fabricates its own
broken fixture: the suite must still be able to catch a real break.
---

## Writing your own rules

`examples/r*.json` are the example templates (5 chapter files, 28 clauses);
`rules/` ships empty. Copy them in or write your own; each file has this shape:

```json
{
 "ch": 1,
 "file": "v01_core.txt",
 "chapter_title": "1. Core Principles",
 "pre": ["optional intro lines"],
 "clauses": [
   { "id": "1.1", "root": "1.1",
     "title": "1.1 Be honest about limits.",
     "body": ["optional extra lines of explanation"] }
 ]
}
```

Rules:
- `id` must be unique. `root` is `id` with any `(n)` child suffix stripped.
- Children (`1.1(1)`, `1.1.2`) must sit **directly after** their parent --
  blocks are contiguous.
- Every clause must say something (no placeholder/shell clauses).
- To add or change a rule, use `edit.py`, **never** hand-edit `views/`:

```python
import edit
edit.insert_after_block(1, "1.5", ["1.6 My new rule text here."])
edit.append_body(1, "1.6", "An extra explanation line.")
```

Then:

```bash
python render.py write
python BumaoXTGL_Minimal_v01.py check --strict
```

If either step fails, the change is not accepted.

---

## Wiring the PreToolUse guard onto a host

`pretool/stdio_adapter.py` is the plug. A host that exposes a PreToolUse /
pre-tool hook points the hook command at it:

```bash
python /path/to/bumao-xtgl-minimal/pretool/stdio_adapter.py
```

The host pipes a JSON request on stdin and reads a JSON decision on stdout
(exit code `0` = allow, `3` = deny):

```json
{"tool_name": "Bash", "tool_input": {"command": "rm -rf build/"}}
```

```json
{"decision": "deny", "allow": false, "tier": "exec", "reason": "L3 blocked: ..."}
```

For Claude Code style hosts, add `--proto claude` and you get the
`hookSpecificOutput.permissionDecision` shape.

**The audited escape hatch.** When the user explicitly authorizes one specific
dangerous call, issue a one-time token and pass it with that call:

```python
from pretool import issue_token
tok = issue_token("user authorized one cleanup run")   # reason is mandatory
# host request: {"tool_name":"Bash","tool_input":{...},"escape_token": tok}
# -> allowed exactly once, then consumed, appended to logs/escape_audit.txt
```

### Honest boundary (please read)

This guard enforces **its own runtime's** entry points and the hosts that
actually attach the PreToolUse plug. **If a host does not expose an external
hook surface or an MCP stdio channel, Bumao XTGL Minimal cannot physically take over that
host's bare shell.** That is host-level permission, and we state it plainly
rather than claiming "everything is locked down". L3 is rule review, not
semantic understanding; clever rewording can bypass the regexes. The real safety
comes from default-deny + asking + the audited escape hatch, not from an
exhaustive word list.

---

## Repository layout

```
bumao-xtgl-minimal/
  meta.json            version single point (name/version/effective)
  rules/               ships empty -- zero effective rules in this edition
  examples/r*.json     replaceable template pack (5 chapter files, 28 clauses)
  views/               derived, generated by render.py (do not hand-edit)
  BumaoXTGL_Minimal_v01.py  entry: whoami / check --strict / audit / show / bump / selftest
  ../kernel/bumao_core/engine.py      gate kernel (A1–A11 + A13) -- bundled at the repo root
  rules_db.py          load SSOT + structural validation
  render.py            SSOT -> views (idempotent)
  edit.py              block-only rule editing API
  output_guard.py      L3 high-risk review + enforce hard-block
  capability.py        L4 whitelist, default deny
  pretool/             host PreToolUse adapter (core/escape/stdio)
  demo/                break_it.py / fix_it.py -- gates go red, then green (injects examples/ first)
  tests/               unit tests + reverse test
  docs/TUTORIAL.md     step-by-step GitHub upload & usage tutorial
  logs/                runtime audit (gitignored)
```

**Kernel placement.** The kernel ships inside this repository at
`kernel/bumao_core` (a sibling of `10_rac`); the entry script imports it from
`../kernel/bumao_core` (wrapper line 13), so a fresh clone runs without any extra
step. The kernel has one upstream: the `bumao-core` repository. To update it,
overwrite `kernel/bumao_core/` with the whole directory from `bumao-core` -- no
per-file merging. If the copy is moved without the kernel, `check --strict` cannot
run: the entry prints one `[FATAL] missing gate kernel ...` line and exits 2
(verified on a kernel-less copy of this directory).

## License

Apache-2.0 -- see [LICENSE](LICENSE).

---

## 中文

# Bumao XTGL Minimal（中文）

![version](https://img.shields.io/badge/version-0.10-blue)
![python](https://img.shields.io/badge/python-3.12.14-blue)
![deps](https://img.shields.io/badge/deps-stdlib%20only-brightgreen)
![gates](https://img.shields.io/badge/gates-28%20passing-brightgreen)

> **闸门内核已内置在本仓库内。** 本仓库携带版别层（入口脚本、守卫、渲染器、规则／视图），以及 `kernel/bumao_core` 中的 A 段闸门内核 `engine.py`，规格见 `HOST_CONTRACT.md`。入口脚本按相对 `10_rac` 的 `../kernel/bumao_core` 解析它，因此直接 clone 即可运行。若该目录缺失，入口会以单行 `[FATAL] missing gate kernel: no engine.py under ../kernel/bumao_core ...` 失败关闭并返回退出码 2——不打印 traceback。将 `kernel/bumao_core/` 用 `bumao-core` 仓库的整个目录覆盖即可恢复；见下文 *仓库布局 -> 内核放置*。

面向 AI Agent 的**规则即代码治理层**。你把 Agent 的运行规则一次性写成纯 JSON（唯一事实来源）。人类与工具所读的一切都*派生*自该 JSON，编辑经由受保护的块级 API，严格的闸门套件证明整套内容一致——其中包含一个*反向测试*，它故意破坏规则并观察闸门变红、再变绿。

零第三方运行时依赖：**Python 3.12.14，仅标准库**。

---

## 隐私与无遥测

Bumao XTGL Minimal **完全本地**运行：

- 它只读取你本地的规则文件（`rules/` 目录）。
- 它**不访问网络**，不上传，也不收集任何使用数据。
- 无遥测、无崩溃上报、无分析脚本、无电话回连。

---

## 这解决什么问题

当 AI Agent 无人值守运行时，通常有三件事会出问题：

1. 所谓「规则」散落在各处的 markdown 与提示词里，会漂移，且没人知道哪一份是权威。
2. 危险动作（关机、格式化、递归删除、写注册表、下载并执行）会溜过去，因为守卫代码虽然存在，却从未真正接到执行路径上。
3. 测试因构造而通过——套件只在健康的仓库上运行，因此永远无法告诉你某个闸门是否真的*捕获*了一次破坏。

Bumao XTGL Minimal 三件都解决了：

| 模块 | 思路 |
| --- | --- |
| `rules_db.py` | `rules/*.json` 是**唯一事实来源**——本版中 `rules/` 故意为空，`examples/*.json` 携带 28 条模板条款。结构校验（id 唯一、块连续、无空条款、引用可解析）。 |
| `render.py` | `views/` 下的派生视图是生成的，绝不手工编辑。渲染两次得到**逐字节相同**的输出。版本号只存在于 `meta.json`。 |
| `edit.py` | 修改规则的**唯一**方式：块级 API（`insert_after_block`、`append_body`……）。你永远不按索引触碰 clauses 列表。 |
| `BumaoXTGL_Minimal_v01.py` + 共享内核 | 入口注入本版的 `rules_db` 适配器，并调用 `kernel/bumao_core/engine.py`（一个内核，由所有版别共享）；`check --strict` 运行**28 项检查**套件（**A1–A11 + A13 + G01–G16**）。无法运行自身检查的闸门报**红**，绝不静默变绿。 |
| `output_guard.py` | L3 高风险意图审查。对未授权的危险载荷，`enforce()` **硬阻断**（抛出异常）。 |
| `capability.py` | L4 能力白名单：读／写／执行三档，对任何未登记项**默认拒绝**。 |
| `pretool/` | 宿主侧的 **PreToolUse 适配器**（stdio JSON），在工具调用执行前依次跑 L4 -> L3 -> 一个受审计的一次性逃生令牌。 |

---

## 安装

无需安装。克隆并运行：

```bash
git clone -b v0.12 https://github.com/Bumao-Ai/bumao-xtgl-minimal.git
cd bumao-xtgl-minimal
python --version        # needs 3.12+
```

没有必需的软件包。`requirements.txt` 故意不列运行时依赖（你可以在其中添加可选项）。

## 快速开始

```bash
# 1. render the derived views from the JSON source
python render.py write

# 2. run the strict gate suite (28 gates; A10/A13 are denied without an approval ledger)
python BumaoXTGL_Minimal_v01.py check --strict

# 3. run the tests (unit + reverse test)
python tests/test_output_guard.py
python tests/test_capability.py
python tests/test_pretool.py
python tests/test_render.py
python tests/test_reverse.py
```

公开仓库不附带内部审批台账（`30_taizhang/shenpi_jilu.txt`），因此**A10** 与**A13**（版本变更授权／授权引文）在此被**显式拒绝（DENY）**——结果是 FAIL，不是 PASS，也不是豁免。所谓「设计上红」只意味着公开仓库不附带当日的授权凭证。闸门会在失败时大声报错，而不是被塞进一份空的审批样本；其余闸门应为绿色。

`BumaoXTGL_Minimal_v01.py` 命令（入口点注入本版的 `rules_db` 适配器，然后分派到共享内核）：

```bash
python BumaoXTGL_Minimal_v01.py whoami           # identity + version + counts
python BumaoXTGL_Minimal_v01.py check            # gate summary
python BumaoXTGL_Minimal_v01.py check --strict   # gates; exit 1 if anything is red
python BumaoXTGL_Minimal_v01.py audit            # clause / chapter inventory
python BumaoXTGL_Minimal_v01.py show 2.1         # print one clause
python BumaoXTGL_Minimal_v01.py bump --level L2  # print the next version
python BumaoXTGL_Minimal_v01.py selftest         # engine-level self check
python BumaoXTGL_Minimal_v01.py refresh          # placeholder in this edition
```

于 2026-11-05 针对这个零规则版实测，因为「CLI 存在」并不等同于「它确实做了那行所说的事」：`whoami` 报告 `0 clauses across 0 chapters`；`audit` 打印全零计数并退出 0；`show 2.1` 以 `clause 2.1 not found` 退出 1（没有任何条款生效）；`selftest` 打印 `selftest完成（引擎3/8）` 且仍退出 0（其 8 项检查中有 5 项需要生效条款）；`refresh` 打印 `refresh placeholder (no render module)`——此处的重新渲染是 `python render.py write`；`bump` **只打印**下一个版本，它从不写 `meta.json`，也从不重新渲染，因此版本点仍是一次手动、有记录的编辑。

---

## 30 秒演示：看闸门变红，再变绿

要信任闸门，最快的方法是故意让它失败一次。`rules/` 发布时为空，因此 `demo/break_it.py` 先走文档化的注入路径——把 `examples/r*.json` 复制进 `rules/`，重新渲染，然后才测量基线：

```bash
python demo/break_it.py                              # inject -> ALL PASS -> break clause 2.5
python BumaoXTGL_Minimal_v01.py check --strict      # -> gates red, exit 1
python demo/fix_it.py                                # restore from examples/, re-render
python BumaoXTGL_Minimal_v01.py check --strict      # -> ALL PASS (28 gates), exit 0
python demo/fix_it.py --uninject                     # shipped state again: rules/ empty
```

于 2026-11-05 实测，破坏条款 2.5 会让五个闸门变红：**A2**（重复条款 id）、**G04** / **G05**（本版的唯一性与根一致性闸门）、**G10**（视图漂移，因为 `break_it.py` 故意不重新渲染）以及 **G16**——集合中存在一个生效的重复项后，反向测试的「生效集合保持干净」这一前置条件不再成立。两个脚本都通过本版的入口点驱动套件；二者都不导入内核，内核住在本目录之外且不暴露 `gates()` API。两个脚本都不触碰与其 `examples/` 对应件不匹配的 `rules/` 文件——你自己写的规则包永远不会变成演示粉尘。

当 `rules/` 为空时，套件内的反向测试仍会运行：`G16` 在内存中克隆一个双条款的夹具，复制其中一个 id，并要求 `duplicate_ids()` 报告该破坏。`A1` 会把 `zero_rules` 声明与文件系统对账，但只对账了一半。当 `rules/` 中没有任何可加载内容时，其中任何游离的 `.json` 都是 FAIL（2026-11-05 实测：`rules_json=1` -> A1 变红，1/27 个闸门变红）。相反，一个*可加载*的章会通过其第一个分支让 A1 重新变绿，即使 `meta.json` 仍声明零规则（实测：`1 ch / 5 cls`，A1 PASS；变红的闸门是 A7 与 G10，2/27）。填补这个缺口会是一条新的闸门判据，而不是一次措辞修改，并作为一项单独的架构决策跟踪。

---

## 随包发布的规则：无——`examples/` 携带 28 条模板条款

`rules/` 中不发布任何规则——本版以零生效条款运行。`examples/r*.json` 以可替换的模板包形式携带 **5 个章文件**与 **28 条条款**；把你需要的复制进 `rules/` 即可注入规则，而机制（渲染、闸门、守卫）不关心措辞，只关心形状。

| 章 | 文件 | 章标题 | 条款 id | 条款数 |
| --- | --- | --- | --- | --- |
| 1 | `examples/r01_core.json` | 1. Core Principles | 1.1 – 1.6 | 6 |
| 2 | `examples/r02_safety.json` | 2. Safe Execution | 2.1 – 2.5 | 5 |
| 3 | `examples/r03_editing.json` | 3. Editing the Rules | 3.1 – 3.5 | 5 |
| 4 | `examples/r04_verify.json` | 4. Verification Gates | 4.1 – 4.4 | 4 |
| 5 | `examples/r05_working.json` | 5. Working Agreement | 5.1 – 5.8 | 8 |
| | | | | **合计** | **28** |

派生视图（`views/v01_core.txt` … `views/v05_working.txt`，加上 `views/FULL.txt`、`views/CATALOG.txt`、`views/AGENTS.md`）由 `render.py` 从这些 JSON 文件重新生成。绝不手工编辑它们。

---

## 闸门表：28 个闸门（A1–A11 + A13 + G01–G16）

`python BumaoXTGL_Minimal_v01.py check --strict` 按顺序运行 28 个闸门：共享内核贡献 A 段（A1–A11 + A13），本版的包装层贡献 G 段（G01–G16）。无法运行自身检查的闸门会报**红**（失败大声报错），绝不静默变绿。

| 闸门 | 它证明什么 |
| --- | --- |
| A1 | **规则可加载**——章与条款可解析，**或者** `meta.json` 声明 `zero_rules` 且 `rules/` 确实不含任何 `.json` 文件（该声明与目录对账，而非凭其字面采信）。 |
| A2 | **条款 id 唯一**——已加载集合中任何位置都没有重复的条款 id。 |
| A3 | **块连续**——子条款紧跟在它们的父块之后。 |
| A4 | **无断引用**——每个内联交叉引用都能解析到真实的 id 或根。 |
| A5 | **无空壳条款**——没有任何条款正文什么都不说。 |
| A6 | **版本语法**——`meta.json` 的 `version` 匹配 `N.N` 或 `N.N.N`。 |
| A7 | **章编号**——章号按 `0..n-1` 连续且无空缺。 |
| A8 | **章标题**——每个章标题的前导编号等于其章号。 |
| A9 | **内核 + 入口卫生**——每个内核 `.py` 加本入口脚本都能编译、不带 UTF-8 BOM，且每个内核侧 `.json` 都能解析。 |
| A10 | **版本变更授权**——一条当日审批条目携带授权引文，且所述版本与获批版本一致。 |
| A11 | **规则来源可达**——每个声明的规则来源路径都能解析。 |
| G01 | **meta 存在**——`meta.json` 中存在 `name` 与 `version`。 |
| G02 | **语义化版本**——`version` 匹配 `major.minor.patch`。 |
| G03 | **所有规则文件可解析**——每个 `rules/*.json` 都是合法 JSON；本版不发布任何规则文件，因此该闸门凭 `zero_rules` 声明通过（A1 才是让该声明保持诚实的那道）。 |
| G04 | **条款 id 唯一**——跨章没有重复的条款 id。 |
| G05 | **根／id 一致**——`root` 等于剥离任意子后缀后的 `id`。 |
| G06 | **条款形状**——每条条款都携带必需的键（`id`、`root`、`title`）。 |
| G07 | **块连续**——子条款紧跟其父条款；中间不插入同级项。 |
| G08 | **无空条款**——没有什么都不说的空壳／占位条款。 |
| G09 | **内联引用可解析**——内联交叉引用指向真实的条款 id。 |
| G10 | **视图与 SSOT 同步**——派生 `views/` 与规则 JSON 逐字节一致。 |
| G11 | **版本已注入**——来自 `meta.json` 的版本字符串出现在每个派生视图中。 |
| G12 | **渲染幂等**——渲染两次产生逐字节相同的输出。 |
| G13 | **L3 守卫阻断／区分**——`output_guard` 阻断关机载荷、放行干净载荷，且 `enforce()` 对被阻断者抛出异常。 |
| G14 | **L4 白名单默认拒绝**——未知工具被拒绝，读档工具被放行，执行档被阻断。 |
| G15 | **PreToolUse 适配器**——stdio 适配器拒绝 bash、放行读取、拒绝未知工具名。 |
| G16 | **反向：破损夹具被检出**——在内存中伪造的重复 id 被捕获，同时生效集合保持干净（证明套件不是靠构造变绿；由于 `rules/` 为空，此处的夹具是合成的）。 |

当 `rules/` 为空时，条款范围的闸门（A2–A5 与 G03–G09）在零条款集合上评估并空泛通过。这就是零规则版的诚实代价，也正是 A1 要将声明与文件系统对账、G16 要伪造自身破损夹具的原因：套件仍必须能够捕获一次真实的破坏。

---

## 编写你自己的规则

`examples/r*.json` 是示例模板（5 个章文件，28 条条款）；`rules/` 发布时为空。把它们复制进来或编写你自己的；每个文件具有这种形状：

```json
{
 "ch": 1,
 "file": "v01_core.txt",
 "chapter_title": "1. Core Principles",
 "pre": ["optional intro lines"],
 "clauses": [
   { "id": "1.1", "root": "1.1",
     "title": "1.1 Be honest about limits.",
     "body": ["optional extra lines of explanation"] }
 ]
}
```

规则：
- `id` 必须唯一。`root` 是剥离任意 `(n)` 子后缀后的 `id`。
- 子项（`1.1(1)`、`1.1.2`）必须**紧跟在**其父项之后——块是连续的。
- 每条条款都必须说点什么（无占位／空壳条款）。
- 要新增或修改规则，使用 `edit.py`，**绝不**手工编辑 `views/`：

```python
import edit
edit.insert_after_block(1, "1.5", ["1.6 My new rule text here."])
edit.append_body(1, "1.6", "An extra explanation line.")
```

然后：

```bash
python render.py write
python BumaoXTGL_Minimal_v01.py check --strict
```

任何一步失败，改动都不被接受。

---

## 把 PreToolUse 守卫接到宿主上

`pretool/stdio_adapter.py` 就是插头。暴露 PreToolUse / pre-tool 钩子的宿主把钩子命令指向它：

```bash
python /path/to/bumao-xtgl-minimal/pretool/stdio_adapter.py
```

宿主通过 stdin 管道送入 JSON 请求，并从 stdout 读取 JSON 决定（退出码 `0` = 放行，`3` = 拒绝）：

```json
{"tool_name": "Bash", "tool_input": {"command": "rm -rf build/"}}
```

```json
{"decision": "deny", "allow": false, "tier": "exec", "reason": "L3 blocked: ..."}
```

对于 Claude Code 风格的宿主，加上 `--proto claude` 即可得到 `hookSpecificOutput.permissionDecision` 形状。

**受审计的逃生通道。** 当用户显式授权某一次具体的危险调用时，签发一个一次性令牌，并随该调用传入：

```python
from pretool import issue_token
tok = issue_token("user authorized one cleanup run")   # reason is mandatory
# host request: {"tool_name":"Bash","tool_input":{...},"escape_token": tok}
# -> allowed exactly once, then consumed, appended to logs/escape_audit.txt
```

### 诚实边界（请读）

此守卫只对**其自身运行时**的入口点，以及真正挂上 PreToolUse 插头的宿主生效。**如果某个宿主不暴露外部钩子面或 MCP stdio 通道，Bumao XTGL Minimal 无法在物理上接管该宿主的裸 shell。** 那是宿主级权限，我们如实陈述，而不是宣称「一切都被锁死」。L3 是规则审查，不是语义理解；巧妙改写措辞可以绕过正则。真正的安全来自默认拒绝 + 询问 + 受审计的逃生通道，而不是一份穷尽的词表。

---

## 仓库布局

```
bumao-xtgl-minimal/
  meta.json            version single point (name/version/effective)
  rules/               ships empty -- zero effective rules in this edition
  examples/r*.json     replaceable template pack (5 chapter files, 28 clauses)
  views/               derived, generated by render.py (do not hand-edit)
  BumaoXTGL_Minimal_v01.py  entry: whoami / check --strict / audit / show / bump / selftest
  ../kernel/bumao_core/engine.py      gate kernel (A1–A11 + A13) -- bundled at the repo root
  rules_db.py          load SSOT + structural validation
  render.py            SSOT -> views (idempotent)
  edit.py              block-only rule editing API
  output_guard.py      L3 high-risk review + enforce hard-block
  capability.py        L4 whitelist, default deny
  pretool/             host PreToolUse adapter (core/escape/stdio)
  demo/                break_it.py / fix_it.py -- gates go red, then green (injects examples/ first)
  tests/               unit tests + reverse test
  docs/TUTORIAL.md     step-by-step GitHub upload & usage tutorial
  logs/                runtime audit (gitignored)
```

**内核放置。** 内核随本仓库放在 `kernel/bumao_core`（`10_rac` 的同级）；入口脚本从 `../kernel/bumao_core` 导入它（包装层第 13 行），因此全新 clone 无需任何额外步骤即可运行。内核只有一个上游：`bumao-core` 仓库。要更新它，用 `bumao-core` 的整个目录覆盖 `kernel/bumao_core/`——不做逐文件合并。如果未带内核地移动副本，`check --strict` 无法运行：入口打印一行 `[FATAL] missing gate kernel ...` 并退出 2（已在本目录的无内核副本上验证）。

## 许可证

Apache-2.0——见 [LICENSE](LICENSE)。
