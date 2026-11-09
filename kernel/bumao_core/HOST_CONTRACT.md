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

1. `configure()` 必须最先调用——除 `selftest --kernel` 外，未注入时任何命令都不可用；
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
| `main` | `main(argv=None)` | CLI 入口，返回值即退出码。内部只调用一次 `build_parser()`（2026-11-09 起） |
| `build_parser` | `build_parser()` | 唯一的 CLI 解析器定义；7 个子命令各注册一次 |
| `cmd_check` | `cmd_check(strict=False, quick=False)` | `check` 子命令实现；`quick=True` 只跑 A 段结构闸 |
| `cmd_whoami` | `cmd_whoami(full=False)` | `whoami` 子命令实现，恒返回 0；`full=True` 追加 4 行诊断信息 |
| `cmd_selftest` | `cmd_selftest(kernel=False)` | `selftest` 子命令实现；`kernel=True` 走内核自检，不需要宿主 |
| `cmd_selftest_kernel` | `cmd_selftest_kernel()` | 内核自检：不读宿主规则库、不写宿主账本 |

### CLI 子命令（7 个）

`whoami / check / audit / bump / show / selftest / refresh`

- `check` 支持 `--strict` 与 `--quick`：
  - `--strict` 是历史兼容参数。当前版本任何 FAIL 都会让退出码非 0（不因缺 `--strict` 而报成功），因此它不改变判据；
  - `--quick` **只跑 A 段结构闸**，跳过宿主注入的 B/Z 段、防缩水对账与检查凭据写入；结论行会明说「不能替代 `check --strict`」。
- `whoami` 支持 `--full`：追加内核路径、Python 版本、规则目录、子命令清单 4 行；不带 `--full` 时输出与历史版本逐字一致。
- `bump` 支持 `--level`（默认 `L1`）；
- `show` 需要一个条款 id；
- `selftest` 支持 `--kernel`：内核自检（无宿主）；不带 `--kernel` 时是宿主集成自检，未注入 `rules_db` 会打印「内核自检需宿主注入规则库（rules_db）」并返回 `2`。

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

### 随包的 `bumao_core_rules.py` 是参考实现，**不参与运行时**

`bumao_core/bumao_core_rules.py` 只演示三种历史规则目录格式（`zhunze/`、`ZH/`、`rules/`）如何被解析，
**不满足上表 12 成员契约**：缺 `load()`、`dup_ids()`、`render_all()` 与模块级 `ROOT`
（它提供的是 `load_db()`／`duplicate_ids()`）。

- 内核 `engine.py` 对本模块**零引用**，三端 wrapper 也零引用；
- **不得**把本模块直接传给 `configure()`——缺成员会在第一条命令就抛异常；
- 真实接入路径是自备一个满足 12 成员的 `rules_db`，可直接复制运行的最小样例见仓库根目录
  `examples/minimal_host.py`。

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
| 包安装能力 | 提供 `pyproject.toml`（可 `pip install -e .`）与 `__init__.py`；同时保留 `sys.path.insert` 扁平加载（见 §五） |
| 闸门清单 | 闸门由宿主 wrapper 显式 `register()` 提供，**不是数据驱动** |

**它是什么**：CLI 式**规则执行／治理框架**。卖点是「执行可信」——宿主定下的规矩被不折不扣执行，
结论不能被偷偷放宽、跳过或伪造（防缩水机制见 §七）。
**它不是什么**：不是应用运行时。Web 应用、游戏、桌面软件不会「跑在它上面」，只会「调它做一次 check」。

---

## 五、加载方式（两种，任选其一）

**方式 A：包安装（2026-11-09 起）**

```bash
pip install -e .
```

```python
from bumao_core import engine
```

**方式 B：目录硬绑（历史用法，保持可用）**

```python
sys.path.insert(0, "<内核目录绝对路径>")
import engine
```

**约束**：

