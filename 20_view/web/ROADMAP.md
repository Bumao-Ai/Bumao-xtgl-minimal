# XTGL 路线图 · 从个人工具到可扩展平台

> 北极星不是 Stars，是**每周真实使用的工作区数**。
> 100 个每天在用的人，比 5000 个只点过 Star 的人更有价值。

---

## 阶段 0 · 独立可运行（已完成，2026-11-02）

- 控制台内核 2.0：路径无关、三层规则、首次向导、演示环境、22 项测试；
- 两个开源发行物共用同一内核，8 个核心文件 sha256 全一致；
- 两端闸门 ALL PASS，主系统 `check --strict` ALL PASS。

**这一阶段证明的是**：它不是只能在作者电脑上跑。

---

## 阶段 1 · 稳定与可安装（近期，1–2 个月）

目标：一个陌生人能在干净 Windows 上装好、跑起来、看懂。

验收标准（全部满足才算过）：

- [ ] 干净机器（无 Python 缓存、无本项目历史）三条命令内启动成功；
- [ ] 首次向导能覆盖「新建 / 已有项目 / 坏配置」三种入口；
- [ ] 内核测试 ≥ 22 项，两端全过；CI 上跑；
- [ ] 至少 10 个非作者用户独立安装并反馈（不是演示，是真实使用）；
- [ ] 两份 README + 一份技术文档 + 一份架构说明，全部与代码同步；
- [ ] 已知问题清单公开，坏味道不藏着。

**明确不做**：插件、模块市场、多端。

---

## 阶段 2 · 多系统模块化（中期，3–6 个月）

目标：同一内核上，至少三个系统能独立开关、独立升级。

验收标准：

- [ ] 模块清单 v1 冻结，`module_check` 进 CI；
- [ ] 至少 3 个模块可独立启用/停用（任务 / 规则 / 审计为候选）；
- [ ] 工作区数据规范 v1 冻结，新增字段只增不改；
- [ ] 模块之间不互相读私有文件，只经 Core；
- [ ] 第一个外部开发者提交的模块被合并（哪怕很小）。

**这一阶段的关键**：证明「共享内核」不是口号，而是能约束第三方的东西。

---

## 阶段 3 · 开源生态（6–12 个月）

目标：不再只有作者一个人在扩展。

验收标准：

- [ ] 至少 2 个第三方模块长期可用；
- [ ] 兼容性策略被执行过一次（弃用 → 迁移 → 移除）；
- [ ] 有固定的发布节奏与变更日志；
- [ ] 有可提问、可复现 issue 的社区入口；
- [ ] 至少一次「外部贡献者修了 Core 的 bug」的合并记录。

---

## 阶段 4 · 基础设施（1 年以上，长期愿景）

目标：别的项目愿意把 XTGL Core 当成底座。

验收标准：

- [ ] 有项目把 Core 作为依赖集成；
- [ ] 出现桌面之外的客户端（服务端 / Web / 其他）；
- [ ] 数据规范与模块契约成为可引用的标准文档。

这一阶段不设时间表，也不承诺。做不到就停在阶段 2/3，不丢人。

---

## 现在最该做的六件事（未来 30 天）

1. **引擎收敛**：把两个开源仓库的 render / rules_db / engine 合成一套，或至少加契约测试；
2. **写接口令牌**：启动时生成一次性 token，写接口校验，替换「只信本机」；
3. **HTTP 端到端测试**：起停真实服务器，覆盖 200 / 403 / 404 与写接口鉴权；
4. **规则 schema**：`rules_schema.json` + 校验命令，坏规则在向导第 3 步就报；
5. **干净机器安装**：找一台没装过本项目的 Windows，从零走一遍并记录卡点；
6. **英文 README**：对外发布的第一道门，不写英文等于只面向中文用户。

---

## 判断标准（防止自嗨）

每季度只问三个问题：

1. 有没有人**每周**在用，而不是装完就放着？
2. 新用户第一次失败，能不能在文档里找到原因？
3. 这一季度删掉的复杂度，是否多于新增的功能？

