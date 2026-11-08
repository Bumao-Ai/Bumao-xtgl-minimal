# Bumao XTGL Minimal（骨架版）

一句话：它不提供规矩，只规定「规矩该怎么写，机器才认」。本仓带内核接入骨架与 28 条示例模板，**不带任何生效规则**。

- 运行时依赖：**纯 Python 标准库**，要求 **Python 3.12 或更高**，不需要 `pip install`。
- 本仓是四个独立仓库之一，**已内置内核**（`kernel/bumao_core/`），克隆后可直接运行。
- 想要「装上就能用的一套规则」，请用 `bumao-xtgl-community`；本仓只有骨架。

## 内核已内置

入口脚本按 `10_rac/../kernel/bumao_core` 查找内核，内核随本仓一起分发，克隆后无需另装：

```
bumao-xtgl-minimal/
├── kernel/
│   └── bumao_core/          ← 已随本仓内置（源头为 bumao-core 仓）
├── 10_rac/
│   └── BumaoXTGL_Minimal_v01.py
└── 20_view/
```

内核只有一份源头：`bumao-core` 仓。内核更新时，用 `bumao-core` 的 `bumao_core/` **整目录覆盖**本仓 `kernel/bumao_core/`，不做逐文件合并；覆盖后比对哈希是否一致即可。

## 30 秒跑起来

```bash
cd 10_rac
python BumaoXTGL_Minimal_v01.py whoami
python render.py write      # 真身 → 视图（views/ 下只读产物）
python BumaoXTGL_Minimal_v01.py check --strict
```

`check --strict` 输出唯一结论。首次运行时，A10／A13 两个「授权留痕」闸门会报缺件：公开仓不携带内部审批记录，这是预期差异；功能类闸门不受影响。

Web 控制台：

```bash
cd 20_view/web
python serve.py
```

默认端口 8804（见 `web_config.json`，端口被占用时会自动向后寻找）。Windows 也可以直接双击 `20_view/web/qidong_kongzhitai.bat`。

## 加一条自己的规矩（四步，不许跳）

1. 编辑 `10_rac/rules/` 下对应章节的 JSON 真身，追加一个 clause。
2. `python render.py write` —— 视图必须能重建。
3. `python BumaoXTGL_Minimal_v01.py check --strict` —— 不许编号重复、父子矛盾、视图漂移。
4. 在 `30_taizhang/` 记一笔：谁、什么时候、加了什么、为什么。

反着做（先改视图再补真身）一定出事：下一轮渲染会覆盖你的改动。

## 目录

```
00_meta/       元信息、版本单点、规则库与功能包
10_rac/        执行器：入口脚本 / render.py / rules / views / examples / docs
20_view/       只读视图区与 Web 控制台
30_taizhang/   变更台账（只追加）
40_renwu/      任务区
90_lishi/      历史归档（只读）
```

## 它不做什么

- 不含具体规矩：别指望装完就有人管你，规矩要你自己写。
- 不做权限控制、不做代码审查。
- 不保证你写的规则本身是好主意，只查自相矛盾、编号重复、视图漂移。

## 许可

Copyright 2026 Bumao

Licensed under the Apache License, Version 2.0. 全文见 [`LICENSE`](LICENSE)。
商标与品牌使用边界见 [`TRADEMARK.md`](TRADEMARK.md)。
贡献流程与 DCO 要求见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。
安全问题请按 [`SECURITY.md`](SECURITY.md) 的私密渠道报告。
