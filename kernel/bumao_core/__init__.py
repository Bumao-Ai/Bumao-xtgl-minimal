# -*- coding: utf-8 -*-
# Copyright 2026 Bumao
#
# Licensed under the Apache License, Version 2.0.
# SPDX-License-Identifier: Apache-2.0

"""Bumao Core · 规则执行内核（唯一运行时实现是 engine.py）。

两种加载方式都支持，任选其一：

    pip install -e .                 # 之后 import bumao_core.engine
    sys.path.insert(0, "bumao_core") # 之后 import engine（历史用法）

内核不在导入时读任何宿主文件，也不做任何注入；注入仍由宿主 wrapper 调 configure()。
"""

__version__ = "0.2.5"
