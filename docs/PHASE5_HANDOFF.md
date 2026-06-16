# Phase 5 handoff prompt

Copy the fenced block below to brief the Phase 5 coding agent.

**Prerequisite:** Phases 1–4 merged. **Environment:** `calibration.py` is PsychoPy-free; the
`runSetupProcedure` window/loop needs **PsychoPy 2026.1.3**. A human does the visual GUI check (see
`docs/HUMAN_TASKS.md`, Phase 5).

---

````
You are implementing **Phase 5 — Calibration via PsychoPy (`runSetupProcedure`)** of
`psychopy-eyetracker-eyetribe`. Phases 0–4 are merged: the device streams calibrated-aware samples with
proper transforms and time-sync.

## Read first (authoritative)
- `docs/DEVELOPMENT_PLAN.md` — §3 (calibration messages + `calibresult`), §6, and the **Phase 5**
  section.
- `docs/REFERENCES.md` — calibration sequence and `calibresult` shape; the validity note (gaze is only
  meaningful AFTER a successful calibration).
- The mock's scriptable calibration responder in `psychopy_eyetracker_eyetribe/mock/mock_server.py`
  (returns a configurable `calibresult`). The in-tree MouseGaze `runSetupProcedure` and the in-tree
  `…/eyetracker/hw/mouse/calibration.py` as references for the PsychoPy-side pattern.
- Stubs: `psychopy_eyetracker_eyetribe/eyetribe/calibration.py` and `EyeTracker.runSetupProcedure`.

## Scope — implement calibration
- `calibration.py` (PsychoPy-free): the device-protocol **sequencing** + `calibresult` parsing
  (`parse_calibresult`), point layouts for target counts 5/9/12 (default 9), and the timing constants
  (settle 750 ms, sample 1000 ms). No PsychoPy imports here — it must be unit-testable without a window.
- `EyeTracker.runSetupProcedure(calibration_args)`: the thin PsychoPy drawing/loop wrapper — present
  animated targets in the window for the configured `target_count` in a standard grid; for each point
  run `calibration start` → settle → `pointstart` → sample window → `pointend`; handle keyboard abort
  (`calibration abort`) and `clear`; parse `calibresult`; render an accuracy summary (overall `deg` +
  per-point `ad`); offer accept/redo; restore window state on exit.

## Do NOT touch
- `eyetribe_client.py`, `mock/` (extend only the calibration responder if needed), `frames.py`,
  `transforms.py`, `time_sync.py` (read only). `settings.py` (Phase 6). Don't change pinned decisions
  (plan §2 for discrepancies).

## Acceptance criteria (from the plan)
- Against the mock's scriptable responder, full 5-, 9-, and 12-point runs complete, parse `calibresult`,
  and report per-point + overall accuracy; abort and redo paths work and leave the device in a clean
  recordable state.
- Calibration is keyboard-interruptible; window state is restored after accept, redo, and abort.
- Tests: `tests/unit` for `calibration.py` (message-sequence + result parsing vs the mock responder, no
  window); `tests/integration` driving `runSetupProcedure` with a headless/offscreen window where
  supported, asserting the exact message sequence sent to the mock.
- (Visual correctness on real hardware is confirmed by a human in Phase 11b — out of scope here.)

## Conventions (§6)
- `calibration.py` is PsychoPy-free (mypy --strict + ≥90% coverage; extend the coverage gate to include
  it). `runSetupProcedure` lives in `eyetracker.py` (PsychoPy-coupled, excluded from strict mypy).
  `ruff`/`black`/`isort` clean.
- Branch `phase-5-calibration`; Conventional Commits; PR `Phase 5: Calibration (runSetupProcedure)` with
  acceptance checklist + evidence; append a Phase 5 section to `docs/REPORT.md`.

## Dev/test commands
```
& "C:\Program Files\PsychoPy\python.exe" -m pip install -e .[dev]
& "C:\Program Files\PsychoPy\python.exe" -m pytest -m "not hardware" -q
# calibration.py unit tests also run on any plain Python 3.10:  pytest tests/unit -q
```
````
