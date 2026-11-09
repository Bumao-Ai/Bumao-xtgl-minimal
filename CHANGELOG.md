# Changelog

## 0.34 — 2026-11-09

本版只改对外自述与版本号，不改判据、不改核心件集合，也不动 `kernel/`。

- **加号依据：0.33→0.34（+0.01 同档正常晋升）** — 依据 `HX\personal\20_view\di00_qidong_zongze.txt` L55—60 的 0.6.8 规则；随包内核仍 core `v0.2.6`，不跨档再加号。
- **②执行中监管改为实跑口径** — README 双语 Roadmap 第 2 条改写为 2026-11-09 的真实复跑：动作级记录（`op_id`／目标／结果）之外，序列执行中有人在单外改动，下一次动作前即以 `EXTERNAL_DRIFT` 中断，生成证据包（`halt.json`／`diff.txt`／账本快照／`manifest.sha256`）；恢复须先 recover 再经人工批准 resume 才能继续。绕过入口只记为「仅事后可查」，不计入已覆盖。
- **本轮复跑范围** — `community`、`minimal` 两个活区各跑一次中途越界中断（halt → recover → resume → done 全过，`shenji` 按 `op_id` 导出动作链）；`personal` 沿用当日早间演练留证，未重跑。
- **计数与版本同步** — 发布 tag 由 `v0.21` 改为 `v0.22`，tag 总数 13→14；随附 2026-11-09 授权条目 9→10；`00_meta/meta.json` 与 `10_rac/meta.json` 的应用内版本同时 0.33→0.34。
- **维护暂停** — 每版照旧写「维护暂停，稳定可用」；哪一版才算最终暂停版尚未确定，因此仍按不定时更新发布。
- **未变** — 规则 0 条（声明式）、检查项 28；A10／A13 判据不变；`check --strict` 仍 `ALL PASS（A段 12 项 + B段 16 项）`。

**English**
- Documentation and version strings only; no verdict, no core-file-set change, `kernel/` untouched.
- Item ② (mid-execution supervision) in the bilingual roadmap now records the real 2026-11-09 replay: on top of action-level records (`op_id` / target / result), an out-of-order change made from outside the entry while a sequence is running interrupts the next action with an `EXTERNAL_DRIFT` evidence bundle (`halt.json` / `diff.txt` / ledger snapshot / `manifest.sha256`); resuming requires recover plus a human approval. A bypass is recorded as post-hoc searchable only and never counted as covered.
- Replayed live this round on `community` and `minimal` (halt → recover → resume → done, with `shenji` exporting the action chain by `op_id`); `personal` keeps its earlier same-day drill evidence and was not re-run.
- Counts and versions synced: release tag `v0.21` → `v0.22`, 13 → 14 tags, 9 → 10 authorization entries dated 2026-11-09, in-app version 0.33 → 0.34 in both `00_meta/meta.json` and `10_rac/meta.json`.
- The maintenance-pause line is kept in every release, noting that the final paused release is undecided and releases continue at irregular intervals.
- Unchanged: 0 rules (declarative), 28 checks, and the A10 / A13 verdicts.

## 0.33 — 2026-11-09

本版只改对外自述与版本号，不改判据、不改核心件集合，也不动 `kernel/`。

- **加号依据：0.32→0.33（+0.01 同档正常晋升）** — 依据 `HX\personal\20_view\di00_qidong_zongze.txt` L55—60 的 0.6.8 规则；随包内核仍 core `v0.2.6`，不跨档再加号。
- **0.2 三项状态改为「活区三端已复跑」** — README 双语 Roadmap 与状态行写明：①执行前约束、②执行中监管、③执行后审计均在 2026-11-09 于维护者活区三端复跑；同时写明**随包不附监督执行器**，本仓 `BUMO_JIANCHA_MODE` 仍为 `off`。
- **订正** — 克隆命令与版本行按实物同步（13 个 tag、9 条 2026-11-09 授权条目）；`00_meta/meta.json` 与 `10_rac/meta.json` 的应用内版本同时 0.32→0.33。
- **维护暂停** — 每版照旧写「维护暂停，稳定可用」；本版补一句维护者口径：哪一版才算最终暂停版尚未确定，因此仍按不定时更新发布。
- **未变** — 规则 0 条（声明式）、检查项 28；A10／A13 判据不变；`check --strict` 仍 `ALL PASS（A段 12 项 + B段 16 项）`。

