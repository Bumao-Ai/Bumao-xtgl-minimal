# -*- coding: utf-8 -*-
"""GateRegistry 契约测试（P1-5 · C3—C5）。

用独立假引擎隔离，不动真实 engine 的全局账：
  注册即登记、重复 gid 报错、注销清三张账、期望集对账、整跑 strict 首败即抛。
运行：python test_gate_registry.py （退出码 0＝ALL PASS）
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gate_registry import GateRegistry, RegistryMismatch, _REGISTRY


class _FakeEngine:
    """与 engine 同形的三张账：B/Z 闸列表＋已注册 ID 集。"""

    def __init__(self):
        self._b_gates_list = []
        self._z_gates_list = []
        self._registered_gate_ids = set()

    def register(self, gid, fn, label, section="B"):
        (self._b_gates_list if section == "B" else self._z_gates_list).append((gid, fn, label))
        self._registered_gate_ids.add(gid)
        return fn


class GateRegistryTest(unittest.TestCase):
    def setUp(self):
        _REGISTRY.clear()  # 模块级账与本测试的假引擎隔离
        self.eng = _FakeEngine()
        self.reg = GateRegistry(engine_module=self.eng, name="contract")

    def tearDown(self):
        _REGISTRY.clear()

    def test_register_and_validate(self):
        self.reg.register("B", "D1", "恒真", lambda: True)
        self.reg.register("Z", "D2", "恒真", lambda: True)
        self.assertEqual([g["gid"] for g in self.reg.list_gates()], ["D1", "D2"])
        self.assertEqual(self.eng._registered_gate_ids, {"D1", "D2"})
        self.assertTrue(self.reg.validate({"D1", "D2"}))

    def test_duplicate_gid_raises(self):
        self.reg.register("B", "D1", "恒真", lambda: True)
        with self.assertRaises(RegistryMismatch):
            self.reg.register("B", "D1", "重复", lambda: True)

    def test_unregister_clears_three_ledgers(self):
        self.reg.register("B", "D1", "恒真", lambda: True)
        self.assertTrue(self.reg.unregister("D1"))
        self.assertEqual(self.eng._b_gates_list, [])
        self.assertEqual(self.eng._registered_gate_ids, set())
        self.assertEqual(self.reg.list_gates(), [])
        self.assertFalse(self.reg.unregister("D1"))

    def test_validate_missing_gate_raises(self):
        self.reg.register("B", "D1", "恒真", lambda: True)
        with self.assertRaises(RegistryMismatch):
            self.reg.validate({"D1", "D2"})

    def test_validate_requires_explicit_expected(self):
        with self.assertRaises(RegistryMismatch):
            self.reg.validate()

    def test_run_all_collects_and_strict_raises(self):
        self.reg.register("B", "D1", "恒真", lambda: True)
        self.reg.register("B", "D2", "恒假", lambda: False)
        rows = self.reg.run_all(strict=False)
        self.assertEqual([r[0] for r in rows], ["D1", "D2"])
        self.assertEqual([r[1] for r in rows], [True, False])
        with self.assertRaises(RegistryMismatch):
            self.reg.run_all(strict=True)

    def test_run_all_swallows_exception_when_not_strict(self):
        def boom():
            raise RuntimeError("boom")
        self.reg.register("B", "D1", "抛异常", boom)
        rows = self.reg.run_all(strict=False)
        self.assertFalse(rows[0][1])
        self.assertIn("boom", rows[0][2])
        with self.assertRaises(RuntimeError):
            self.reg.run_all(strict=True)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GateRegistryTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("ALL PASS" if result.wasSuccessful() else "FAILED")
    sys.exit(0 if result.wasSuccessful() else 1)
