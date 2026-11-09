# 前端接入契约单页

> **参考件·不构成约束。** 2026-11-07 裁定：核心件改动不靠这份单页管人，靠三段机制（只读锁定／哨兵／下游阻断，见 `kernel/bumao_core/HOST_CONTRACT.md` §九）。本页只解决「改的人知道该改什么」。

## 一、九个 `/api/*` 端点

| 端点 | 入参 | 返回字段 | 取不到时的正确表现 |
|---|---|---|---|
| `/api/overview` | 无 | `core_version, edition, title, subtitle, root, root_name, root_source, setup_required, setup_reason, modules, goals, daiban, logs, clauses, health, gates` | 页面主体显示「未配置」＋`/setup` 入口；不得空转、不得留空白卡片 |
| `/api/env` | 无 | `root, ok, checks` | 顶部状态条显示「未配置」＋`/setup` 入口 |
| `/api/clauses` | 无 | `file, error, clauses` | 条款区显示 `error` 原文；不隐藏错误 |
| `/api/doc` | `?file=`（必填；缺参 400） | `error` | 显示「文件不存在或未选择」＋返回列表入口 |
| `/api/tasks` | 无 | 数组 | 待办区显示「暂无待办」空态文案 |
| `/api/modules` | 无 | `ok, core, list_version, modules, errors` | 模块区显示 `errors` 原文；不得用「加载中」长期占位 |
| `/api/goals` | 无 | `ok, path, count, list, error` | 目标区显示 `error`＋`/setup` 入口 |
| `/api/detail` | `?file=`（必填；缺参 400） | 明细文本 | 显示「未选择文件」空态 |
| `/api/snapshot` | 无 | `meta, gates, coverage, drift, rules_library, _capabilities` | 体检区显示「未取到快照」；不得把缺数据画成绿 |

判据：九条逐个实测 200／400，且每种「取不到」都有可见文案与 `/setup` 入口；空转（请求失败但页面无变化）即不合格。

## 二、不可变项

1. **设计语言**：配色、间距、圆角、字体、卡片结构、动画已定型，新增元素只从 `design_tokens.json` 取值。
2. **token 闸**：三页出现的字面色值 `#xxxxxx` 与 `font-size:Npx` 必须命中 `design_tokens.json` 或 `00_meta/frontend_token_baseline.json` 的存量登记，否则 `B28` 红。
3. **三端一致性**：community 与 minimal 的 12 件逐字节一致；`xtgl_core.py` 只许端口兜底行按端不同。

## 三、脱敏规则

- 盘符前缀（如 X 盘）、用户名、机器名、内部目录名四类零命中。
- 路径一律走同一个 `maskPath()`，只显示末段；禁止在 `innerHTML` 拼接、`title`、`data-*`、tooltip 里绕开它直接写原路径。
- 验收两处都扫：`innerText` 与 `outerHTML`，命中数必须为 0。

## 四、改前必做三件事

1. **落预告行**：先跑 `kernel/suoding.py unlock ...`（自动写 `20_view/web/gaigai_yugao.txt`），再动手；
2. **留改前件**：被改文件的原件与哈希进 `90_lishi` 对应维护目录；
3. **通知基线重算**：改完报「需要重算基线」，由基线负责人一次性 `--manifest` 重算并复跑三端；不得自行重算抹平。

入口：`/setup` 页。本页入口链接待前端线在 `setup.html` 加一行（本轮未改该文件，避免与美化在途打架）。

---

## English

# Frontend Integration Contract (Single Page)

> **Reference document · not binding.** Ruling of 2026-11-07: changes to core files are not policed by this single page, but by the three-part mechanism (read-only lock / sentinel / downstream blocking, see §9 of `kernel/bumao_core/HOST_CONTRACT.md`). This page only answers "the person making the change knows what to change".

## 1. The nine `/api/*` endpoints

| Endpoint | Input | Returned fields | Correct behaviour when it cannot be obtained |
|---|---|---|---|
| `/api/overview` | none | `core_version, edition, title, subtitle, root, root_name, root_source, setup_required, setup_reason, modules, goals, daiban, logs, clauses, health, gates` | The page body shows "not configured" + a `/setup` entry; it must not spin idle and must not leave blank cards |
| `/api/env` | none | `root, ok, checks` | The top status bar shows "not configured" + a `/setup` entry |
| `/api/clauses` | none | `file, error, clauses` | The clause area shows the original `error` text; errors are not hidden |
| `/api/doc` | `?file=` (required; missing parameter returns 400) | `error` | Shows "file does not exist or was not selected" + an entry back to the list |
| `/api/tasks` | none | array | The to-do area shows the empty-state copy "no to-dos for now" |
| `/api/modules` | none | `ok, core, list_version, modules, errors` | The module area shows the original `errors` text; "loading" must not be used as a long-term placeholder |
| `/api/goals` | none | `ok, path, count, list, error` | The goals area shows `error` + a `/setup` entry |
| `/api/detail` | `?file=` (required; missing parameter returns 400) | detail text | Shows the empty state "no file selected" |
| `/api/snapshot` | none | `meta, gates, coverage, drift, rules_library, _capabilities` | The health area shows "snapshot not obtained"; missing data must not be drawn green |

Criterion: test all nine one by one for 200/400, and every "cannot be obtained" case has visible copy and a `/setup` entry; idle spinning (the request fails but the page does not change) fails.

## 2. Immutable items

1. **Design language**: colors, spacing, corner radius, fonts, card structure and animation are already fixed; new elements take values only from `design_tokens.json`.
2. **Token gate**: the literal color values `#xxxxxx` and `font-size:Npx` appearing on the three pages must hit existing registrations in `design_tokens.json` or `00_meta/frontend_token_baseline.json`, otherwise `B28` goes red.
3. **Three-edition consistency**: the 12 files of community and minimal are byte-identical; in `xtgl_core.py` only the port fallback line may differ per edition.

## 3. Desensitization rules

- Zero hits for four categories: drive-letter prefixes (such as drive X), usernames, machine names, internal directory names.
- Paths all go through the same `maskPath()`, which shows only the last segment; it is forbidden to bypass it and write the raw path in `innerHTML` concatenation, `title`, `data-*`, or tooltips.
- Acceptance scans both: `innerText` and `outerHTML`; the hit count must be 0.

## 4. Three things that must be done before changing anything

1. **Leave a notice line**: first run `kernel/suoding.py unlock ...` (which automatically writes `20_view/web/gaigai_yugao.txt`), then start changing;
2. **Keep a pre-change copy**: the original of each changed file and its hash go into the corresponding maintenance directory under `90_lishi`;
3. **Notify for baseline recomputation**: after the change, report "baseline recomputation required"; the baseline owner recomputes once with `--manifest` and re-runs the three editions; you must not recompute on your own to smooth things over.

Entry: the `/setup` page. The entry link on this page awaits a line to be added to `setup.html` by the frontend line (that file was not changed this round, to avoid clashing with the beautification work in flight).