- 两种方式加载的是同一份 `engine.py`；包内部互相导入已同时兼容相对导入与扁平导入，行为一致。
- 内核目录可整体搬走；搬走后方式 B 仍成功，因为内核不依赖工程树位置。
- 未 `configure()` 时运行 `whoami` 会打印 `[ERROR] whoami failed: rules_db not configured. Call configure() first.` 并返回退出码 1，CI 可据此判失败。
- 未 `configure()` 时运行 `selftest` 会打印「内核自检需宿主注入规则库（rules_db）；独立运行请用：`python -m bumao_core.engine selftest --kernel`」并返回退出码 2；`selftest --kernel` 不需要任何宿主文件。
- 闸门模板文件 `bumao_core_gates.py` 采用**宿主注入契约**：模板只接受 `drift_func`／`targets_func`／`clauses_func` 这类可调用对象，取不到注入一律判 **FAIL** 并写明缺哪个注入名；文件内不 `import render`，不设「取不到就返回 True」的兜底。
- 现有 13 个闸门模板（`make_drift_gate` 等）均可在内核目录之外单文件载入执行。

---

## 六、已知缺陷（写在这里，不藏）

| # | 缺陷 | 影响 |
|---|---|---|
| 1 | ~~契约是隐式的，全库没有接口定义、类型约定或最小示例~~ → **已修（2026-11-09）**：新增 `examples/minimal_host.py`（不依赖三仓、可直接跑出一次真实 check）与 `pyproject.toml`；接口说明仍以本文件为准，未引入机器可校验 schema | 契约仍无机器校验 |
| 2 | 契约里**含私有成员 `_inner`** | 私有成员进了对外契约；文档只能描述它，消不掉它 |
| 3 | **`render_all` 各宿主端皆无**，且调用点有 `hasattr` 守卫 | 功能静默缺失，全绿也照不出来 |
| 4 | ~~闸门模板硬依赖宿主的 `render` 模块~~ → **已修**：改为宿主注入函数，取不到即判 FAIL | 内核目录已自包含，坏依赖不再被 `except ImportError` 静默吞掉 |
| 5 | **闸门模板接线不完整**：部分宿主端只 import 不调用；G 族模板从未被 `core.register` 注册 | 已写好的能力取不出来；挂载需改闸门数，属未授权的架构动作 |
| 6 | **新增产品的成本是「移植」不是「接入」** | 要复制一份 wrapper 并手工注册几十个闸 |
| 7 | **入口文档与实现不符（历史问题）**：入口页曾承诺若干内核并未实现的子命令。**2026-11-09 起** `--quick`／`--full`／`--kernel` 已真实实现并写进本文件与 README；`--strict` 明确为历史兼容参数 | 照旧版入口页抄命令仍可能失败，现以本文件为准 |
| 8 | ~~闸数统计口径与 `check --strict` 结论行不一致~~ → **已修**：改按行首 `PASS ＋ 闸门编号` 计数 | 统计值与结论行声明的项数逐轮相等 |
| 9 | ~~内核曾按全局名 `import daiban` 并调用其私有函数 `_date`~~ → **已修**：改为读取注入成员 `dbm.daiban` | 剩余口径：① 契约面上仍是私有名 `_date`；② 未提供 `daiban` 成员的端，周期待办行结构性恒回落；③ 宿主 wrapper 侧仍可能自行 import `daiban` |
| 10 | ~~`meta["zero_rules"]` 是一句无对账的声明~~ → **已修**：A1 要求声明为真**且**规则目录下 `.json` 计数为 0；无法对账记 `unverifiable` 判红 | 剩余口径：**反向闸未加**——声明零规则但目录非空且条款仍能装载时走第一分支判绿 |
| 11 | **A1 对账让内核多要一个宿主成员 `RULES_DIR`** | 该成员不在 §三 的 12 项清单内；新端口若漏给，得到的是一句 `unverifiable` 红而不是「契约要求」 |
| 12 | ~~`build_parser()` 重复注册 `check` 子命令，调用即抛 `argparse.ArgumentError: conflicting subparser: check`（beta.3／beta.4 均中）~~ → **已修（2026-11-09）**：只注册一次，`main()` 复用同一个解析器；回归用例 `bumao_core/test_build_parser.py` | 已发布的 beta.3／beta.4 包仍带此缺陷 |

缺陷 1–4 属**内核 API 设计**问题，缺陷 5–6 属**接线**问题，缺陷 7–8 属**文档与工具**问题，
缺陷 9–11 属「内核伸手进宿主取物」的耦合问题：9 与 11 已改为注入面，10 已加对账，剩余边界见上表；
缺陷 12 属**CLI 注册**问题，已由回归用例锁定。

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

---

## 十、契约范围外的内部件（N/A 判定）

