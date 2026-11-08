#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2026 Bumao
#
# Licensed under the Apache License, Version 2.0.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""演示用假引擎：不读真实规则，只回一段可预期的闸门输出。

它存在的唯一目的，是让没有工程的用户也能看到「闸门面板」长什么样。
输出里所有行都带「演示」字样，不会被误当成真实检查结果。
"""
import sys

print("[演示] 闸门检查（合成数据，不对应任何真实工程）")
print("  PASS  D1  元信息可装载")
print("  PASS  D2  三层规则可合并")
print("  PASS  D3  任务留档齐全")
print("[结论] ALL PASS（演示）")
sys.exit(0)