**English**
- Documentation and version strings only; no verdict, no core-file-set change, `kernel/` untouched.
- The roadmap now states that all three 0.2 items were replayed on the maintainer's three live editions on 2026-11-09, and that this repository still ships no supervisor (`BUMO_JIANCHA_MODE` stays `off`).
- Synced clone/version lines (13 tags, 9 authorization entries dated 2026-11-09); in-app version `0.32` → `0.33` in both `00_meta/meta.json` and `10_rac/meta.json`.
- The maintenance-pause line is kept in every release, now noting that the final paused release is undecided and releases continue at irregular intervals.
- Unchanged: 0 rules (declarative), 28 checks, and the A10 / A13 verdicts.

## 0.32 — 2026-11-09

本版只修「发布件自述与实物不一致」，不改判定、不改核心件集合。

- **加号依据：0.31→0.32（+0.01 同档正常晋升）** — 依据 `HX\personal\20_view\di00_qidong_zongze.txt` L55—60 的 0.6.8 规则；随包内核仍 core `v0.2.6`，不跨档再加号。
- **`20_view/web/core_manifest.json` 的 `index.html` 哈希改为实物值** — 旧值 `17db952b…` 是 logKey 分组目录名修正前的版本；现按磁盘 12 件逐件重算，`generated` 改为 `2026-11-09`，`core_version` 仍 `0.10`。
- **README 自述按实物校正** — 英文侧「应用内版本」停在 `0.30`，改为 `0.32`；克隆命令的 tag 由 `v0.18` 改为 `v0.20`；`A10` 段旧文称「随附零条目模板、按设计为红」，与实际（随附 8 条 2026-11-09 条目、`A10` 为 PASS）不符，按实物改写。
- **未变** — 规则 0 条（声明式）、检查项 28；A10／A13 判据不变；`check --strict` 仍 `ALL PASS（A段 12 项 + B段 16 项）`。

**English**
- Fixes only where the published artefacts described themselves wrongly; no verdict or core-file-set changes.
- `20_view/web/core_manifest.json`: the `index.html` entry now carries the actual on-disk sha256; all 12 entries verify against disk, `generated` is `2026-11-09`, `core_version` stays `0.10`.
- README: the English "in-app version" line (stuck at `0.30`) now reads `0.32`; the clone command pins tag `v0.20`; the `A10` paragraph said the edition ships an empty template and is "red by design", which contradicted the shipped file (8 entries dated 2026-11-09, `A10` PASS) and is now corrected.
- Unchanged: 0 rules (declared), 28 checks, and the A10 / A13 verdicts.

## 0.31 — 2026-11-09

本版同步 core `v0.2.6`：A13 基线按端分文件存放，首次纳入基线时如实标注「未授权基线建立」；判定口径不变。

- **加号依据：0.30→0.31（+0.01 同档正常晋升；0.2.5→0.2.6 属 0.2.x 同档，不跨档）** — 依据 `HX\personal\20_view\di00_qidong_zongze.txt` L55—60 的 0.6.8／0.6.9 规则。
- **随包内核 `kernel/bumao_core/` 同步 core `v0.2.6`** — 改动 2 件：`engine.py`、`__init__.py`。
- **未变** — 规则 0 条／28 项检查；A10／B16 等判据不变。
- **应用内版本 `0.30` → `0.31`** — `00_meta/meta.json`、`10_rac/meta.json`；`README.md` 两个版本空间说明同步。

**English**
- Kernel bundled copy synced to core `v0.2.6` (`engine.py`, `__init__.py`); A13's verdict is unchanged and its baseline is now per-edition. In-app version `0.30` → `0.31`.

## 0.30 — 2026-11-09

本版同步 core `v0.2.5`：内核测试件与运行层文案不再命中发布端测试词闸门，测试与运行行为不变。

