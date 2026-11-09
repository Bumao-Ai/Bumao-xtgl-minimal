# -*- coding: utf-8 -*-
"""运行层装载器：默认关闭，只有宿主显式开启才加载。

取值：`off` / `shadow` / `enforce`。
未设、空串、未知值一律归 `off` —— 不加载、不建目录、不写账。
"""

import os

MODE_ENV = "BUMO_JIANCHA_MODE"
KNOWN_MODES = ("off", "shadow", "enforce")


def mode():
    """返回归一化后的模式；任何无法识别的输入都按 off 处理。"""
    raw = os.environ.get(MODE_ENV, "").strip().lower()
    return raw if raw in KNOWN_MODES else "off"


def is_enabled():
    return mode() != "off"


def load_if_enabled():
    """开启时返回 supervisor 模块，关闭时返回 None（延迟导入）。"""
    if not is_enabled():
        return None
    from . import supervisor

    return supervisor


__all__ = ["MODE_ENV", "KNOWN_MODES", "mode", "is_enabled", "load_if_enabled"]
