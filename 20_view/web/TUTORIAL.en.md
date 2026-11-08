# Bumao XTGL Console · Beginner Tutorial (Detailed)

> This assumes you have never installed it. Follow the steps in order; each one has a way to verify.
> No internet required, no `pip install`, no Node.js.

---

## 0. What it is

The console is a **local web page**: a small Python service runs on your machine, and your
browser opens `http://127.0.0.1:<port>/` to show project status.

It is not a cloud service and works offline. It does not modify your project, except when the
first-run wizard writes a config or creates a task.

---

## 1. Prerequisites (5 minutes)

### 1.1 Python

Open PowerShell and run:

```powershell
python --version
```

You need Python 3.8 or newer. If the command is not found:

1. Install Python 3.8+ from python.org;
2. Tick **Add Python to PATH** during installation;
3. Reopen the terminal and try again.

### 1.2 Locate the console folder

Each repository has one, typically:

```text
<repo>\20_view\web\
  ├─ serve.py          entry point
  ├─ index.html        main UI
  ├─ setup.html        first-run wizard
  ├─ xtgl_core.py      core
  ├─ web_config.json   config (the only file allowed to differ)
  └─ README.md         run notes
```

---

## 2. First start (3 minutes)

```powershell
cd <repo>\20_view\web
python serve.py
```

You will see:

```text
========================================================
 Bumao XTGL · Console
 URL  http://127.0.0.1:8804/
 Root /path/to/BumaoXTGL_Minimal
 Core 0.10 · Python 3.12.14
 Browser Chrome
 Ctrl+C to stop
========================================================
```

**Verify**: the browser opens automatically (Chrome preferred). If not, open the printed URL.

> On Windows you can also double-click `qidong_kongzhitai.bat`.
> If the port is busy it scans up to 40 ports; always trust the URL printed in the terminal.

---

## 3. First-run wizard

If the folder has no project, the page shows "First run". Click **Open setup wizard** or visit
`http://127.0.0.1:8804/setup`.

### Step 1: choose the project folder

- Existing project: point to its root (it should contain `00_meta/meta.json`);
- New project: enter an **empty folder**, tick "New workspace", click "Create skeleton".

The skeleton contains:

```text
00_meta/meta.json      metadata (single source of version)
rules/r01_default.json two sample rules
10_rac/                engine folder (optional)
30_taizhang/           ledgers
40_renwu/              tasks
```

Only missing files are created; nothing is overwritten.

### Step 2: check the environment

Click **Check**:

| Check | Pass condition |
|---|---|
| Python | 3.8+ |
| Project folder | exists and readable |
| 00_meta/meta.json | parses |
| Engine | command found (warning if absent) |
| Rule layers | default layer exists |
| Writable | needed to create tasks |

Red items must be fixed; yellow warnings are fine.

### Step 3: rule layers

Three folders, merged by priority:

```text
core (not overridable) > default > user
```

- default is required (e.g. `rules` or `zhunze`);
- core and user may be empty;
- a user clause with the same id as a core clause is **rejected** and reported at the top of the page.

### Step 4: first task (optional)

Enter a task name and click **Create task**. A `benci_gongcheng.txt` skeleton is created under
`40_renwu/<task>/`.

Finally click **Save and open console**.

**Verify**: the project root appears at the top, all cards have data, no red errors.

---

## 4. Reading the main page

| Card | What to look at |
|---|---|
| Project info | version/name/nature from `00_meta/meta.json` |
| Gate check | click "Run gate check" to run the real engine; green = ALL PASS |
| Rules | merged core/default/user; click a row to expand |
| Modules | module list and version compatibility |
| Long-term goals | A-class asset goals, progress, linked projects; exportable |
| Tasks | whether each task has a record |

The first paint uses `?fast=1` and does **not** run the gate (milliseconds). Run it manually —
a real engine check can take 1–40 seconds.

---

## 5. Writing rules

A rule file looks like this:

```json
{
  "ch": 1,
  "file": "r01_default.json",
  "chapter_title": "1. Default rules",
  "clauses": [
    {"id": "1.1", "root": "1.1", "title": "1.1 Back up before editing",
     "body": ["Keep a timestamped .bak next to the file before overwriting."]}
  ]
}
```

Where rules live:

- default: `rules.default.dir` in `web_config.json`;
- core: `rules.core.dir` (users cannot override);
- user: `rules.user.dir` (may override default).

Refresh the page after editing; no restart needed.

---

## 6. Tasks and records

Every task folder needs at least one record file. Any of these names count:

```text
benci_gongcheng.txt / renwu_liudang.txt / xiangmu_jilu.txt (or any name containing "liudang")
```

Tasks without a record are flagged red, and the main system's B42 gate fails.

A record has three parts: summary header (date/executor/task/status/goal), body, index tail.
Write the executor as "model + client", never the user's own name.

---

## 7. Long-term goals and export

There is exactly one goals file, stored as an A-class asset:

```text
你的 goals 文件（web_config 的 goals 或环境变量 XTGL_GOALS）
```

