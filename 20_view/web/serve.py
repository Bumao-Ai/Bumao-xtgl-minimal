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

"""Bumao XTGL 控制台入口（薄壳，约 10 行）。

通用能力全部在 xtgl_core.py：路径解析、三层规则、环境自检、首次向导接口。
用法：
    python serve.py                  # 按 web_config.json 启动
    python serve.py --root "<你的项目根目录>"   # 临时指定项目根
    python serve.py --demo           # 内置演示项目（合成数据）
    python serve.py <端口>          # 位置参数写法（等价 --port <端口>）
    python serve.py --port 8802 --no-browser
"""
import sys

from xtgl_core import main


def _normalize_argv(argv):
    """兼容 `serve.py 8801`：裸数字位置参数按 --port 处理。"""
    if len(argv) > 1 and argv[1].isdigit():
        return [argv[0], "--port", argv[1]] + argv[2:]
    return argv


if __name__ == "__main__":
    sys.argv = _normalize_argv(sys.argv)
    raise SystemExit(main())
