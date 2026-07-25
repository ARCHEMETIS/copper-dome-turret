# Copper Dome Turret

## Agent skills

### Issue tracker

Issues live as GitHub issues on `ARCHEMETIS/copper-dome-turret` (via the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context layout — one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Operating constraints

Hard-won on this machine. Read before running anything.

### Python

- **Always `venv\Scripts\python.exe`. Never bare `python`** — an MSYS2 Python is on PATH and
  its OpenCV is unusable (see the header of `requirements.txt`). Ultralytics CLI is
  `venv\Scripts\yolo.exe`.
- The venv's real interpreter lives **outside the workspace**
  (`C:\Users\Pc\AppData\Local\Programs\Python\Python312`). A workspace-only sandbox blocks it
  and every venv command dies with `No Python at ...`.

### GPU

One 6 GB card (RTX 4050 Laptop, 6141 MiB). **Never run two GPU/YOLO jobs at once** — parallel
runs kill each other silently and the survivor still reports success. If a training or eval
job may be running, pass `device=cpu` for incidental inference and keep the image count small.

### Git

- **Do not commit unless the task explicitly asks for a commit.** Leave the work in the
  working tree and report the diff.
- **Never revert, stash, or overwrite working-tree changes you did not make.** `src/config.py`
  in particular carries live hardware calibration being tuned by hand.
- Never add `dataset/`, `runs/`, `NegativeDataSet/`, `New_Video/`, or `Model/` to git — see
  `.gitignore`. `NegativeDataSet/` contains identifiable faces. `models/best.pt` is the one
  tracked weight file.

### HUD text must be ASCII

`cv2.putText` uses the Hershey font, which has no Thai glyphs — Thai renders as empty boxes.
Thai belongs in docs, code comments, and commit messages only.

`_set_status()` ASCII-replaces the status line (`src/main_click.py:280`,
`tools/manual_aim.py:122`), but that is a last-resort net over one string. Every other
`cv2.putText` call site is unguarded, so **write the literals ASCII at the source** — including
exception messages that can surface on the HUD.

### Code layout

- `src/config.py` is the single source of truth for constants — other files import from it and
  never hardcode numbers.
- `src/main_click.py` is the only entry point for real hardware. `src/main.py` is
  simulator-only and refuses to run without `--sim`.

### Acceptance checks

- **Report real, verified numbers, not "done"** — e.g. "labelled 396 of 396", with the command
  that produced the count. Partial work reported as success has happened here.
- Regression gate for anything touching vision / aiming / ranging:
  `venv\Scripts\python.exe tools\smoke_test.py` must pass 9/9.
- State anything you could not verify as unverified rather than softening it.

Architecture, hardware, and the vision pipeline are documented in `README.md` and `docs/` (Thai).