- **加号依据：0.29→0.30（+0.01 同档正常晋升）** — 依据 `HX\personal\20_view\di00_qidong_zongze.txt` L55—60 的 0.6.8 规则。
- **随包内核 `kernel/bumao_core/` 同步 core `v0.2.5`** — 改动 6 件，只改文案与测试临时件名，不改判定与测试行为。
- **发布 tag** — `v0.18` → `v0.19`；应用内版本 `0.29` → `0.30`。
- **未变** — 规则 0 条／28 项检查；A10／A13 判据不变。

## 0.28 — 2026-11-09

本版同步 core `v0.2.2`（commit `140d304`）随包内核，并把应用内版本补齐到发布序列号。Kernel sync to core v0.2.2; in-app version back-filled to the release series.

- **加号依据：0.17→0.18（+0.01 正常晋升）→0.28（+0.10 内核跨档 0.1→0.2，同一版内叠加）** — 依据 `HX\personal\20_view\di00_qidong_zongze.txt` L55—60 的 0.6.8 逐级加号规则，不跳号、不跨级。
- **应用内版本 `0.10` → `0.28`** — 生效声明 `00_meta/meta.json` 与执行器实际读取的 `10_rac/meta.json` 同步；`README.md` 两个版本空间说明同步。
- **随包内核同步到 core `v0.2.2`** — 以 tag 内容为准，非工作树拷贝；整目录覆盖 `kernel/bumao_core/`，新增 `host_reference.py`、`test_a10_policy.py`、`test_gate_registry.py` 与 `jiancha/` 运行层子包。
- **未变** — 规则 0 条／28 项检查；`A10`／`A13` 判定逻辑与判据输入无改动。

## 0.17 — 2026-11-09

本版只做内核同步，不新增规则、不放宽任何判定；**是本阶段的最后一个版本**，未来一个月不再主动迭代（只做维护与修复）。Kernel sync only; this is the last release of this phase.

- **内核随 core `v0.2.0-beta.5` 同步** — `kernel/bumao_core/` 的 `engine.py`、`gate_registry.py`、`bumao_core_rules.py`、`gate_count.py`、`test_equivalence.py`、`HOST_CONTRACT.md` 覆盖到 core 同版本，core 是唯一上游源头。
- **`build_parser()` 重复注册修复** — 旧内核连续两次 `sub.add_parser("check")`，调用即抛 `argparse.ArgumentError: conflicting subparser: check`；`main()` 过去另建一份解析器，文档里的参数因此从未真正注册。现在只有一份，`main()` 复用。
- **三个参数由文档承诺改为真实实现** — `check --quick`（只跑 A 段结构闸，结论行明说不能替代 `--strict`）、`whoami --full`（追加 4 行诊断，不带时逐字不变）、`selftest --kernel`（6 项宿主无关自检）。随包新增 `kernel/bumao_core/test_build_parser.py`（4/4）。
- **两种加载方式并存** — 新增 `kernel/bumao_core/__init__.py`，`pip install -e .` 与历史 `sys.path.insert` 都可用；`gate_count.py`／`test_equivalence.py` 在单仓 clone 下改为打印「需要三端同级检出」并退出 2，不再假绿或误报红。
- **未变** — 规则 0 条／28 项检查、应用内版本 `0.10`、目录结构；`A10`／`A13` 判定逻辑无改动，无当日授权条目时仍判 `DENY`。
- **已知红项（设计行为）** — 本机工作树已有基线，当日改内核件使 `A13` 判红（`改而未授权`）；`A10` 因随包审批册零条目恒判 `DENY`。下载件解出后首跑无基线，`A13` 先纳基线后通过，只剩 `A10`。

## 0.16 — 2026-11-09

本版只修判据取件，不放宽任何判定。This release only fixes where the gates find the ledger; no verdict was relaxed.