三个都答不上来，就停止加功能，先修基础。

---

## English

# XTGL Roadmap · From a personal tool to an extensible platform

> The North Star is not Stars, it is **the number of workspaces actually used every week**.
> 100 people using it every day are worth more than 5000 people who only clicked Star once.

---

## Stage 0 · Independently runnable (done, 2026-11-02)

- Console kernel 2.0: path-independent, three-layer rules, first-run wizard, demo environment, 22 tests;
- Two open-source releases share the same kernel, 8 core files with identical sha256;
- Gates on both editions ALL PASS, main system `check --strict` ALL PASS.

**What this stage proved**: it is not something that only runs on the author's computer.

---

## Stage 1 · Stable and installable (near term, 1–2 months)

Goal: a stranger can install it, run it, and understand it on a clean Windows machine.

Acceptance criteria (all must be met to pass):

- [ ] On a clean machine (no Python cache, no history of this project) it starts successfully within three commands;
- [ ] The first-run wizard covers all three entries: "new / existing project / broken config";
- [ ] Kernel tests ≥ 22 items, all passing on both editions; run in CI;
- [ ] At least 10 non-author users install it independently and give feedback (not a demo, real usage);
- [ ] Two READMEs + one technical document + one architecture note, all in sync with the code;
- [ ] The known-issues list is public; bad smells are not hidden.

**Explicitly not doing**: plugins, module marketplace, multi-device.

---

## Stage 2 · Multi-system modularization (mid term, 3–6 months)

Goal: on the same kernel, at least three systems can be switched on and off independently and upgraded independently.

Acceptance criteria:

- [ ] Module manifest v1 frozen, `module_check` in CI;
- [ ] At least 3 modules can be enabled/disabled independently (tasks / rules / audit are candidates);
- [ ] Workspace data spec v1 frozen, new fields are only added, never changed;
- [ ] Modules do not read each other's private files, they only go through Core;
- [ ] The first module submitted by an external developer is merged (even a very small one).

**The key to this stage**: proving that "shared kernel" is not a slogan but something that can constrain third parties.

---

## Stage 3 · Open-source ecosystem (6–12 months)

Goal: the author is no longer the only one extending it.

Acceptance criteria:

- [ ] At least 2 third-party modules usable over the long term;
- [ ] The compatibility policy has been executed once (deprecate → migrate → remove);
- [ ] A fixed release cadence and changelog;
- [ ] A community entry point where questions can be asked and issues reproduced;
- [ ] At least one merge record of "an external contributor fixed a Core bug".

---

## Stage 4 · Infrastructure (1 year and beyond, long-term vision)

Goal: other projects are willing to take XTGL Core as a foundation.

Acceptance criteria:

- [ ] A project integrates Core as a dependency;
- [ ] Clients beyond desktop appear (server / Web / other);
- [ ] The data spec and module contract become citable standard documents.

This stage has no schedule and makes no promise. If we cannot reach it, we stop at stage 2/3; there is no shame in that.

---

## The six things most worth doing now (next 30 days)

1. **Engine convergence**: merge the render / rules_db / engine of the two open-source repositories into one set, or at least add contract tests;
2. **Write-interface token**: generate a one-time token at startup, validate it on the write interface, replacing "trust only the local machine";
3. **HTTP end-to-end tests**: start and stop a real server, covering 200 / 403 / 404 and write-interface authentication;
4. **Rule schema**: `rules_schema.json` + a validation command; bad rules are reported at step 3 of the wizard;
5. **Clean-machine install**: find a Windows machine that never had this project, walk through it from scratch, and record the sticking points;
6. **English README**: the first gate for going public; without English you are only targeting Chinese users.

---

## Judging criteria (to prevent self-congratulation)

Ask only three questions every quarter:

1. Is anyone using it **every week**, rather than installing it and leaving it?
2. When a new user fails the first time, can they find the reason in the documentation?
3. Did this quarter delete more complexity than it added features?

If you cannot answer all three, stop adding features and fix the basics first.
