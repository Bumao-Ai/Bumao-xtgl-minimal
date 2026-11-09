# -*- coding: utf-8 -*-
"""jiancha —— personal 端「执行中监管」包（v0.2）。

落地口径（2026-11-08 用户令）：
  唯一挂载点是 mcp_server.handle_message 的工具分发处，位于 L4 capability 与
  L3 output_guard 两道闸之后；总开关 BUMO_JIANCHA_MODE，未设/未知值一律 off。
  off 时本包完全不加载（延迟导入），不建目录、不写账、不输出。

包内一律用相对导入（from . import ...）：10_rac 顶层已有同名 ledger.py（另一套账本），
若按 sys.path 插入再绝对导入会把同名模块顶掉，live 现有工具会跟着坏。
"""