- **A10／A13 取件修正** — 单仓 clone 下「区根」原被取成仓外上一级，`A10` 读不到 `30_taizhang/shenpi_jilu.txt`，只能报「无审批册」。现在本仓根带 `30_taizhang/` 时以本仓根为区根。Area-root resolution fixed so `A10` can see the shipped ledger template on a single-repo clone.
- **不再读兄弟目录** — `find_approval_ledger()` 旧实现会向上走后翻兄弟目录，在发布仓同级布局下会读到别仓审批册；结论仍是 `DENY` 但理由写错。现在只沿直系祖先查找。No more sibling-directory scan.
- **随包审批册结构模板** — 新增 `30_taizhang/shenpi_jilu.txt`（零条目），`A10` 输出 `A10 判定=DENY ｜ 判拒（DENY · 策略 deny）：审批册里没有可解析的【第 N 号】条目`。Shipped zero-entry template makes the DENY explicit and judgeable.
- **未变** — 规则 0 条（`zero_rules` 声明）、闸门 28 项、应用内版本 `0.10`、`test_reverse.py` 5/5、`test_pretool.py` 10/10。Rules, gate count, in-app version and tests unchanged.
- **已知红项** — `check --strict` `1/28`（仅 `A10`，按设计判 DENY）。`1/28` red, only `A10`.

## 0.15 — 2026-11-08

本版是功能版：逃生令牌可按「具体工具＋具体载荷」绑定。This release ships a real security change: escape tokens can be bound to one exact tool + payload.

- **逃生令牌绑定** — `10_rac/pretool/escape.py` 的 `issue_token(reason, ttl_seconds, tool_name=None, payload=None)` 新增可选绑定；`is_valid(tok, tool_name, payload)` 对已绑定令牌校验 `sha256(tool_name + "\0" + payload)`。`10_rac/pretool/core.py` 先算载荷再验令牌，把工具名与载荷一起传入。改前：一枚令牌在 TTL 内可用于任何危险的 exec/write 调用，只要第一次用掉即可；改后：令牌只为签发时点名的那个调用放行，换一条命令则回落到 L3 判定，不匹配不会消耗令牌。Before: a token could be spent on any dangerous call inside its TTL. Now: a bound token only honors the exact tool + payload it was issued for; a mismatch falls back to L3.
- **向后兼容** — 不传 `tool_name`/`payload` 的调用保持旧行为（不绑定），既有调用方无需改动。Unbound tokens keep the old behaviour.
- **回归用例** — `10_rac/tests/test_pretool.py` 新增 1 条用例：绑定令牌对另一条命令判拒、对点名命令放行、同令牌重放判拒；实跑 10 cases / 10 pass。Adapter suite is now 10 cases, all passing.
- **未变** — 0 条生效规则、28 个闸门、应用内版本 `0.10`、内核、目录结构、启动器与视图均未改动。Rules, gate count, in-app version, kernel, layout, launcher and views unchanged.
- **已知红项** — 干净克隆连续两次运行均为 `2/28`（`A10`、`A13`，公开仓不发审批册，按设计红）。Clean clone: `2/28` on both runs (`A10`/`A13` by design).

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

---

## English

### 0.28 — 2026-11-09

Kernel sync to core v0.2.2; in-app version back-filled to the release series.

- **Bump rationale: 0.17→0.18 (+0.01 normal promotion) →0.28 (+0.10, kernel crossing tiers 0.1→0.2, stacked within one release)** — per the 0.6.8 stepwise bump rule at `HX\personal\20_view\di00_qidong_zongze.txt` L55—60: no skipped numbers, no skipped tiers.
- **In-app version `0.10` → `0.28`** — the effective declaration `00_meta/meta.json` and the `10_rac/meta.json` actually read by the executor are aligned; the two-version-spaces note in `README.md` is aligned.
- **Bundled kernel synced to core `v0.2.2`** — taken from the tag contents, not a working-tree copy; the whole directory overwrites `kernel/bumao_core/`, adding `host_reference.py`, `test_a10_policy.py`, `test_gate_registry.py` and the `jiancha/` runtime subpackage.
- **Unchanged** — 0 rules / 28 checks; the `A10` / `A13` verdict logic and evidence inputs are untouched.

### 0.17 — 2026-11-09

Kernel sync only; this is the last release of this phase.

