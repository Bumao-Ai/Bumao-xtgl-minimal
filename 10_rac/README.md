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

# 2. run the strict gate suite (28 gates; A10/A13 report missing in the public repo)
python BumaoXTGL_Minimal_v01.py check --strict

# 3. run the tests (unit + reverse test)
python tests/test_output_guard.py
python tests/test_capability.py
python tests/test_pretool.py
python tests/test_render.py
python tests/test_reverse.py
```

The public repository ships no internal approval ledger (`30_taizhang/shenpi_jilu.txt`),
so **A10** and **A13** (version-change authorisation / authorising quote) report
**missing** and are treated as **not applicable** here. The gates fail loud rather than
being handed an empty approval sample; all other gates should be green.

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
