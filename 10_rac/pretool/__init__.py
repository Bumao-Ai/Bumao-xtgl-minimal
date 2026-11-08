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

"""pretool -- host-side PreToolUse guard adapter.

Attach this to an agent host that exposes a PreToolUse / pre-tool hook. On every
tool call the host pipes {"tool_name","tool_input"} to stdio_adapter.py and gets
an allow/deny decision back. Decision order: L4 whitelist -> L3 payload review
-> audited one-time escape token.
"""
from .core import decide, tier_of_tool
from .escape import issue_token, is_valid, consume
