# bumao_core 宿主契约（HOST CONTRACT）

> 本文件回答一个问题：**外部产品要接入这个内核，必须实现什么。**
> 内核本身不带任何规则、不带任何业务、不带任何端名；规则、闸门清单、路径全部由宿主提供。
>
> 本文件只描述契约，不构成开工授权。

- 契约对应内核版本：**Bumao Core 0.10**（`engine.py` 为唯一运行时实现）
- 契约版本：**implicit-v1**（尚无机器校验，见 §六 缺陷 1）
- 适用对象：任何宿主端。一个宿主端由两部分组成——**wrapper**（启动入口，负责注入与注册）与 **rules_db**（规则库模块，负责数据与检查函数）。
- 版本号来源：内核自身不存端名，运行时从宿主 `meta` 取 `name`／`version`／`effective`。

---

## 一、接入四步

```python
import sys, os
sys.path.insert(0, r"<内核目录绝对路径>")   # 内核不是包，只能这样加载（见 §五）
sys.path.insert(0, HERE)                     # 宿主自己的目录

import engine as core                        # 1. 拿内核
core.configure(rules_db_module=my_rules_db)  # 2. 注入规则库模块
core.register("B1", my_gate_fn, "闸门说明")   # 3. 逐个注册闸门
core.set_expected("MyEdition", frozenset(["B1", ...]))  # 4. 声明期望集（防缩水基准）
sys.exit(core.main(["check", "--strict"]))   #    跑检查，退出码即结论
```

**顺序约束**：

1. `configure()` 必须最先调用——未注入时任何命令都不可用；
2. `set_expected()` 必须在全部 `register()` 完成之后调用；
3. `main()` 最后调用，其返回值即进程退出码。

宿主 wrapper 必须自行完成上述五处动作：`import engine as core`、`configure(rules_db_module=...)`、逐个 `register(...)`、`set_expected(...)`、`sys.exit(core.main(...))`。内核不替宿主做其中任何一步。

---

## 二、内核公开的函数签名

| 函数 | 签名 | 说明 |
|---|---|---|
| `configure` | `configure(rules_db_module=None)` | **必须最先调用**。只把模块存进全局 `_rdb` |
| `register` | `register(gid, fn, label, section="B")` | 注册单个闸门。`section` 取 `"B"`（实物闸）或 `"Z"`（准则闸）；其它值落入 B |
| `register_all` | `register_all(category_fn_map, category="B")` | 从 `{gid: fn}` 字典批量注册，label 固定为 `"(auto-discovered)"`，返回已注册 gid 列表 |
| `set_expected` | `set_expected(section, expected_set)` | 声明本版期望闸门集。**必须在全部 `register()` 之后调用** |
| `verify_registration` | `verify_registration(expected_set, edition_name="unknown")` | 防缩水校验：计算 `missing = expected - registered`、`extra = registered - expected` |
| `main` | `main(argv=None)` | CLI 入口，返回值即退出码 |
| `cmd_check` | `cmd_check(strict=False, quick=False)` | `check` 子命令实现 |
| `cmd_whoami` | `cmd_whoami()` | `whoami` 子命令实现，恒返回 0；接入与否由 `check --strict` 的 B1 与 N4 判定 |

### CLI 子命令（7 个）

`whoami / check / audit / bump / show / selftest / refresh`

- `check` 支持 `--strict` 与 `--quick`；
- `whoami` 支持 `--full`；
- `bump` 支持 `--level`（默认 `L1`）；
- `show` 需要一个条款 id。

**退出码约定**：`0` 表示全部通过或命令正常完成；非 `0` 表示存在 FAIL、异常或参数错误。
`cmd_whoami` 是例外：漂移不为 0 时它打印「未接入（先 render.py write）」但仍返回 0——停机判据由 `check --strict` 承担。

若宿主入口文档与本文件命令不一致，**以本文件为准**；内核实际只注册上表 7 个子命令。

---

## 三、宿主必须提供的规则库模块（`rules_db`）—— 12 个成员

`configure(rules_db_module=X)` 之后，内核把 `X` 记作 `dbm`，并按下表访问它。