以下三件**不属于宿主契约面**，公开仓不随包。`contract_test.py` 对它们判 `[N/A]`（不适用），
既不计 FAIL，也不计 SKIP；若使用者自备同名文件放进 `bumao_core/`，它们仍参与编译与隔离扫描。
这不是「缺件所以跳过」，而是按契约范围作出的判定：

| 件 | 为什么不属契约面 |
|---|---|
| `facts.py` | 内部文档事实源生成器：扫描内部多端目录树（台账／视图／规则层）产出 `facts.json`。宿主接入不需要它，它的输入在公开仓不存在。 |
| `facts_check.py` | `facts.py` 的配套校验器：唯一输入是内部 `facts.json`。没有生成器，它没有可校验对象。 |
| `portability_probe.py` | 内部可迁移性探针：按内部目录树与本机临时区布局编写，含主机绝对路径形态；脱敏即失去原功能，故不随包。 |

契约内的核心件（`CORE_FILES`）仍是硬依赖：缺一件、空一件、编译不过一件，都判 FAIL。

---

## 十一、随包运行层（`bumao_core/jiancha/`，0.2.2 起）

运行层是「执行中监管」的实现，**随包但不参与内核判定**：`engine.py` 不导入它，`selftest --kernel` 与 `contract_test.py` 不依赖它。

```
bumao_core/jiancha/
  supervisor.py        中断 / 恢复 / 停机状态机
  ledger.py            只追加、带哈希链的动作账本
  scope.py             in_scope / 冻结区 / 区根外入口解析
  reasons.py           错误码查表
  qingli.py            证据束与基线的留存清理
  personal_adapter.py  宿主布局适配器（裸仓不生效）
  gate_check.py        宿主闸门 A/B 自检（依赖宿主布局）
  jiancha_canshu.json  运行参数
  schema/reason_codes.json 错误码表（含 RESTORE_FAILED）
```

- **默认关闭（0.2.2 起有装载器）**：`bumao_core.jiancha.loader.load_if_enabled()` 仅在 `BUMO_JIANCHA_MODE` 为 `shadow`／`enforce` 时加载；未设、`off`、未知值一律返回 `None`，不建目录、不写账。`engine.py` 不导入运行层。
- **相对导入**：包内一律 `from . import ...`。宿主 `10_rac/` 下已有同名 `ledger.py`（另一套账本），不得用 `sys.path` 插入后绝对导入，否则会顶掉宿主模块。
- **契约边界**：运行层不改变宿主必须实现的 12 个成员，也不改变任何内核判定；它只消费宿主注入的事件与文件树。
- **状态口径**：恢复遇失败即中止整轮、已恢复件保留；不新增 `partial` 状态；失败码 `RESTORE_FAILED`。

---

# English（HOST_CONTRACT）

# bumao_core Host Contract（HOST CONTRACT）

> This document answers one question: **what must an external product implement in order to integrate with this kernel.**
> The kernel itself carries no rules, no business logic and no edition name; rules, the gate list and paths are all supplied by the host.
>
> This document describes the contract only; it does not constitute authorization to start work.

- Kernel version this contract corresponds to: **Bumao Core 0.10** (`engine.py` is the sole runtime implementation)
- Contract version: **implicit-v1** (no machine validation yet, see §六 defect 1)
- Applies to: any host edition. A host edition consists of two parts——**wrapper** (the startup entry, responsible for injection and registration) and **rules_db** (the rules library module, responsible for data and check functions).
- Source of version numbers: the kernel itself stores no edition name; at runtime it takes `name` / `version` / `effective` from the host `meta`.

---

## 一、Four Steps of Integration

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

**Order constraints**:

1. `configure()` must be called first——except for `selftest --kernel`, no command is available before injection;
2. `set_expected()` must be called after all `register()` calls are complete;
3. `main()` is called last, and its return value is the process exit code.

The host wrapper must perform these five actions itself: `import engine as core`, `configure(rules_db_module=...)`, `register(...)` one by one, `set_expected(...)`, `sys.exit(core.main(...))`. The kernel does none of them on the host's behalf.

---

## 二、Public Function Signatures of the Kernel