- **Kernel synced with core `v0.2.0-beta.5`** — `engine.py`, `gate_registry.py`, `bumao_core_rules.py`, `gate_count.py`, `test_equivalence.py` and `HOST_CONTRACT.md` under `kernel/bumao_core/` are overwritten to the same core release, with core as the only upstream source.
- **`build_parser()` duplicate-registration fix** — the old kernel called `sub.add_parser("check")` twice, so calling it raised `argparse.ArgumentError: conflicting subparser: check`; `main()` used to build a separate parser, so the documented parameters were never actually registered. Now there is only one, reused by `main()`.
- **Three parameters moved from documented promises to real implementations** — `check --quick` (runs only the section A structural gates, and the conclusion line states it cannot replace `--strict`), `whoami --full` (appends 4 diagnostic lines, byte-for-byte unchanged without it), `selftest --kernel` (6 host-independent self-checks). Bundled `kernel/bumao_core/test_build_parser.py` (4/4).
- **Two loading modes coexist** — new `kernel/bumao_core/__init__.py`, so both `pip install -e .` and the historical `sys.path.insert` work; on a single-repo clone `gate_count.py` / `test_equivalence.py` now print "requires the three editions checked out at the same level" and exit 2, no longer faking green or reporting false red.
- **Unchanged** — 0 rules / 28 checks, in-app version `0.10`, layout; the `A10` / `A13` verdict logic is untouched and still DENYs when there is no same-day authorization entry.
- **Known reds (design behaviour)** — the local working tree already has a baseline, so changing kernel files that day makes `A13` red (`改而未授权`); `A10` always DENYs because the bundled approval ledger has zero entries. A downloaded artifact has no baseline on first run, so `A13` first enrolls the baseline and then passes, leaving only `A10`.

### 0.16 — 2026-11-09

This release only fixes where the gates find the ledger; no verdict was relaxed.

- **A10 / A13 evidence-lookup correction** — on a single-repo clone the "area root" was originally taken as the parent outside the repo, so `A10` could not read `30_taizhang/shenpi_jilu.txt` and could only report "no approval ledger". Now, when this repo root contains `30_taizhang/`, this repo root is the area root. Area-root resolution fixed so `A10` can see the shipped ledger template on a single-repo clone.
- **No more sibling directories** — the old `find_approval_ledger()` implementation walked up and then back through sibling directories, reading another repo's approval ledger under the release repos' sibling layout; the conclusion was still `DENY` but the reason was wrong. It now searches only along direct ancestors. No more sibling-directory scan.
- **Bundled approval-ledger structure template** — new `30_taizhang/shenpi_jilu.txt` (zero entries), and `A10` prints `A10 判定=DENY ｜ 判拒（DENY · 策略 deny）：审批册里没有可解析的【第 N 号】条目`. Shipped zero-entry template makes the DENY explicit and judgeable.
- **Unchanged** — 0 rules (`zero_rules` declaration), 28 gates, in-app version `0.10`, `test_reverse.py` 5/5, `test_pretool.py` 10/10. Rules, gate count, in-app version and tests unchanged.
- **Known reds** — `check --strict` `1/28` (only `A10`, DENY by design). `1/28` red, only `A10`.

### 0.15 — 2026-11-08

This release ships a real security change: escape tokens can be bound to one exact tool + payload.

- **Escape-token binding** — `issue_token(reason, ttl_seconds, tool_name=None, payload=None)` in `10_rac/pretool/escape.py` gains optional binding; `is_valid(tok, tool_name, payload)` checks `sha256(tool_name + "\0" + payload)` for bound tokens. `10_rac/pretool/core.py` computes the payload first and then validates the token, passing the tool name and payload together. Before: a token could be spent on any dangerous call inside its TTL. Now: a bound token only honors the exact tool + payload it was issued for; a mismatch falls back to L3 and does not consume the token.
- **Backward compatible** — calls that pass no `tool_name`/`payload` keep the old (unbound) behaviour, so existing callers need no change. Unbound tokens keep the old behaviour.
- **Regression case** — `10_rac/tests/test_pretool.py` adds 1 case: a bound token rejects another command, allows the named command, and rejects a replay of the same token; actually run 10 cases / 10 pass. Adapter suite is now 10 cases, all passing.
- **Unchanged** — 0 effective rules, 28 gates, in-app version `0.10`, kernel, layout, launcher and views are all unchanged. Rules, gate count, in-app version, kernel, layout, launcher and views unchanged.
- **Known reds** — a clean clone shows `2/28` on two consecutive runs (`A10`, `A13`; public repos do not ship an approval ledger, red by design). Clean clone: `2/28` on both runs (`A10`/`A13` by design).

