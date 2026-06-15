# Phase 6 handoff prompt

Copy the fenced block below to brief the Phase 6 coding agent.

**Prerequisite:** Phases 1–5 merged. **Environment:** needs **PsychoPy 2026.1.3** (wheel install +
Builder check). A human does the Builder dropdown visual check (see `docs/HUMAN_TASKS.md`, Phase 6).

---

````
You are implementing **Phase 6 — Packaging, plugin discovery & Builder backend** of
`psychopy-eyetracker-eyetribe`. Phases 0–5 are merged: a working device with calibration. Now make it a
real, installable, Builder-visible plugin.

## Read first (authoritative)
- `docs/DEVELOPMENT_PLAN.md` — §5.1 (the exact `pyproject.toml` build/discovery sections), §5.2 (YAML
  filenames), §6, and the **Phase 6** section.
- `docs/REFERENCES.md` — CONFIRMED: the Builder settings backend base class is **`EyetrackerBackend`**
  (module `psychopy.experiment.components.settings.eyetracking`); the in-tree **`MouseGazeEyetrackerBackend`**
  is your template; both device YAML filenames are correct. Entry points are already declared in
  `pyproject.toml` and resolve (verified Phase 0).
- Reference plugin: `github.com/psychopy/psychopy-eyetracker-pupil-labs` (`settings.py`, `MANIFEST.in`,
  `release.yml`). The in-tree MouseGaze backend on the machine:
  `C:\Program Files\PsychoPy\Lib\site-packages\psychopy\experiment\components\settings\eyetracking.py`.
- Stub: `psychopy_eyetracker_eyetribe/eyetribe/settings.py` (already subclasses `EyetrackerBackend`).

## Scope — packaging + Builder backend
- Flesh out `settings.py`: `EyeTribeEyetrackerBackend(EyetrackerBackend)` exposing the Builder
  Eyetracker dropdown entry + its parameter fields — **host, port, gaze source, calibration target
  count**. Sampling rate is **not** a field (auto-adopted from the Server). Mirror
  `MouseGazeEyetrackerBackend` for the field/registration mechanics.
- Finalize `pyproject.toml` (per §5.1) and `MANIFEST.in` (ship `*.yaml`). Replace the `<ORG>` placeholder
  in the project URLs with the real GitHub owner.
- `.github/workflows/release.yml`: build a wheel on tag and **attach it to a GitHub Release**
  (`windows-latest`). **No PyPI publication.**

## Do NOT touch
- Core logic (`eyetribe_client`, `frames`, `transforms`, `time_sync`, `calibration`, `eyetracker`) —
  read only. Don't change pinned decisions (plan §2 for discrepancies).

## Acceptance criteria (from the plan)
- Building the wheel and `pip install`-ing it into a **clean** PsychoPy 2026.1.3 environment (no source
  tree present) makes `eyetracker.hw.eyetribe.EyeTracker` importable/usable.
- "Eye Tribe" appears in the Builder Eyetracker component dropdown with its parameter fields (a human
  confirms this visually and records it in `docs/REPORT.md`).
- CI job builds the wheel, installs it into a clean PsychoPy env, imports the namespace, and loads the
  device config.

## Conventions (§6)
- `settings.py` is PsychoPy-coupled (excluded from strict mypy). `ruff`/`black`/`isort` clean.
- Branch `phase-6-packaging`; Conventional Commits; PR `Phase 6: Packaging & Builder backend` with the
  acceptance checklist + evidence; append a Phase 6 section to `docs/REPORT.md`. Update `CHANGELOG.md`.

## Dev/test commands
```
& "C:\Program Files\PsychoPy\python.exe" -m build --wheel
# install the built wheel into a clean env and confirm the namespace + device config load
& "C:\Program Files\PsychoPy\python.exe" -m pytest -m "not hardware" -q
```
````
