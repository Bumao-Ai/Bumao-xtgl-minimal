# RETURN_HERE — resume here

Status: maintenance pause · 状态：维护暂停，稳定可用

Iteration is paused; the current release is stable and usable as-is. When work resumes, start from this file.
迭代已暂停；当前版本稳定可用。恢复迭代时，从这份文件开始。

## Look at these three first · 先看这三样

1. **Which version you are on, and whether the tree is clean**
   `git tag --sort=-v:refname | head -3` and `git status --short`.
   If the tree is dirty, stop and decide what to keep before touching anything.
   先确认当前 tag 与工作区是否干净；工作区不干净就先决定留什么，再动手。

2. **The last verdict, then the current one**
   Run `python BumaoXTGL_Minimal_v01.py check --strict` twice (in `10_rac/`). This edition has no `check_last.json`; the two conclusions are the only credential.
   在 `10_rac/` 连跑两次 `check --strict`；本仓没有 `check_last.json`，两次结论一致才算基线。

3. **What was in flight**
   Read the top entry of `CHANGELOG.md` and `ROADMAP.md`. The top entry lists what the last release actually changed; the roadmap marks what was still in progress.
   读 `CHANGELOG.md` 最上面一条与 `ROADMAP.md`：前者是上一版真实改动，后者标着当时未完成项。

## Default-off switches · 默认关闭的开关

- `00_meta/feature_packs/f01_jieru.json` — `enabled: false`（接入名册，只读面板）；要用再打开。
- `00_meta/feature_packs/f02_lishi.json` — `enabled: false`（日志日历，只读面板）；要用再打开。
- 维护暂停：迭代停了，但已发的代码照常能跑；`serve.py` 不会自动启动，`check --strict` 也不会自己跑。
- 本仓没有 `check_last.json`，检查不落凭据、不自动改任何文件。
- 真正的主开关是 `BUMO_JIANCHA_MODE`（监督执行器属 personal／live 树，本仓不随附）：未设或拼错一律按 `off`，不会自启。
- 该开关置 `enforce` 时，一轮检查会复制基线，实测约 228 MB／1303 文件；`qingli` 默认只 dry-run，400 MB 上限只报警、不删。

## Touch this file first · 先动这个文件

`CHANGELOG.md` — open the new version entry before editing any code, so the change is recorded before it exists.
先开 `CHANGELOG.md` 的新版本条目，再改代码；先有记录，后有改动。

Then run `check --strict` twice and compare the two conclusions before committing.
然后连跑两次 `check --strict`，两次一致再提交。
