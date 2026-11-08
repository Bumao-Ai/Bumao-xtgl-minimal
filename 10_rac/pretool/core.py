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

"""core.py -- PreToolUse decision core: L4 whitelist -> L3 review -> escape hatch."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

import output_guard as og  # noqa: E402

# Generic host tool names mapped to tiers. read tools never go through L3, to
# avoid false-firing on normal search/read.
READ_TOOLS = {
    "Read", "Glob", "Grep", "LS", "list_dir", "search_files",
    "WebSearch", "WebFetch", "NotebookRead", "get_file_content",
    "list_files", "read_file",
}
WRITE_TOOLS = {
    "Write", "Edit", "MultiEdit", "NotebookEdit",
    "write_file", "edit_file", "create_file",
}
EXEC_TOOLS = {
    "Bash", "PowerShell", "Shell", "execute", "run_command",
    "run_terminal", "terminal", "exec_command", "bash", "powershell",
}


def tier_of_tool(tool_name):
    t = (tool_name or "").strip()
    if t in READ_TOOLS:
        return "read"
    if t in WRITE_TOOLS:
        return "write"
    if t in EXEC_TOOLS:
        return "exec"
    return None  # unregistered -> L4 default deny


def _payload_text(tool_name, tool_input):
    if not isinstance(tool_input, dict):
        return str(tool_input or "")
    parts = []
    if tool_name in EXEC_TOOLS:
        for k in ("command", "cmd", "script", "shell", "command_line", "input"):
            if k in tool_input:
                parts.append(str(tool_input[k]))
    if tool_name in WRITE_TOOLS:
        for k in ("content", "text", "new_string", "code", "block"):
            if k in tool_input:
                parts.append(str(tool_input[k]))
        for k in ("file_path", "path", "notebook_path"):
            if k in tool_input:
                parts.append("PATH " + str(tool_input[k]))
    return "\n".join(parts)


def decide(tool_name, tool_input=None, authorized=(), escape_token=None,
           source="pretool"):
    """Return {'allow','decision','tier','reason','hits'}."""
    tool_input = tool_input or {}
    tier = tier_of_tool(tool_name)

    if tier is None:
        return {"allow": False, "decision": "deny", "tier": "deny",
                "reason": "L4 default deny: tool %r not in read/write/exec whitelist" % tool_name,
                "hits": []}

    if tier == "read":
        return {"allow": True, "decision": "allow", "tier": "read",
                "reason": "read-only tool allowed (does not pass L3)", "hits": []}

    if escape_token:
        from . import escape
        if escape.is_valid(escape_token):
            escape.consume(escape_token, tool_name, _payload_text(tool_name, tool_input))
            return {"allow": True, "decision": "allow", "tier": tier,
                    "reason": "audited one-time escape token honored and consumed", "hits": []}

    payload = _payload_text(tool_name, tool_input)
    try:
        og.enforce(payload, authorized=tuple(authorized),
                   source="%s:%s" % (source, tool_name))
    except og.GuardBlocked as gb:
        return {"allow": False, "decision": "deny", "tier": tier,
                "reason": "L3 blocked: %s" % gb.result.get("advice", ""),
                "hits": gb.result.get("hits", [])}
    return {"allow": True, "decision": "allow", "tier": tier,
            "reason": "%s payload passed L3" % tier, "hits": []}