| # | 成员 | 必需？ | 守卫 | 语义 |
|---|---|---|---|---|
| 1 | `load()` | **必需** | 无 | 加载原始规则数据 |
| 2 | `index(db)` | **必需** | 无 | 建索引；**返回值必须是含 `meta`／`clauses`／`chapters` 三个键的 dict** |
| 3 | `load_meta()` | **必需** | 无 | 返回 dict，内核取 `name`／`version`／`effective` 三个键 |
| 4 | `dup_ids(db)` | **必需** | 无 | 返回重复 id 列表；**空列表 `[]` 表示无重复** |
| 5 | `block_broken(clauses)` | **必需** | 无 | 块断裂检查 |
| 6 | `shell_clauses(db)` | **必需** | 无 | 空壳条款检查 |
| 7 | `ROOT` | 可选 | 有 | 产品根目录，四级 fallback 第 1 级 |
| 8 | `_inner.ROOT` | 可选 | 有 | **私有成员**，第 2 级 |
| 9 | `HERE` | 可选 | 有 | 第 3 级；三级都缺则退到 `os.path.dirname(引擎所在目录)` |
| 10 | `render_all(meta, db)` | 可选 | 有 | 渲染全部视图，返回渲染数 |
| 11 | `check_drift()` | 可选 | 有（`getattr` ＋ `sys.modules` 双兜） | 返回漂移列表；`whoami` 据此打印「视图漂移：N 处」与「接入状态」 |
| 12 | `daiban`（**模块对象**，须含 `parse()` 与 `_date()`） | 可选 | 有 | 周期待办的数据源；内核**不** `import` 全局模块名，只读注入成员 |

**约束**：

- 第 1–6 项无 `hasattr` 守卫，缺任一立即抛异常，命令失败。
- 第 7–9 项用于产品根目录回退，整段有 `try/except`，全缺不会崩。
- 第 11 项的取值顺序：先取注入的 `dbm.check_drift`；再退回宿主**已导入**的 `render` / `rules_render` 模块上的 `check_drift`；两处都取不到时打印「视图漂移：宿主未提供 check_drift，无法计算」＋「接入状态：未就绪（漂移未算出）」——**拿不到就明说拿不到，不打假数**。
- 第 12 项取不到时按下方《周期待办兜底契约》输出固定兜底行，不算缺陷。
- 第 8 项是私有成员，但已进入对外契约（见 §六 缺陷 2）。

### 周期待办兜底契约（2026-11-08 定案）

第 12 项缺失，或成员不含 `parse`／`_date` 时，**兜底文案即契约行为**：不视为缺陷，不改两端核心逻辑。固定输出须逐字一致（含结尾文件名）：

```
周期待办：宿主 rules_db 未注入 daiban 成员（须含 parse／_date）——须手读宿主规程目录下 daiban_zongbiao.txt
```

约束：

- `whoami` 必须退出码 0，该行逐字与上式一致；不得抛异常、不得编造条数。
- 开源两端（community／minimal）不提供 `daiban.py`，属契约内的正常形态；personal 提供数据源，输出真实待办。
- 验收方法：两端各跑 `whoami`，比对「周期待办：」整行，须字节级相同。

### 零规则端：`meta["zero_rules"]` ＋ 规则目录成员 `RULES_DIR`

A1 判据为：

```
(n_ch > 0 and n_cls > 0) or (meta["zero_rules"] 为真 and 规则目录下 .json 计数为 0)
```

声明 `zero_rules` 时，宿主还必须暴露规则目录成员 `RULES_DIR`（目录不可用时内核回退读 `ZH`）。
`RULES_DIR` **不在上表 12 个契约成员之内**，是零规则端的额外硬性要求。

| 情形 | A1 判定 |
|---|---|
| 有生效条款 | **PASS**（走第一分支，不数目录） |
| 声明 `zero_rules` 且规则目录内 `.json` 为 0 | **PASS** |
| 声明 `zero_rules` 但规则目录内有 `.json` | **FAIL** |
| 声明 `zero_rules` 但规则目录未暴露／不存在 | **FAIL**（detail 记 `unverifiable`） |
| 声明 `zero_rules`、目录非空**且条款能装载** | 走第一分支判绿（**未加反向闸**） |

### 宿主可选扩展成员（非契约必需）

除上表 12 项外，内核还按 `getattr` 读取若干宿主扩展；缺失时各命令走兜底，不影响契约成立：

- `META_PATH` —— `bump` 定位 meta 文件；
- `ZH` —— 规则目录的第二候选；
- `enforce_decl` —— A12 强制／限制条款与闸位接线；
- `record_check_result` —— check 结果回写。

---

## 四、内核不提供什么（能力边界）