The console reads it and shows goal, stage, status, progress, linked projects and missing linked
files. **Export Markdown** produces a manifest with the source path, projects and per-file
existence. It exports the index only; project files stay where they are.

The path is configured by `goals` in `web_config.json`; leave it empty to hide the card.

---

## 8. Demo mode

```powershell
python serve.py --demo
```

Uses built-in synthetic data (three layers, one task, a fake engine) and marks the page as demo.
It deliberately includes a user clause that collides with a core clause, to demonstrate rejection.

---

## 9. FAQ

**Q1: The .bat window flashes and closes.**
A: Usually Python not on PATH, port busy, or the default browser failing. Run `python serve.py`
in a terminal to see the real error.

**Q2: The page says "read failed".**
A: You probably opened `index.html` directly. It must be served by `serve.py` so `/api/*` works.

**Q3: Browser is not Chrome / won't open.**
A: The server prefers Chrome (`chrome --new-window`), then falls back to the default browser.
You can always paste the printed URL into any browser.

**Q4: The gate spinner never stops.**
A: The gate really executes; large projects can take tens of seconds. The first paint skips it.

**Q5: Port conflict.**
A: It scans up to 40 ports. Use the URL printed in the terminal.

**Q6: Can I move it to another machine?**
A: Yes. Copy the whole repository. With `project_root` empty it resolves to the parent project
root, so moving the tree keeps working.

---

## 10. Security boundaries

- binds to `127.0.0.1` only; no auth — never expose it to LAN/WAN;
- write endpoints accept only local pages (`X-XTGL-Setup: 1`);
- except the four wizard write endpoints, the console never modifies project files;
- the doc endpoint only reads whitelisted files.

---

## 11. Stop / uninstall

- Stop: `Ctrl+C` in the terminal;
- Uninstall: delete the repository folder. No registry, no service, no leftover process.

---

## 11.5 Turning features on, configuring rules, rule packs vs feature packs

### How to turn a feature on

Capabilities are declared in two places; both must agree:

- `capabilities` in `web_config.json`: names this copy is allowed to enable (new capabilities start disabled; add the name to `capabilities_off` to keep them off);
- `status` in `modules.json`: `active` / `planned` / `disabled`. A capability with no module declaration never shows up in the UI.

To enable: add the name to `capabilities`, make sure `modules.json` has a module with the same `id`, restart the server. To disable: move the name back to `capabilities_off`.

### How to configure rules

Rules live in layers: `core` (kernel, read-only) → `default` → `user`. A user clause with the same id as a core clause is rejected and reported at the top of the page; edit only the `user` layer, never `core`. The Minimal copy ships `rules/` with zero active clauses and `examples/` with 5 chapters of 28 sample clauses; mount a sample into the `user` layer to see it take effect.

### Rule packs vs feature packs

- **Rule pack**: the clauses themselves (JSON files, mountable, replaceable, exportable), no code;
- **Feature pack**: modules and endpoints (`modules.json` declarations plus page/server code), no clauses.

They stay separate: swapping a rule pack changes no code; swapping a feature pack changes no clauses.

### Back to the guide

The **📖 Guide** button at the top right of the console returns to this page at any time; **← Back to console** at the top left of this page returns to the main view.

## 12. Next steps

- Architecture and module contract: `ARCHITECTURE.md`
- Roadmap: `ROADMAP.md`
- Tests: `python -m unittest discover -s tests -v`
- Core consistency: `python kernelsync.py --check`

## Mounting a rule from the rules library (six steps)

The library lives in the host layer at `00_meta/rules_library/` (end-root folders are bound by the
B5b naming gate, so the library is not placed at the root), separate from the directory holding live
rules. All five preset packs ship with an empty rule array and `enabled: false`.

1. Copy `00_meta/rules_library/examples/example-template.json` into
   `00_meta/rules_library/packs/` and rename it;
2. Fill your own rules per `00_meta/rules_library/schema.json` - only your own action and scope;
   leave every threshold, day count and quota empty for the user to set;
3. Set that pack's `enabled` to `true` (otherwise nothing ever takes effect);
4. Run `python 20_view/web/module_check.py` - a malformed pack must FAIL;
5. Run the gate `check --strict` - it must stay green;
6. Check the rules-library row in the capability panel - disabled packs never reach the snapshot.

## Mounting a rule from the rules library (six steps)

The library lives in the host layer at `00_meta/rules_library/` (end-root folders are bound by the
B5b naming gate, so the library is not placed at the root), separate from the directory holding live
rules. All five preset packs ship with an empty rule array and `enabled: false`.

1. Copy `00_meta/rules_library/examples/example-template.json` into
   `00_meta/rules_library/packs/` and rename it;
2. Fill your own rules per `00_meta/rules_library/schema.json` - only your own action and scope;
   leave every threshold, day count and quota empty for the user to set;
3. Set that pack's `enabled` to `true` (otherwise nothing ever takes effect);
4. Run `python 20_view/web/module_check.py` - a malformed pack must FAIL;
5. Run the gate `check --strict` - it must stay green;
6. Check the rules-library row in the capability panel - disabled packs never reach the snapshot.


