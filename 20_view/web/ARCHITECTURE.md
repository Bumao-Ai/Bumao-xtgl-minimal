# XTGL 架构说明 · Core 0.10（Minimal 版）

> 多个系统，一个内核。先做模块化单体，等真的需要独立部署时再拆。
> 这份文件描述的是**已经存在**的边界，和**明确暂不做**的事，不是愿景清单。
> 本文只描述 Minimal 版实物；Minimal 版与 Community 版共用同一套前端与内核，差异靠能力开关。

---

## 1. 目标与非目标

**目标**：本地优先、规则驱动、可扩展；同一内核支撑多个系统；工作区数据有统一规范；
外部（包括 AI）可以按契约扩展，但不能改内核。

**现在不做**：微服务、插件市场、热加载、权限系统、多端同步。
理由见第 7 节——维护者只有一个人时，架构复杂度就是最大的敌人。

---

## 2. 分层

```text
用户配置（规则包 / 工作目录 / 数据源 / 自动化）
        │
业务模块 modules（闸门 / 备份等已打开能力）
        │
XTGL Core（配置 · 路径 · 规则合并 · 闸门调用 · 数据读取 · 模块清单 · 写接口边界）
        │
工作区数据（00_meta / 10_rac / 20_view / 30_taizhang / 40_renwu）
```

四条纪律：

1. 模块只调用 Core，不直接读别人的私有文件；
2. Core 不认识具体业务，只认识「规则、任务、文档、闸门」这四种数据；
3. 视图可以重建，真身只有一份；
4. 写操作必须显式（向导接口），读操作默认只读。

---

## 3. Core 的边界

| Core 负责 | Core 不负责 |
|---|---|
| 配置解析（v1/v2 兼容） | 具体业务页面长什么样 |
| 站点根解析（CLI / 环境变量 / 配置 / 默认） | AI 模型调用与提示词 |
| 三层规则合并与冲突拒绝 | 文件清理策略（只报告，不删） |
| 调用引擎并回传原始输出 | 权限与多用户 |
| 任务目录与留档判定 | 数据库/远端同步 |
| 模块清单与版本兼容 | 模块内部的实现细节 |
| 写接口的本机边界 | 第三方插件运行时 |

Core 的公开面是 `xtgl_core.py` 的 `Console` 类对外方法，外加 `modules.json`。

---

## 4. 模块契约 v1

清单在 `modules.json`，校验工具为维护者本地工具（本地工具，不发布）：

| 字段 | 含义 | 约束 |
|---|---|---|
| `id` | 唯一标识 | 小写、唯一 |
| `name` | 显示名 | 非空 |
| `version` | 模块版本 | 语义化 |
| `core` | 兼容的内核范围 | `^0.10` 表示同内核版本 |
| `kind` | 类型 | `builtin` / `local` / `experimental` |
| `status` | 状态 | `active` / `planned` / `disabled` |
| `desc` | 一句话说明 | 可空但建议写 |

硬规则：

- 模块**不得声明写内核权限**（清单里出现 `write` / `mutate` 直接判失败）；
- 模块与内核版本不兼容时，校验工具与页面都会标出来；
- 当前只做「内置模块」：清单是边界声明，不是插件加载器。

校验命令不随公开仓发布（本地工具，不发布）；正文与表中字段即契约本身。

---

## 5. 工作区数据规范 v1

| 路径 | 作用 | 规则 |
|---|---|---|
| `00_meta/meta.json` | 版本单点 | 必需；`version` 是唯一版本来源 |
| `10_rac/` | 引擎与规则真身 | 引擎可缺省；`rules/` 默认不启用 |
| `10_rac/examples/` | 示例模板 | 5 章 28 条，只作示范，不参与判定 |
| `20_view/` | 视图 | 可重建，不手改 |
| `30_taizhang/` | 台账 | 只追加 |
| `40_renwu/<任务>/` | 任务与留档 | 每个目录至少一份留档 |
| `20_view/web/` | 控制台 | 本目录；核心文件清单见 `core_manifest.json` |

留档固定三段：摘要头 / 正文明细 / 索引尾；摘要头必须写「执行主体」（模型＋客户端），
不得署用户本人姓名。

---

## 6. 版本与兼容

- Core 用 `主.次`（当前 `0.10`），模块声明 `^0.10`；
- 破坏性变更升主版本，模块清单必须同步改范围；
- 弃用至少提前一个次版本，并在 README 写迁移方式；
- 数据规范只增字段、不改语义；新增字段必须可缺省；
- 核心文件由 `core_manifest.json` 锁定 sha256，端内不一致即视为故障。

---

## 7. 为什么先做模块化单体

1. **维护者少**：一个人维护十个服务，等于十个部署、十套日志、十次排障。
2. **调试成本**：单体里一个断点能走完；拆开后要先证明「不是网络问题」。
3. **AI 生成需要确定性边界**：单体的接口面小，AI 才可能生成可验证的模块。

什么时候拆：出现「必须独立部署」「必须独立升级」「外部开发者要独立发版」三者之一，
再拆，不提前。

---

## 8. AI 原生开发的护栏

允许 AI 生成模块，但必须走四步：

