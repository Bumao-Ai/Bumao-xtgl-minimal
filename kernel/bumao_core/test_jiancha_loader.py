# -*- coding: utf-8 -*-
"""运行层装载器自测：六态归一化 + 两态加载返回。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bumao_core.jiancha import loader


def case(label, value, want_mode, want_enabled):
    if value is None:
        os.environ.pop(loader.MODE_ENV, None)
    else:
        os.environ[loader.MODE_ENV] = value
    got_mode = loader.mode()
    got_enabled = loader.is_enabled()
    ok = got_mode == want_mode and got_enabled == want_enabled
    print(("PASS " if ok else "FAIL ") + label + " mode=%s enabled=%s" % (got_mode, got_enabled))
    return ok


def main():
    results = [
        case("未设 → off", None, "off", False),
        case("空串 → off", "", "off", False),
        case("未知值 → off", "banana", "off", False),
        case("off → off", "off", "off", False),
        case("shadow → on", "shadow", "shadow", True),
        case("enforce → on", "enforce", "enforce", True),
    ]

    os.environ.pop(loader.MODE_ENV, None)
    loaded_off = loader.load_if_enabled()
    ok_off = loaded_off is None
    print(("PASS " if ok_off else "FAIL ") + "关闭时不加载")

    os.environ[loader.MODE_ENV] = "enforce"
    loaded_on = loader.load_if_enabled()
    ok_on = loaded_on is not None and loaded_on.__name__ == "bumao_core.jiancha.supervisor"
    print(("PASS " if ok_on else "FAIL ") + "开启时返回 supervisor 模块")

    os.environ.pop(loader.MODE_ENV, None)
    results += [ok_off, ok_on]
    print("ALL PASS" if all(results) else "HAS FAIL")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