| 不提供 | 判据 |
|---|---|
| 任何具体规则 | 内核内 0 条；规则全部在宿主规则包 |
| 任何端名／业务名 | `engine.py` 内无端名、无业务名 |
| 任何服务／SDK／IPC | 内核全部 `.py` 内无 `http`／`socket`／`grpc`／`daemon`／`server`／`api` |
| 包安装能力 | 内核目录无 `__init__.py`／`pyproject.toml`／`setup.py` |
| 闸门清单 | 闸门由宿主 wrapper 显式 `register()` 提供，**不是数据驱动** |

**它是什么**：CLI 式**规则执行／治理框架**。卖点是「执行可信」——宿主定下的规矩被不折不扣执行，
结论不能被偷偷放宽、跳过或伪造（防缩水机制见 §七）。
**它不是什么**：不是应用运行时。Web 应用、游戏、桌面软件不会「跑在它上面」，只会「调它做一次 check」。

---

## 五、加载方式（当前唯一可行的一种）

内核**不是 Python 包**（无 `__init__.py`），只能靠 `sys.path.insert` 硬绑目录树：

```python
sys.path.insert(0, "<内核目录绝对路径>")
import engine
```

**约束**：

- 内核目录可整体搬走；搬走后 `import engine` 仍成功，因为内核不依赖工程树位置。
- 未 `configure()` 时运行 `whoami` 会打印 `[ERROR] whoami failed: rules_db not configured. Call configure() first.` 并返回退出码 1，CI 可据此判失败。
- 闸门模板文件 `bumao_core_gates.py` 采用**宿主注入契约**：模板只接受 `drift_func`／`targets_func`／`clauses_func` 这类可调用对象，取不到注入一律判 **FAIL** 并写明缺哪个注入名；文件内不 `import render`，不设「取不到就返回 True」的兜底。
- 现有 13 个闸门模板（`make_drift_gate` 等）均可在内核目录之外单文件载入执行。

---

## 六、已知缺陷（写在这里，不藏）

| # | 缺陷 | 影响 |
|---|---|---|
| 1 | **契约是隐式的**，全库没有接口定义、类型约定或最小示例 | 外部开发只能反读既有 wrapper 才知道该实现什么 |
| 2 | 契约里**含私有成员 `_inner`** | 私有成员进了对外契约；文档只能描述它，消不掉它 |
| 3 | **`render_all` 各宿主端皆无**，且调用点有 `hasattr` 守卫 | 功能静默缺失，全绿也照不出来 |
| 4 | ~~闸门模板硬依赖宿主的 `render` 模块~~ → **已修**：改为宿主注入函数，取不到即判 FAIL | 内核目录已自包含，坏依赖不再被 `except ImportError` 静默吞掉 |
| 5 | **闸门模板接线不完整**：部分宿主端只 import 不调用；G 族模板从未被 `core.register` 注册 | 已写好的能力取不出来；挂载需改闸门数，属未授权的架构动作 |
| 6 | **新增产品的成本是「移植」不是「接入」** | 要复制一份 wrapper 并手工注册几十个闸 |
| 7 | **入口文档与实现不符（历史问题）**：入口页曾承诺若干内核并未实现的子命令 | 照入口页抄命令会失败；现以本文件为准 |
| 8 | ~~闸数统计口径与 `check --strict` 结论行不一致~~ → **已修**：改按行首 `PASS ＋ 闸门编号` 计数 | 统计值与结论行声明的项数逐轮相等 |
| 9 | ~~内核曾按全局名 `import daiban` 并调用其私有函数 `_date`~~ → **已修**：改为读取注入成员 `dbm.daiban` | 剩余口径：① 契约面上仍是私有名 `_date`；② 未提供 `daiban` 成员的端，周期待办行结构性恒回落；③ 宿主 wrapper 侧仍可能自行 import `daiban` |
| 10 | ~~`meta["zero_rules"]` 是一句无对账的声明~~ → **已修**：A1 要求声明为真**且**规则目录下 `.json` 计数为 0；无法对账记 `unverifiable` 判红 | 剩余口径：**反向闸未加**——声明零规则但目录非空且条款仍能装载时走第一分支判绿 |
| 11 | **A1 对账让内核多要一个宿主成员 `RULES_DIR`** | 该成员不在 §三 的 12 项清单内；新端口若漏给，得到的是一句 `unverifiable` 红而不是「契约要求」 |

缺陷 1–4 属**内核 API 设计**问题，缺陷 5–6 属**接线**问题，缺陷 7–8 属**文档与工具**问题，
缺陷 9–11 属「内核伸手进宿主取物」的耦合问题：9 与 11 已改为注入面，10 已加对账，剩余边界见上表。

---

