# Bumao XTGL Minimal — 开源发行说明

核对日期：2026-11-07　核对方式：逐项对照仓库内实物

## 一、基本信息

| 项 | 值 | 实物依据 |
|---|---|---|
| 名称 | Bumao XTGL Minimal | `10_rac/meta.json` 的 `name` |
| 版本 | 0.10 | `20_view/web/xtgl_core.py` 的 `CORE_VERSION`；`20_view/web/core_manifest.json` 的 `core_version` |
| 许可证 | Apache License 2.0 | 仓根 `LICENSE` 与 `10_rac/LICENSE`，两份字节相同 |
| 版权行 | `Copyright 2026 Bumao` | `NOTICE` |
| 商标 | 名称与标识的使用边界见仓根 `TRADEMARK.md` | 实物文件 |
| 端口 | `127.0.0.1:8804` | `20_view/web/web_config.json` 的 `port` |
| 运行环境 | Python 3.12.14；功能代码仅使用标准库 | 入口脚本与核心件的导入清单 |
| 预置规则 | 0 条生效（`10_rac/rules/` 为空，`10_rac/examples/` 另附 28 条示例模板） | 实物目录 |
| 前端 | `20_view/web` 全量随仓库发布，不剥离、不压缩、不混淆 | 实物目录 |

## 二、核心件与清单口径

`20_view/web` 下 13 个核心件，清单登记在 `core_manifest.json`：

```
xtgl_core.py  serve.py  index.html  setup.html  tutorial.html
kernelsync.py  module_check.py  modules.json  snapshot.py
i18n.js  favicon.png  xtgl_clean.py  design_tokens.json
```

其中 `kernelsync.py`、`module_check.py` 为本地工具，不发布。

`core_manifest.json` 记录上述 13 件的 SHA256，本身也在仓库内。核对应以仓内实物为准：

- 清单内的文件必须都在仓库内，仓库内不得出现清单外的核心件；
- 任意核心件改动后，由维护者在本地重算清单（本地工具，不发布）；
- 版本号只认 `xtgl_core.py` 的 `CORE_VERSION` 与 `core_manifest.json` 的 `core_version`，本文件不另立版本口径。

## 三、前端随包与 SPDX 标注现状

前端源码与后端同许可、同脱敏标准：

- `index.html`、`setup.html`、`tutorial.html`、`i18n.js`、`design_tokens.json`、`favicon.png` 全部随仓库发布；
- 4 个随包 Python 核心件（`xtgl_core.py`、`serve.py`、`snapshot.py`、`xtgl_clean.py`）文件头均带 `SPDX-License-Identifier: Apache-2.0`；
- HTML 与 JS（`index.html`、`setup.html`、`tutorial.html`、`i18n.js`）目前**未带** SPDX 注释，此项待补；
- `modules.json` 与 `design_tokens.json` 为数据文件，不带 SPDX 注释；
- 前端不得出现内部路径、内部角色代号、私有端名称或引用；
- 构建产物、缓存、`node_modules`、`*.bak*`、`*.tmp` 一律不入包。

## 四、禁止入包

- `web_config.local.json`（本机私有配置）
- `__pycache__/`、`*.pyc`
- `*.bak*`、`*.tmp`、`*~`
- `node_modules/`
- 任何未列入本仓库的私有配置或他端文件
- 本机路径、机器名、用户名、内部角色代号、内网地址

## 五、发布前自检

1. 在 `10_rac` 下执行 `python BumaoXTGL_Minimal_v01.py check --strict`，结论须为 `ALL PASS`；
2. 在 `20_view/web` 下核对 13 件哈希与 `core_manifest.json` 一致（由维护者在本地用核验工具完成，本地工具，不发布）；
3. 隐私重扫：本机路径、机器名、用户名、内部角色代号、内网地址零命中；
4. 冷启动：在干净目录解包后直接起服务，首页可开、向导可走；
5. 确认包内无 `.bak`／`__pycache__`／`node_modules`。

## 六、许可义务

- 分发须保留仓根 `LICENSE` 与 `NOTICE`；
- 修改过的文件须标注改动；
- 名称与标识的使用受仓根 `TRADEMARK.md` 约束。

维护者：Bumao

本稿替代 2026-11-03 的旧稿（旧稿已移入 `90_lishi`）。本稿只写仓库内可核对的实物事实；与实物不符的旧表述已删除。

