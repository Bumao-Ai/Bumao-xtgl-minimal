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