## 七、防缩水机制

`engine.py` 模块级注入段维护 `_registered_gate_ids = set()`，记录**所有**注册过的闸门 id；
`set_expected(section, expected_set)` 由 wrapper 声明期望集；
`verify_registration(expected_set, edition_name="unknown")` 计算 `missing`／`extra`，有差异时返回 False。

**效果**：注释掉任意一行 `register()`，`check --strict` 立刻 FAIL。

**约束**：期望集的唯一来源是宿主 wrapper 的 `set_expected()`——内核侧不存任何 `EXPECTED_<端名>` 常量（内核不该知道端身份）。

三口径口径定义（供宿主统计使用）：

- `register` = AST 数出的 `core.register()` 调用数，**唯一权威口径**；
- `declared` = `set_expected()` 声明数；
- `runtime` = `check --strict` 结论行报出的 A 段＋B 段项数。

---

## 八、版本对应

| 层 | 版本口径 | 说明 |
|---|---|---|
| 内核 | **Bumao Core 0.10** | 唯一实现为 `engine.py` |
| 契约 | **implicit-v1** | 本文件；尚无机器校验 |
| 宿主规则库 | 由宿主 `meta` 的 `name`／`version`／`effective` 自报 | 内核不存端名与版本常量 |
| 前端核心件 | `0.10` | 以 `core_manifest.json` 清单为准（13 件） |
| 启动入口 | 由宿主 wrapper 提供 | 内核不写死入口文件名，`whoami` 从 `sys.argv[0]` 取 |

**变更约束**：

- 内核版本变更时，须同步本文件 §二（签名）与 §三（成员清单）；
- 契约成员数变更时，须同步 README 中声明的成员数；
- 前端核心件变更后，须重新生成 `core_manifest.json`。

---

## 九、核心件改动前置机制（三段，第三方可独立复跑）

核心件的改动不靠「一份契约单页」管人（2026-11-07 裁定：契约单页降为参考件，不构成约束），而靠三段机制：改不动、改了就现形、现形就有代价。

### 9.1 只读锁定（改不动）

- 覆盖：三端 `20_view/web/core_manifest.json` 登记的 13 件，共 39 件，一律 `attrib +R`。
- 工具 `kernel/suoding.py`：
  - `python -X utf8 kernel/suoding.py status` → 逐端打印「只读 x/13」与未锁清单；
  - `... lock` → 三端上锁（可 `--end <端>` 单端）；
  - `... unlock --end <端> --files a.json,b.html --why "为什么" --who "执行方" --eta 60 --impact token` → 解锁并自动追加预告行。
- 解锁即通知：绕过脚本直接 `attrib -R` 不落预告行，由 9.2 的哨兵抓到。

### 9.2 哨兵（一改就现形）

- 工具 `kernel/shaobing.py`：`run` 单轮／`run --watch 60` 常驻／`baseline` 重置快照。
- 盯 39 件的 mtime／字节数／sha256／只读属性。
- 落地 `90_lishi/core_shaobing.json`（上轮快照）＋ `90_lishi/core_bianhua_jilu.txt`（变化流水：时间｜文件｜字节前后｜sha 前后｜只读前后）。
- 原则：不阻止写入，只保证必被发现；流水可直接当证据。

### 9.3 下游阻断（现形就有代价）

- 工具 `kernel/duanxia_zuduan.py --task <screenshot|baseline|release> --end <端>`。
- 判据现跑，不读缓存：对目标端执行一次 `check --strict`，取改动类闸那一行。
  - community → `B16`（每次改动必须留痕）；
  - personal → `B48`（核心件改动必须先预告；该端 `B16` 是「全库表格体检」，不属改动类）；
  - minimal → 无 B 段（闸门体系 G01—G16），如实返回 N/A，不假装绿。
- 红即停：退出码 3，打印「因 <闸> 红，已阻断：<动作>（<端>）」。

### 9.4 预告文件与闸位

- 位置：各端 `20_view/web/gaigai_yugao.txt`（三端各一份，随端走）。
- 格式：六段固定 `时间 | 改哪几件 | 为什么 | 预计多久 | 影响面（token／接口／脱敏／基线／无） | 执行方`。
- 闸位：community `B29`／personal `B48`。对应＝文件名命中第二段＋预告时刻落在基线与该件 mtime 之间＋mtime 不晚于「预告时刻＋预计时长＋10 分钟宽限」。
- 豁免：`check_last.json`、`saojian_zuijin.json`（运行期遥测，由检查自身写盘）。