---

## English

# Bumao XTGL Minimal — Open-Source Release Notice

Verification date: 2026-11-07　Verification method: item-by-item comparison against the physical items in the repository

## 1. Basic Information

| Item | Value | Physical basis |
|---|---|---|
| Name | Bumao XTGL Minimal | `name` of `10_rac/meta.json` |
| Version | 0.10 | `CORE_VERSION` of `20_view/web/xtgl_core.py`; `core_version` of `20_view/web/core_manifest.json` |
| License | Apache License 2.0 | repository-root `LICENSE` and `10_rac/LICENSE`, the two are byte-identical |
| Copyright line | `Copyright 2026 Bumao` | `NOTICE` |
| Trademark | the usage boundary of the name and logo is in the repository-root `TRADEMARK.md` | physical file |
| Port | `127.0.0.1:8804` | `port` of `20_view/web/web_config.json` |
| Runtime environment | Python 3.12.14; functional code uses only the standard library | import lists of the entry script and core files |
| Preset rules | 0 effective (`10_rac/rules/` is empty, `10_rac/examples/` additionally carries 28 example templates) | physical directory |
| Front end | `20_view/web` shipped in full with the repository, not stripped, not minified, not obfuscated | physical directory |

## 2. Core Files and Manifest Convention

There are 13 core files under `20_view/web`, registered in `core_manifest.json`:

```
xtgl_core.py  serve.py  index.html  setup.html  tutorial.html
kernelsync.py  module_check.py  modules.json  snapshot.py
i18n.js  favicon.png  xtgl_clean.py  design_tokens.json
```

Among them `kernelsync.py` and `module_check.py` are local tools and are not published.

`core_manifest.json` records the SHA256 of the above 13 files and is itself in the repository. Verification should be based on the physical items in the repository:

- Files listed in the manifest must all be in the repository, and no core file outside the manifest may appear in the repository;
- after any core file is changed, the maintainer recalculates the manifest locally (a local tool, not published);
- the version number is recognized only from `CORE_VERSION` of `xtgl_core.py` and `core_version` of `core_manifest.json`; this document does not establish a separate version convention.

## 3. Current State of Front-end Bundling and SPDX Marking

The front-end source is under the same license and the same desensitization standard as the backend:

- `index.html`, `setup.html`, `tutorial.html`, `i18n.js`, `design_tokens.json`, `favicon.png` are all shipped with the repository;
- the 4 bundled Python core files (`xtgl_core.py`, `serve.py`, `snapshot.py`, `xtgl_clean.py`) all carry `SPDX-License-Identifier: Apache-2.0` in their header;
- HTML and JS (`index.html`, `setup.html`, `tutorial.html`, `i18n.js`) currently **do not carry** SPDX comments; this item is to be added;
- `modules.json` and `design_tokens.json` are data files and carry no SPDX comments;
- the front end must not contain internal paths, internal role code names, private edition names, or references;
- build artifacts, caches, `node_modules`, `*.bak*`, `*.tmp` are never packaged.

## 4. Must Not Be Packaged

- `web_config.local.json` (local private configuration)
- `__pycache__/`, `*.pyc`
- `*.bak*`, `*.tmp`, `*~`
- `node_modules/`
- any private configuration or other-edition file not listed in this repository
- local paths, machine names, user names, internal role code names, intranet addresses

## 5. Pre-release Self-check

1. Under `10_rac`, run `python BumaoXTGL_Minimal_v01.py check --strict`; the result must be `ALL PASS`;
2. Under `20_view/web`, verify the 13 hashes match `core_manifest.json` (done locally by the maintainer with the verification tool, a local tool, not published);
3. Privacy rescan: zero hits for local paths, machine names, user names, internal role code names, intranet addresses;
4. Cold start: unpack in a clean directory and start the service directly; the home page opens and the wizard runs;
5. Confirm the package contains no `.bak`／`__pycache__`／`node_modules`.

## 6. License Obligations

- Distribution must retain the repository-root `LICENSE` and `NOTICE`;
- modified files must be marked as changed;
- the use of the name and logo is constrained by the repository-root `TRADEMARK.md`.

Maintainer: Bumao

This document replaces the old draft of 2026-11-03 (the old draft has been moved into `90_lishi`). This document writes only the physical facts verifiable in the repository; old statements inconsistent with the physical items have been removed.
