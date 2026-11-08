# Bumao XTGL Console · English Quickstart

A zero-dependency local web console for an XTGL workspace: read-only project info, rule layers,
task records, gate output, modules and long-term goals.

- **No build step**, no npm, no third-party packages.
- Binds to `127.0.0.1` only.
- Python 3.8+.

## Run

```bash
cd 20_view/web
python serve.py
```

Open the printed URL (Chrome is preferred automatically). Other options:

```bash
python serve.py --root "/path/to/another-project"   # point at another project, no config change
python serve.py --demo                   # synthetic demo data
python serve.py --port 8802 --no-browser
```

Windows: double-click `qidong_kongzhitai.bat`.

## First run

Visit `/setup` (or click **Open setup wizard**). Four steps: choose folder → check environment →
set rule layers → create the first task. A minimal workspace can be generated from an empty folder.

Rule layers merge as `core > default > user`; a user clause with the same id as a core clause is
rejected and reported. See `TUTORIAL.en.md` for the detailed walkthrough (中文版：`TUTORIAL.md`).

## Language

The UI switches between Chinese and English:

- click **EN / 中文** in the header, or
- append `?lang=en` to the URL.

Data files (rules, goals, metadata) keep their original text; only the UI shell is translated.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `/api/overview` | project meta, rule layers, conflicts, gate output (`fast=1` skips the gate) |
| `/api/env` | environment self-check |
| `/api/clauses?file=&layer=` | clauses of one rule file |
| `/api/doc?name=` | whitelisted docs (README, TUTORIAL, …) |
| `/api/tasks` | task folders and record status |
| `/api/modules` | module manifest and compatibility |
| `/api/goals` / `/api/goals/export` | long-term goals (JSON / Markdown download) |
| `/setup` | first-run wizard |

Write endpoints (`/api/setup/*`) require the `X-XTGL-Setup: 1` header and a local client.

## Self-check

```bash
python -m unittest discover -s tests -v   # 25 tests
python module_check.py                    # module manifest
python kernelsync.py --check              # core files vs manifest
```

## Docs

- `README.md` (中文运行说明)
- `TUTORIAL.md` / `TUTORIAL.en.md`
- `ARCHITECTURE.md` — layering, module contract, data schema, compatibility
- `ROADMAP.md` — stages and acceptance criteria