| Function | Signature | Notes |
|---|---|---|
| `configure` | `configure(rules_db_module=None)` | **Must be called first.** Only stores the module into the global `_rdb` |
| `register` | `register(gid, fn, label, section="B")` | Registers a single gate. `section` takes `"B"` (physical gate) or `"Z"` (criteria gate); any other value falls into B |
| `register_all` | `register_all(category_fn_map, category="B")` | Batch-registers from a `{gid: fn}` dict, with label fixed to `"(auto-discovered)"`; returns the list of registered gids |
| `set_expected` | `set_expected(section, expected_set)` | Declares the expected gate set for this edition. **Must be called after all `register()` calls** |
| `verify_registration` | `verify_registration(expected_set, edition_name="unknown")` | Anti-shrinkage validation: computes `missing = expected - registered`, `extra = registered - expected` |
| `main` | `main(argv=None)` | CLI entry; the return value is the exit code. Internally calls `build_parser()` only once (since 2026-11-09) |
| `build_parser` | `build_parser()` | The single CLI parser definition; 7 subcommands, each registered once |
| `cmd_check` | `cmd_check(strict=False, quick=False)` | `check` subcommand implementation; `quick=True` runs only section A structural gates |
| `cmd_whoami` | `cmd_whoami(full=False)` | `whoami` subcommand implementation, always returns 0; `full=True` appends 4 lines of diagnostic information |
| `cmd_selftest` | `cmd_selftest(kernel=False)` | `selftest` subcommand implementation; `kernel=True` runs the kernel self-test, which needs no host |
| `cmd_selftest_kernel` | `cmd_selftest_kernel()` | Kernel self-test: reads no host rules library, writes no host ledger |

### CLI subcommands (7)

`whoami / check / audit / bump / show / selftest / refresh`

- `check` supports `--strict` and `--quick`:
  - `--strict` is a legacy-compatible flag. In the current version any FAIL makes the exit code non-zero (it does not report success merely because `--strict` is absent), so it does not change the criteria;
  - `--quick` **runs only section A structural gates**, skipping the host-injected B/Z sections, the anti-shrinkage reconciliation and the writing of the check credential; the conclusion line states explicitly that it "cannot replace `check --strict`".
- `whoami` supports `--full`: appends 4 lines——kernel path, Python version, rules directory, subcommand list; without `--full` the output is verbatim identical to historical versions.
- `bump` supports `--level` (default `L1`);
- `show` requires a clause id;
- `selftest` supports `--kernel`: kernel self-test (no host); without `--kernel` it is the host integration self-test, and if `rules_db` has not been injected it prints "内核自检需宿主注入规则库（rules_db）" and returns `2`.

**Exit code convention**: `0` means everything passed or the command completed normally; non-`0` means a FAIL exists, an exception occurred, or there is a parameter error.
`cmd_whoami` is the exception: when drift is non-zero it prints "未接入（先 render.py write）" but still returns 0——the stop criterion is borne by `check --strict`.

If the host entry documentation disagrees with the commands in this document, **this document prevails**; the kernel actually registers only the 7 subcommands listed above.

---

## 三、The Rules Library Module (`rules_db`) the Host Must Provide —— 12 Members

After `configure(rules_db_module=X)`, the kernel records `X` as `dbm` and accesses it as in the following table.

| # | Member | Required? | Guard | Semantics |
|---|---|---|---|---|
| 1 | `load()` | **Required** | none | Loads the raw rule data |
| 2 | `index(db)` | **Required** | none | Builds the index; **the return value must be a dict containing the three keys `meta` / `clauses` / `chapters`** |
| 3 | `load_meta()` | **Required** | none | Returns a dict; the kernel takes the three keys `name` / `version` / `effective` |
| 4 | `dup_ids(db)` | **Required** | none | Returns a list of duplicate ids; **an empty list `[]` means there are no duplicates** |
| 5 | `block_broken(clauses)` | **Required** | none | Block-broken check |
| 6 | `shell_clauses(db)` | **Required** | none | Empty-shell clause check |
| 7 | `ROOT` | optional | yes | Product root directory, level 1 of the four-level fallback |
| 8 | `_inner.ROOT` | optional | yes | **Private member**, level 2 |
| 9 | `HERE` | optional | yes | Level 3; if all three levels are missing it falls back to `os.path.dirname(directory containing the engine)` |
| 10 | `render_all(meta, db)` | optional | yes | Renders all views, returns the number rendered |
| 11 | `check_drift()` | optional | yes (`getattr` + `sys.modules` double fallback) | Returns a drift list; `whoami` uses it to print "视图漂移：N 处" and "接入状态" |
| 12 | `daiban` (**module object**, must contain `parse()` and `_date()`) | optional | yes | Data source for recurring todos; the kernel does **not** `import` a global module name, it only reads the injected member |