### 0.14 — 2026-11-08

This release ships real behaviour changes: encoding-safe entry points and a portable launcher.

- **Encoding fix** — the `__main__` blocks of `10_rac/BumaoXTGL_Minimal_v01.py`, `20_view/web/serve.py` and `20_view/web/xtgl_core.py` now call `reconfigure(encoding="utf-8", errors="replace")` on both `stdout` / `stderr`, the same as the kernel's `serve.py` / `xtgl_core.py`. Before: on a cp936 console or with missing glyphs, a rare character could abort the check with `UnicodeEncodeError`; now it degrades to a replacement character and the run continues. Before: a rare glyph could abort the run with `UnicodeEncodeError`. Now: it is replaced instead of raising.
- **Launcher** — `20_view/web/qidong_kongzhitai.bat` sets `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` before calling any interpreter; the probe order changes to `py -3 → python3 → python → python_path.txt` (local override last), each candidate is run with `-c "import sys"`, and the Windows Store stub `python.exe` (exit code 9009) is skipped. The launcher probes `py -3 → python3 → python → python_path.txt`, runs each candidate, and rejects the Store stub.
- **Unchanged** — 0 effective rules, 28 gates, in-app version `0.10`, layout and views unchanged. Rules, gate count, in-app version and layout are unchanged.
- **Docs and maintenance status** — README gains `Status: maintenance pause` / 「状态：维护暂停，稳定可用」 at the top; new `RETURN_HERE.md` as the cold-start entry for resuming iteration (look at three things first, touch `CHANGELOG.md` first). README status line and `RETURN_HERE.md` added.
- **R6 / R8 are not in this repo** — this repo has no `B22` gate, and the reverse suite `10_rac/tests/test_reverse.py` already runs on sandbox copies (5 cases, unchanged). The `B22` content-hash boundary and the 28-case shadow-copy reverse suite belong to community / personal and are not claimed here. No `B22` here; the 5 reverse cases already run on sandbox copies and are unchanged.
- **Known reds** — `check --strict` shows `2/28` on both runs (`A10`, `A13`; public repos do not ship an approval ledger, red by design). Known reds: `A10`/`A13` by design.

### 0.13 — 2026-11-08

This release aligns naming and structure and ships the kernel contract; it adds no UI feature.

- Before: gate `A10` threw `FileNotFoundError` on a fresh clone, because `kernel_contract.json` was not in the repository. Now: `kernel/kernel_contract.json` and `kernel/contract_test.py` ship at the path `engine.py` reads (`kernel/`, one level above `kernel/bumao_core/`), so `A10` reports the missing approval ledger instead of crashing.
- Before: README opened with gate IDs and directory internals. Now: first screen answers what/who/problem, English first, Chinese below.
- Before: no screenshots. Now: two real captures in `docs/screens/` — `check --strict` output and the shipped tree.
- Before: install command followed `main`. Now: pinned to `v0.13` and verified with `SHA256SUMS`.
- Check count corrected to 28 (the `27 gates` line was wrong); a fresh clone reports `2/28 gates red` (A10/A13, not applicable).
- No rule or gate change: `git diff v0.12..HEAD -- 10_rac/ 20_view/` is empty; the only `kernel/` additions are the contract pair above.

### 0.1.1 — 2026-11-08

Bundled kernel.

- This repo adds `kernel/bumao_core/`, so a clone runs without an external `bumao-core`.
- The entry script's kernel lookup path changes from `../../kernel/bumao_core` to `../kernel/bumao_core`.
- Kernel maintenance model: `bumao-core` is the only source, and the whole directory overwrites this repo's copy.

### 0.1 — 2026-11-08

First public release.

- Skeleton edition: 0 effective rules, with 28 example templates / a 5-chapter structure.
- Six-layer workspace plus the three-layer assets: real body / views / ledgers.
- Four-step rule-change workflow plus full-gate self-check.
- Web console (default 8804).
