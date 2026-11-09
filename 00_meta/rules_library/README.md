# rules_library —— 规则库预留槽位（默认不生效、不自动启用）

落点：每端 `00_meta/rules_library/`（宿主层）。端根目录受结构闸 B5b 约束（子目录名必须匹配两位编号），
所以库挂在 00_meta 下面、与运行期声明件同层；生效规则目录（`web_config.json` 的 `rules` 段所指）另在别处，两者分开。

一句话：这里只放「槽位」和「模板」，不放任何人的私有规则。本目录里的包全部 `enabled=false`。

## 目录
- `schema.json` —— 包格式定义，`module_check.py` 按它校验；
- `packs/` —— 五类预置空包，规则数组一律为空；
- `examples/` —— 示例模板，永不自动启用；照着改成自己的包再放进 `packs/`。

## 五类包
| 包 | 管什么 |
|---|---|
| `backup` | 备份与保留 |
| `audit` | 留痕与台账 |
| `credential` | 凭据与闸门 |
| `rollback` | 回滚与证据 |
| `logging` | 日志与复审 |

## 怎么从规则库挂一条规则（六步）
1. 复制 `examples/example-template.json`，改名放进 `packs/`；
2. 按 `schema.json` 填自己的规则——只写自己的动作与范围，**不写真身条款的标题／编号／正文**；
   阈值、天数、份数一律留空由自己填，仓库和代码里不预置任何数值；
3. 把该包的 `enabled` 改成 `true`（不改就永远不生效）；
4. 跑 `python 20_view/web/module_check.py`：包格式错必须 FAIL，格式对才继续；
5. 跑闸门 `check --strict`：必须全绿；
6. 打开前端「能力挂载」里的规则库行看现场计数——未启用的包不进快照，启用了才出现。

## 红线（违反任一条即视为破坏预留）
① 不含任何真身条款标题／编号／正文；② 不写死天数、份数、条数、版本；
③ 不预设行为、不自动启用；④ 空库时三端启动不崩（缺目录只提示，不报错）；
⑤ 只有 `enabled=true` 且规则非空的包才允许出现在快照里。

## 反向用例（自己造，验证拦得住拦不住）
- 把 `packs/` 里任一包改成坏 JSON → `module_check` 必须 FAIL；
- 删掉 `depends_on`，或把 `applies_to` 写成不存在的端，或依赖定义表里没有的能力 → 必须 FAIL；
- 删掉五类槽位中的任意一个 → 必须 FAIL；
- 把整个 `rules_library` 目录改名 → 不许崩：只提示「未建库」，快照该行显示「未建库（不影响启动）」。

---

## English

# rules_library —— Reserved slot for the rules library (inactive by default, not auto-enabled)

Landing point: each end's `00_meta/rules_library/` (host layer). The end's root directory is constrained by structure gate B5b (subdirectory names must match a two-digit number), so the library is mounted under 00_meta, on the same layer as the runtime declaration files; the effective rules directory (the one referenced by the `rules` section of `web_config.json`) is elsewhere, and the two are kept separate.

In one sentence: only "slots" and "templates" live here; no one's private rules. All packs in this directory are `enabled=false`.

## Directory
- `schema.json` — the pack format definition; `module_check.py` validates against it;
- `packs/` — five preset empty packs, all with empty rule arrays;
- `examples/` — example templates, never auto-enabled; adapt one into your own pack and put it into `packs/`.

## The five pack types
| Pack | What it governs |
|---|---|
| `backup` | Backup and retention |
| `audit` | Trails and ledgers |
| `credential` | Credentials and gates |
| `rollback` | Rollback and evidence |
| `logging` | Logs and review |

## How to attach a rule from the rules library (six steps)
1. Copy `examples/example-template.json`, rename it, and put it into `packs/`;
2. Fill in your own rules according to `schema.json` — write only your own actions and scope, and **do not write the titles / numbers / body text of the actual clauses**; leave thresholds, days and counts blank for you to fill in yourself, and preset no values in the repository or the code;
3. Change that pack's `enabled` to `true` (if you do not change it, it will never take effect);
4. Run `python 20_view/web/module_check.py`: a bad pack format must FAIL, and only a correct format lets you continue;
5. Run the gate `check --strict`: it must be all green;
6. Open the rules-library row under "capability mounting" in the front end to see the live count — packs that are not enabled do not enter the snapshot; only enabled ones appear.

## Red lines (violating any one counts as breaking the reservation)
① Contain no titles / numbers / body text of the actual clauses; ② Do not hard-code days, counts, item counts or versions;
③ Do not preset behavior and do not auto-enable; ④ Do not crash the three ends' startup when the library is empty (a missing directory is only a hint, not an error);
⑤ Only packs with `enabled=true` and non-empty rules are allowed to appear in the snapshot.

## Negative cases (build them yourself to verify whether they are caught)
- Change any pack in `packs/` into bad JSON → `module_check` must FAIL;
- Delete `depends_on`, or write a nonexistent end into `applies_to`, or reference a capability that is not in the dependency definition table → must FAIL;
- Delete any one of the five slot categories → must FAIL;
- Rename the entire `rules_library` directory → it must not crash: only report "library not built", and the snapshot row shows "library not built (does not affect startup)".
