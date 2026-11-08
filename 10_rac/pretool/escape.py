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

"""escape.py -- audited one-time escape hatch.

A hard gate with no escape hatch will itself be bypassed on day one ("just turn
the hook off"). Instead we keep one audited path: after the user explicitly
authorizes a single call, issue a one-time token; the adapter honors it for that
one call, consumes it, and appends an audit line. Empty reasons are refused.

Since 0.15 a token can be bound at issue time to the exact tool + payload it was
authorized for (`tool_name`/`payload`). A bound token is refused for any other
call, so authorizing one cleanup cannot be spent on a different command inside
the TTL. Unbound tokens keep the old behaviour for callers that do not bind.
"""
import hashlib
import io
import json
import os
import time
import uuid

import rules_db as dbm

VAULT = os.path.join(dbm.LOGS_DIR, "escape_tokens.json")
AUDIT = os.path.join(dbm.LOGS_DIR, "escape_audit.txt")


def _load():
    if not os.path.exists(VAULT):
        return {"tokens": {}}
    try:
        with io.open(VAULT, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"tokens": {}}


def _save(d):
    os.makedirs(os.path.dirname(VAULT), exist_ok=True)
    with io.open(VAULT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def _bind_sha(tool_name, payload):
    h = hashlib.sha256()
    h.update((str(tool_name or "") + "\x00" + str(payload or "")).encode("utf-8"))
    return h.hexdigest()


def issue_token(reason, ttl_seconds=600, tool_name=None, payload=None):
    """Issue a one-time token. `reason` is mandatory (auditable justification).

    Pass `tool_name` and/or `payload` to bind the token to that exact call.
    """
    if not reason or not str(reason).strip():
        raise ValueError("refusing to issue escape token: a reason is required")
    tok = "ESC-" + uuid.uuid4().hex[:12]
    d = _load()
    rec = {
        "issued": time.strftime("%Y-%m-%d %H:%M:%S"),
        "expire": time.time() + ttl_seconds,
        "reason": str(reason).strip()[:200],
        "used": False,
    }
    if tool_name is not None or payload is not None:
        rec["bind_tool"] = str(tool_name or "")
        rec["bind_sha"] = _bind_sha(tool_name, payload)
    d["tokens"][tok] = rec
    _save(d)
    return tok


def is_valid(tok, tool_name=None, payload=None):
    if not tok:
        return False
    rec = _load()["tokens"].get(tok)
    if not rec or rec.get("used"):
        return False
    if time.time() > rec.get("expire", 0):
        return False
    if rec.get("bind_sha") and rec["bind_sha"] != _bind_sha(tool_name, payload):
        return False
    return True


def consume(tok, tool_name, payload):
    d = _load()
    rec = d["tokens"].get(tok, {})
    rec["used"] = True
    rec["used_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    rec["used_for_tool"] = tool_name
    d["tokens"][tok] = rec
    _save(d)
    line = "%s | ESCAPE-USE | tool=%s | reason=%s" % (
        time.strftime("%Y-%m-%d %H:%M:%S"), tool_name, rec.get("reason", "")[:120])
    os.makedirs(os.path.dirname(AUDIT), exist_ok=True)
    with io.open(AUDIT, "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")
    return rec