**Constraints**:

- Items 1–6 have no `hasattr` guard; missing any one raises an exception immediately and the command fails.
- Items 7–9 are used for the product root directory fallback; the whole block has `try/except`, so all being absent does not crash.
- Resolution order for item 11: first take the injected `dbm.check_drift`; then fall back to `check_drift` on the host's **already-imported** `render` / `rules_render` modules; if neither is available it prints "视图漂移：宿主未提供 check_drift，无法计算" + "接入状态：未就绪（漂移未算出）"——**when it cannot get the value it says so; no fake numbers**.
- When item 12 is unavailable, it outputs the fixed fallback line per the "Recurring-todo fallback contract" below; this is not counted as a defect.
- Item 8 is a private member, but it has already entered the external contract (see §六 defect 2).

### The bundled `bumao_core_rules.py` is a reference implementation and **does not participate in runtime**

`bumao_core/bumao_core_rules.py` only demonstrates how the three historical rule directory formats (`zhunze/`, `ZH/`, `rules/`) are parsed;
**it does not satisfy the 12-member contract above**: it lacks `load()`, `dup_ids()`, `render_all()` and a module-level `ROOT`
(what it provides is `load_db()` / `duplicate_ids()`).

- The kernel `engine.py` has **zero references** to this module, and the three edition wrappers also have zero references;
- **Do not** pass this module directly to `configure()`——missing members will raise an exception on the very first command;
- The real integration path is to provide your own `rules_db` that satisfies the 12 members; a minimal runnable example that can be copied directly is at the repository root
  `examples/minimal_host.py`.

### Recurring-todo fallback contract (settled 2026-11-08)

When item 12 is missing, or the member does not contain `parse` / `_date`, **the fallback text is the contractual behavior**: it is not treated as a defect, and the core logic of neither edition is changed. The fixed output must be verbatim identical (including the trailing file name):

```
周期待办：宿主 rules_db 未注入 daiban 成员（须含 parse／_date）——须手读宿主规程目录下 daiban_zongbiao.txt
```

Constraints:

- `whoami` must exit with code 0, and that line must be verbatim identical to the line above; it must not raise an exception and must not fabricate a count.
- The two open-source editions (community / minimal) do not provide `daiban.py`; that is a normal form within the contract; personal provides the data source and outputs real todos.
- Acceptance method: run `whoami` on both editions and compare the whole "周期待办：" line; it must be byte-for-byte identical.

### Zero-rule editions: `meta["zero_rules"]` + rules-directory member `RULES_DIR`

The A1 criterion is:

```
(n_ch > 0 and n_cls > 0) or (meta["zero_rules"] 为真 and 规则目录下 .json 计数为 0)
```

When declaring `zero_rules`, the host must additionally expose the rules-directory member `RULES_DIR` (when the directory is unavailable the kernel falls back to reading `ZH`).
`RULES_DIR` **is not among the 12 contract members in the table above**; it is an additional hard requirement for zero-rule editions.

| Case | A1 verdict |
|---|---|
| Has effective clauses | **PASS** (takes the first branch, does not count the directory) |
| Declares `zero_rules` and the `.json` count in the rules directory is 0 | **PASS** |
| Declares `zero_rules` but the rules directory contains `.json` files | **FAIL** |
| Declares `zero_rules` but the rules directory is not exposed / does not exist | **FAIL** (detail records `unverifiable`) |
| Declares `zero_rules`, directory not empty, **and clauses can be loaded** | Takes the first branch and is ruled green (**no reverse gate added**) |

### Optional host extension members (not contractually required)

Besides the 12 items above, the kernel also reads several host extensions via `getattr`; when they are absent each command falls back, which does not affect the validity of the contract:

- `META_PATH` —— `bump` locates the meta file;
- `ZH` —— the second candidate for the rules directory;
- `enforce_decl` —— A12 mandatory / restrictive clause and gate-slot wiring;
- `record_check_result` —— check result write-back.

---

## 四、What the Kernel Does Not Provide (Capability Boundary)

| Not provided | Criterion |
|---|---|
| Any concrete rule | 0 inside the kernel; all rules are in the host rule package |
| Any edition name / business name | No edition name and no business name inside `engine.py` |
| Any service / SDK / IPC | In all kernel `.py` files there is no `http` / `socket` / `grpc` / `daemon` / `server` / `api` |
| Package installation capability | Provides `pyproject.toml` (`pip install -e .` works) and `__init__.py`; the flat `sys.path.insert` loading is retained at the same time (see §五) |
| Gate list | Gates are supplied by the host wrapper's explicit `register()`, **not data-driven** |

