# -*- coding: utf-8 -*-
"""参考宿主（P1-5 · C5）：外部 Agent 接入内核的最小标准写法。

要点：不碰 engine 内部结构，只用 GateRegistry 的 register/validate/run_all；
期望集由宿主自己声明（内核不内置任何闸名清单）。端无关。
运行：python host_reference.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engine
from gate_registry import GateRegistry


def demo():
    reg = GateRegistry(engine_module=engine, name="host_reference")
    reg.register("B", "D1", "示例闸：恒真", lambda: True)
    reg.register("B", "D2", "示例闸：读数", lambda: len(reg.list_gates()) >= 2)
    reg.validate({"D1", "D2"})
    rows = reg.run_all(strict=False)
    print("gates=%d ok=%d" % (len(rows), sum(1 for _, ok, _ in rows if ok)))
    reg.unregister("D2")
    print("after unregister: %s" % [g["gid"] for g in reg.list_gates()])


if __name__ == "__main__":
    demo()
