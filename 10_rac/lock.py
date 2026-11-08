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

"""lock.py – lightweight file-lock for engine concurrency safety.

Usage:
    lock = Lock("refresh")      # creates .engine.lock in 10_rac/
    lock.acquire("refresh")     # exclusive wait up to N seconds (default 3)
    lock.release()              # always call in finally block
    lock.poll("refresh", timeout)  # non-blocking poll; returns bool

Designed to be importable even when subprocess is unavailable.
"""
import os
import time


class Lock:
    """Per-process file-based mutual exclusion."""
    def __init__(self, rac_dir):
        self._rac_dir = rac_dir
        self._lock_file = os.path.join(rac_dir, ".engine.lock")

    @property
    def owner_pid(self):
        try:
            text = open(self._lock_file, encoding="utf-8").read().strip()
            return int(text.split("::")[0])
        except Exception:
            return None

    def _is_stale(self, pid):
        try:
            text = open(self._lock_file, encoding="utf-8").read().strip()
            parts = text.split("::")
            if len(parts) < 2:
                return True
            ts = float(parts[1])
        except Exception:
            return False
        ttl = int(os.environ.get("ENGINE_LOCK_TTL", "30"))
        return (time.time() - ts) > ttl

    def acquire(self, tag=None, wait_secs=3):
        pid = os.getpid()
        ts = str(time.time())
        token = f"{pid}::{ts}"
        deadline = time.time() + wait_secs
        while time.time() < deadline:
            try:
                fd = os.open(self._lock_file, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o644)
                os.write(fd, token.encode())
                os.close(fd)
                return True
            except FileExistsError:
                existing_pid = self.owner_pid
                if existing_pid and self._is_stale(existing_pid):
                    try:
                        os.remove(self._lock_file)
                        continue
                    except FileNotFoundError:
                        continue
                time.sleep(0.15)
        return False

    def release(self):
        try:
            os.remove(self._lock_file)
        except FileNotFoundError:
            pass

    def poll(self, tag=None, timeout=3):
        start = time.time()
        while time.time() - start < timeout:
            if not os.path.exists(self._lock_file):
                return True
            pid = self.owner_pid
            if pid and self._is_stale(pid):
                try:
                    os.remove(self._lock_file)
                    return True
                except FileNotFoundError:
                    continue
            time.sleep(0.2)
        return False


def acquire(rac_dir, tag=None, wait_secs=3):
    lk = Lock(rac_dir)
    acquired = lk.acquire(tag, wait_secs)
    if acquired:
        lk.release()
    return acquired