**What it is**: a CLI-style **rule execution / governance framework**. Its selling point is "trustworthy execution"——rules set by the host are executed to the letter, and conclusions cannot be silently relaxed, skipped or forged (the anti-shrinkage mechanism is described in §七).
**What it is not**: it is not an application runtime. Web apps, games and desktop software do not "run on top of it"; they only "call it to perform one check".

---

## 五、Loading Methods (two, choose either)

**Method A: package installation (since 2026-11-09)**

```bash
pip install -e .
```

```python
from bumao_core import engine
```

**Method B: directory hard-binding (historical usage, kept working)**

```python
sys.path.insert(0, "<内核目录绝对路径>")
import engine
```

**Constraints**:

- Both methods load the same `engine.py`; intra-package imports are already compatible with both relative and flat imports, with identical behavior.
- The kernel directory can be moved wholesale; after moving, Method B still succeeds because the kernel does not depend on its position in the project tree.
- Running `whoami` without `configure()` prints `[ERROR] whoami failed: rules_db not configured. Call configure() first.` and returns exit code 1, so CI can fail on it.
- Running `selftest` without `configure()` prints "内核自检需宿主注入规则库（rules_db）；独立运行请用：`python -m bumao_core.engine selftest --kernel`" and returns exit code 2; `selftest --kernel` needs no host files at all.
- The gate template file `bumao_core_gates.py` adopts the **host injection contract**: templates accept only callables such as `drift_func` / `targets_func` / `clauses_func`; if the injection is unavailable it is ruled **FAIL** and states which injection name is missing; the file does not `import render` and has no "return True if unavailable" fallback.
- All 13 existing gate templates (such as `make_drift_gate`) can be loaded and executed as single files outside the kernel directory.

---

## 六、Known Defects (written here, not hidden)

| # | Defect | Impact |
|---|---|---|
| 1 | ~~The contract is implicit; the whole repository has no interface definition, type convention or minimal example~~ → **Fixed (2026-11-09)**: added `examples/minimal_host.py` (does not depend on the three repositories and can directly produce one real check) and `pyproject.toml`; the interface description is still governed by this document, and no machine-validatable schema has been introduced | The contract still has no machine validation |
| 2 | The contract **contains the private member `_inner`** | A private member has entered the external contract; the document can only describe it, not remove it |
| 3 | **`render_all` is absent on every host edition**, and the call site has a `hasattr` guard | The feature is silently missing; even an all-green run cannot reveal it |
| 4 | ~~Gate templates hard-depend on the host's `render` module~~ → **Fixed**: changed to host-injected functions, unavailable means FAIL | The kernel directory is now self-contained; broken dependencies are no longer silently swallowed by `except ImportError` |
| 5 | **Gate template wiring is incomplete**: some host editions only import without calling; G-family templates are never registered by `core.register` | Capabilities already written cannot be taken out; mounting them would change the gate count, which is an unauthorized architectural action |
| 6 | **The cost of a new product is "porting", not "integrating"** | A wrapper must be copied and dozens of gates registered by hand |
| 7 | **Entry documentation does not match the implementation (a historical issue)**: the entry page once promised several subcommands the kernel never implemented. **Since 2026-11-09** `--quick` / `--full` / `--kernel` are actually implemented and written into this document and the README; `--strict` is explicitly a legacy-compatible flag | Copying commands from the old entry page may still fail; this document now prevails |
| 8 | ~~The gate-count statistic is inconsistent with the conclusion line of `check --strict`~~ → **Fixed**: counting now follows line-leading `PASS + gate number` | The statistic equals the item count declared in the conclusion line on every round |
| 9 | ~~The kernel once imported `daiban` by global name and called its private function `_date`~~ → **Fixed**: changed to reading the injected member `dbm.daiban` | Remaining scope: ① the contract surface still contains the private name `_date`; ② editions that do not provide the `daiban` member structurally always fall back on the recurring-todo line; ③ host wrappers may still import `daiban` themselves |
| 10 | ~~`meta["zero_rules"]` was a declaration with no reconciliation~~ → **Fixed**: A1 requires the declaration to be true **and** the `.json` count in the rules directory to be 0; when reconciliation is impossible it records `unverifiable` and rules red | Remaining scope: **no reverse gate added**——when zero rules are declared but the directory is not empty and clauses can still be loaded, the first branch is taken and it is ruled green |
| 11 | **A1 reconciliation makes the kernel require one more host member, `RULES_DIR`** | That member is not in the 12-item list of §三; a new edition that omits it gets an `unverifiable` red instead of a "contract requirement" |
| 12 | ~~`build_parser()` registers the `check` subcommand twice, so calling it raises `argparse.ArgumentError: conflicting subparser: check` (both beta.3 / beta.4 are affected)~~ → **Fixed (2026-11-09)**: registered only once, `main()` reuses the same parser; regression case `bumao_core/test_build_parser.py` | The released beta.3 / beta.4 packages still carry this defect |