```text
AI 生成 → module_check 校验清单 → 单元测试 → 人工验收
```

- AI 不得修改 `xtgl_core.py` / `modules.json` 的内核语义；
- 模块的写操作只能走已声明的接口；
- 没有测试的模块不进 `status: active`；
- 验收人只看三件事：能不能跑、失败时说不说得清、有没有偷偷写别的目录。

一句话：**AI 可以写得快，机器必须验得严。**

---

## 9. 两个公开发行物，一个内核

| 发行物 | 形态 | 现在的关系 |
|---|---|---|
| Bumao XTGL / Minimal 版 | Web 控制台 + 零生效规则，只给工具链与示例模板 | 与 Community 版共用同一内核与同一前端 |
| Bumao XTGL / Community 版 | Web 控制台 + 44 条生效规则 | 与 Minimal 版共用同一内核与同一前端 |

收敛状态（2026-11-07 实测）：闸门内核 `engine.py` 是一份，位于独立仓 `bumao_core`；两端 `10_rac/` 内都不带内核副本，按部署约定导入。
**共用前端**：两端的 `index.html`、`setup.html`、`tutorial.html` 是同一份，不设端别分支；端别差异只写在 `web_config.json` 的 `capabilities`／端口／规则目录／引擎命令。
**已知差异**：`xtgl_core.py` 仅默认端口常量不同（Community 8802／Minimal 8804）；其余 12 件在设计上逐字节相同。
**已知债务**：渲染与规则装载层（`render.py`／`rules_db.py`）仍是两套，两端各一份，接口并不一致——取 meta 一侧叫 `meta_load()`，另一侧叫 `dbm.load_meta()`，`targets(meta)` 的签名也不同。渲染层收敛不在本轮范围。
另注：内核住在独立仓，单独 clone 本仓拿不到它，`check --strict` 跑不起来（属已知集成边界）。

---

## 10. 当前状态（2026-11-07 19:47—19:50 实测）

| 项 | 值 |
|---|---|
| Core 版本 | 0.10（`xtgl_core.py` 的 `CORE_VERSION` ＝ `core_manifest.json` 的 `core_version`） |
| 清单生成时间 | 2026-11-07 19:47:40 |
| 内核文件 | 13 个（`core_manifest.json` 登记；含 tutorial.html / i18n.js / modules.json / xtgl_clean.py / design_tokens.json） |
| 内置模块 | **20 个**（`modules.json` 现行清单；控制台按 `capabilities` 只显示已打开的部分） |
| 本端能力 | `gate` / `backup` 共 2 项；控制台按能力裁剪页签与卡片，不显示未打开能力 |
| 清单对账 | 本端清单结论 `PASS：13 个核心文件与清单一致（内核 0.10）`（核验工具为本地工具，不发布） |
| 两端核心 | 设计上 12/13 逐字节相同；实测当前 3 件不一致：`xtgl_core.py`（端口常量）、`index.html`、`kernelsync.py`（后两件为 Community 端并行改动后待重算） |
| 内核测试 | `tests/test_core.py` 共 27 项；本端当前 **2 FAIL ＋ 2 ERROR** |
| Minimal 版规则 | 0.10，`rules/` 零生效规则；`examples/` 5 章 28 条示例模板 |
| 本端 check | `check --strict` 结论 `ALL PASS`（A 段 11 项 ＋ B 段 16 项 ＝ 27 项） |

当前红项（本端实测）：

- FAIL ×2：`TestManual.test_manual_overrides_machine`（读写宿主机真实 `~/.xtgl/manual.json`，健康度 `33 != 100`）；`TestModules.test_incompatible_module_is_flagged`。
- ERROR ×2：`TestConfig.test_corrupt_config_does_not_crash`（`json.decoder.JSONDecodeError`）；`TestPath.test_empty_config_gives_setup_required`（`xtgl_core.ConfigError`：临时配置缺 `engine.cmd`）。

Community 端同套测试为 27 项、3 FAIL ＋ 2 ERROR（多一项 `test_manifest_matches_files`，由并行改动后清单未重算导致）。红项与成因已登记进缺陷记录，修法待裁。

---

## 11. 版本同步纪律（正式版）

- 任何正式版能力（人工判定、健康度、导出、教程）必须**同时**落在两个公开发行版；
- 两端差异只允许出现在 `web_config.json`（版别文案 / 端口 / 规则目录 / 引擎命令）与 `xtgl_core.py` 的默认端口常量；
- 发版前固定三步：本地重算清单 → 本地比对 → 两端测试全过（清单与比对工具为本地工具，不发布）；
- 人工判定记录放仓库外（`~/.xtgl/manual.json`），两版控制台共用同一份；
- 版别口径：Minimal 版 = 零规则版，不含生效规则，只给工具链＋`examples/` 28 条示例模板；Community 版 = 基础规则版，44 条生效规则。控制台标题取 `web_config.json` 的 title「Bumao XTGL」＋ product_edition；`10_rac/meta.json` 的 name 与之一致：Minimal 版「Bumao XTGL Minimal」、Community 版「Bumao XTGL Community」。两端拼写统一为 Bumao。
