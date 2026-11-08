# Bumao XTGL Minimal · 运行说明

这是**极简版控制台**：零规则内核，只带示例模板，按需注入规则包。只读、不联网、不需要数据库，也不需要 `pip install`。

- 本端：**Bumao XTGL Minimal 0.10**（开源规则框架）
- 端口：**8804**（以 `web_config.json` 的 `port` 为准）
- 内核：`xtgl_core.py`（本端自带，不依赖外部服务）
- 默认打开能力：`gate`、`backup`
- 生效规则：**0 条**（`10_rac/rules/` 只有 `.gitkeep`；示例模板在 `00_meta/rules_library/examples/`）

---

## 30 秒启动

```bash
cd 20_view/web
python serve.py
```

前置只有 Python 3.12.14。启动后终端打印地址，浏览器自动打开。

| 启动方式 | 命令 |
|---|---|
| 按配置启动 | `python serve.py` |
| 临时指定项目 | `python serve.py --root "/path/to/another-project"` |
| 演示数据 | `python serve.py --demo` |
| 不开浏览器 | `python serve.py --no-browser` |

Windows 可双击 `qidong_kongzhitai.bat`。端口被占用会自动向后找，以终端打印地址为准。

---

## 打开后你会看到什么

只有 **1 个页签、3 张卡**：

| 卡片 | 数据来源 |
|---|---|
| 项目元信息 | `00_meta/meta.json` |
| 闸门自检 | 真实运行 `check --strict`，不是 mock |
| 归档 | `90_lishi/` 只列不删 |

没有规则条款清单、没有任务板、没有 AI、没有缺陷台账、没有接入名册、没有三端取数、没有路径地图、没有导出——这些都在包里，不放就不出现。

---

## 零规则怎么变有规则：放规则包

规则包目录：`00_meta/rules_library/packs/`，格式见 `schema.json`。

现成模板：`00_meta/rules_library/examples/example-template.json`，复制改名放进 `packs/`，按格式填自己的规则：

```json
{
  "id": "logging",
  "name": "日志与复审",
  "name_en": "Logging",
  "applies_to": ["minimal"],
  "depends_on": ["evidence"],
  "enabled": false,
  "rules": [
    {"id": "log-four-layers", "action": "require", "scope": "log",
     "params": {}, "desc": "日志按天／时间／项目／客户端四层登记"}
  ]
}
```

启用改为 `"enabled": true`，然后：

```bash
python 20_view/web/module_check.py
python 10_rac/BumaoXTGL_Minimal_v01.py check --strict
```

全绿才算生效。`enabled=false` 的包不进快照、不显示、不生效。

---

## 放功能包：放一个，多一块面板

功能包目录：`00_meta/feature_packs/`，一个包一个 JSON：

```json
{
  "schema": 1,
  "id": "f01_jieru",
  "name": "接入名册",
  "name_en": "Client roster",
  "enabled": false,
  "capabilities": ["clients"],
  "applies_to": ["community", "minimal"],
  "note": "把日志 who 列汇总成接入名册"
}
```

- `capabilities` 只能写 `modules.json` 里已有的 id；
- `enabled=true` 的包启动时并入本端能力表，对应面板才出现；
- 不放包，页签和卡片不会多出一张；
- 两个现成包：`f01_jieru.json`（接入名册）、`f02_lishi.json`（日志日历）。

启用：改 `enabled` 为 `true`，重启 `serve.py`。查看加载情况：`GET /api/packages`。

---

## 日志四层

日志按 **天 → 时间 → 项目 → 客户端** 四层展示：

1. **天**：`YYYY-MM-DD`；
2. **时间**：`HH:MM:SS`；
3. **项目**：`40_renwu/` 下一级目录名；
4. **客户端**：日志 `who` 列，没登记不算接入。

每次更新登记一条：

```bash
python 10_rac/BumaoXTGL_Minimal_v01.py log --file <本次留档> --what "..."
```

---

## 接口

| 接口 | 用途 |
|---|---|
| `GET /api/overview` | 元信息、规则层、闸门 |
| `GET /api/env` | 环境自检 |
| `GET /api/modules` | 能力定义表 |
| `GET /api/packages` | 规则包／功能包加载情况 |
| `GET /api/config` | 本端能力表 |
| `POST /api/setup/save` | 写 `web_config.json` |

---

## 边界

- 只监听 `127.0.0.1`，不做鉴权，不要暴露到公网；
- 必须经 `serve.py` 打开；
- 闸门是真实执行，大项目会跑十几秒；
- 子进程统一 UTF-8，使用同一个解释器；
- 演示数据是合成的，页面会标「演示数据」。

---

## 自检

```bash
python module_check.py
python kernelsync.py --check
python -m unittest discover -s tests -v
```