Defects 1–4 are **kernel API design** issues, defects 5–6 are **wiring** issues, defects 7–8 are **documentation and tooling** issues,
defects 9–11 are coupling issues of "the kernel reaching into the host to take things": 9 and 11 have been changed to the injection surface, 10 has had reconciliation added, and the remaining boundaries are as in the table above;
defect 12 is a **CLI registration** issue, now locked down by a regression case.

---

## 七、Anti-Shrinkage Mechanism

The module-level injection section of `engine.py` maintains `_registered_gate_ids = set()`, recording **all** gate ids ever registered;
`set_expected(section, expected_set)` has the wrapper declare the expected set;
`verify_registration(expected_set, edition_name="unknown")` computes `missing` / `extra` and returns False when there is any difference.

**Effect**: commenting out any single `register()` line makes `check --strict` fail immediately.

**Constraint**: the sole source of the expected set is the host wrapper's `set_expected()`——the kernel side stores no `EXPECTED_<edition>` constant (the kernel should not know edition identity).

Definitions of the three measures (for host statistics):

- `register` = the number of `core.register()` calls counted by AST, **the only authoritative measure**;
- `declared` = the number declared by `set_expected()`;
- `runtime` = the number of section A + section B items reported in the conclusion line of `check --strict`.

---

## 八、Version Correspondence

| Layer | Version measure | Notes |
|---|---|---|
| Kernel | **Bumao Core 0.10** | The sole implementation is `engine.py` |
| Contract | **implicit-v1** | This document; no machine validation yet |
| Host rules library | Self-reported via the host `meta`'s `name` / `version` / `effective` | The kernel stores no edition name or version constant |
| Frontend core files | `0.10` | As per the `core_manifest.json` manifest (13 files) |
| Startup entry | Provided by the host wrapper | The kernel does not hard-code the entry file name; `whoami` takes it from `sys.argv[0]` |

**Change constraints**:

- When the kernel version changes, §二 (signatures) and §三 (member list) of this document must be updated in sync;
- When the number of contract members changes, the member count declared in the README must be updated in sync;
- After frontend core files change, `core_manifest.json` must be regenerated.

---

## 九、Pre-Change Mechanism for Core File Changes (three stages, independently re-runnable by third parties)

Changes to core files are not governed by "a single contract page" (2026-11-07 ruling: the contract page is downgraded to a reference document and does not constitute a constraint), but by a three-stage mechanism: it cannot be changed, once changed it shows, and once it shows there is a cost.

### 9.1 Read-only lock (cannot be changed)

- Coverage: the 13 files registered in `20_view/web/core_manifest.json` on the three editions, 39 files in total, all `attrib +R`.
- Tool `kernel/suoding.py`:
  - `python -X utf8 kernel/suoding.py status` → prints "只读 x/13" and the list of unlocked files, per edition;
  - `... lock` → locks all three editions (single edition via `--end <edition>`);
  - `... unlock --end <edition> --files a.json,b.html --why "why" --who "executor" --eta 60 --impact token` → unlocks and automatically appends a notice line.
- Unlocking is notification: bypassing the script with a direct `attrib -R` leaves no notice line, and the sentinel in 9.2 catches it.

### 9.2 Sentinel (shows as soon as it changes)

- Tool `kernel/shaobing.py`: `run` for a single round / `run --watch 60` to stay resident / `baseline` to reset the snapshot.
- Watches the mtime / byte size / sha256 / read-only attribute of the 39 files.
- Produces `90_lishi/core_shaobing.json` (previous-round snapshot) + `90_lishi/core_bianhua_jilu.txt` (change log: time | file | bytes before/after | sha before/after | read-only before/after).
- Principle: it does not prevent writes, it only guarantees that writes are discovered; the log can serve directly as evidence.

### 9.3 Downstream blocking (showing has a cost)

- Tool `kernel/duanxia_zuduan.py --task <screenshot|baseline|release> --end <edition>`.
- The criterion is evaluated live, not read from cache: run `check --strict` once against the target edition and take the line of the change-type gate.
  - community → `B16` (every change must leave a trace);
  - personal → `B48` (core file changes must be announced in advance; that edition's `B16` is "whole-repository table health check" and is not change-type);
  - minimal → no section B (gate system G01—G16), truthfully returns N/A and does not pretend to be green.
- Red means stop: exit code 3, prints "因 <闸> 红，已阻断：<动作>（<端>）".

### 9.4 Notice file and gate slots

- Location: `20_view/web/gaigai_yugao.txt` on each edition (one per edition, traveling with the edition).
- Format: six fixed segments `时间 | 改哪几件 | 为什么 | 预计多久 | 影响面（token／接口／脱敏／基线／无） | 执行方`.
- Gate slots: community `B29` / personal `B48`. Match = the file name hits the second segment + the notice time falls between the baseline and that file's mtime + the mtime is no later than "notice time + estimated duration + 10 minutes grace".
- Exemptions: `check_last.json`, `saojian_zuijin.json` (runtime telemetry, written by the check itself).

---

## 十、Internal Files Outside the Contract Scope (N/A determination)

The following three files **do not belong to the host contract surface** and are not shipped in public repositories. `contract_test.py` rules them `[N/A]` (not applicable),
counting them neither as FAIL nor as SKIP; if a user supplies files of the same names inside `bumao_core/`, they still participate in compilation and isolation scanning.
This is not "skipping because files are missing", but a determination made according to the contract scope:

| File | Why it is not in the contract surface |
|---|---|
| `facts.py` | Internal document fact-source generator: scans the internal multi-edition directory tree (ledger / views / rule layer) and produces `facts.json`. Host integration does not need it; its input does not exist in the public repository. |
| `facts_check.py` | The companion validator of `facts.py`: its only input is the internal `facts.json`. Without the generator it has nothing to validate. |
| `portability_probe.py` | Internal portability probe: written against the internal directory tree and the local machine's scratch-area layout, containing host absolute-path forms; desensitizing it would destroy its original function, so it is not shipped. |

Core files within the contract (`CORE_FILES`) remain hard dependencies: one missing, one empty, or one that fails to compile is a FAIL.

---

## 十一、Bundled Runtime Layer (`bumao_core/jiancha/`, since 0.2.2)

The runtime layer is the implementation of "in-execution supervision"; it is **bundled but does not participate in kernel verdicts**: `engine.py` does not import it, and neither `selftest --kernel` nor `contract_test.py` depends on it.

```
bumao_core/jiancha/
  supervisor.py        中断 / 恢复 / 停机状态机
  ledger.py            只追加、带哈希链的动作账本
  scope.py             in_scope / 冻结区 / 区根外入口解析
  reasons.py           错误码查表
  qingli.py            证据束与基线的留存清理
  personal_adapter.py  宿主布局适配器（裸仓不生效）
  gate_check.py        宿主闸门 A/B 自检（依赖宿主布局）
  jiancha_canshu.json  运行参数
  schema/reason_codes.json 错误码表（含 RESTORE_FAILED）
```

- **Off by default (loader available since 0.2.2)**: `bumao_core.jiancha.loader.load_if_enabled()` loads only when `BUMO_JIANCHA_MODE` is `shadow`／`enforce`; when unset, `off` or an unknown value it always returns `None`, creating no directory and writing no ledger. `engine.py` does not import the runtime layer.
- **Relative imports**: inside the package always use `from . import ...`. The host's `10_rac/` already contains a `ledger.py` of the same name (a different ledger); do not insert it via `sys.path` and then import it absolutely, otherwise it will shadow the host module.
- **Contract boundary**: the runtime layer does not change the 12 members the host must implement, nor any kernel verdict; it only consumes the events and file trees injected by the host.
- **State convention**: on restore failure the whole round is aborted and already-restored items are retained; no new `partial` state is introduced; the failure code is `RESTORE_FAILED`.
