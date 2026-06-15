# Phase 8 handoff prompt

Copy the fenced block below to brief the Phase 8 coding agent.

**Prerequisite:** Phases 1–7 merged. **Environment:** the agent **writes** the scripts/analysis (and can
develop them against the mock); the **human runs them on the real ET1000** and records results (see
`docs/HUMAN_TASKS.md`, Phase 8). This is the only hardware phase.

---

````
You are implementing **Phase 8 — Hardware validation** of `psychopy-eyetracker-eyetribe`. Phases 0–7 are
merged. Your job is to build the validation scripts and analysis so the human can run them on the real
ET1000 and record results; you cannot run the hardware yourself, so develop/verify against the mock.

## Read first (authoritative)
- `docs/DEVELOPMENT_PLAN.md` — §6 and the **Phase 8** section (steps 8a–8d).
- `docs/REFERENCES.md` — the OBSERVED/CORRECTION items; note the current `_captured_frame.json` is
  **uncalibrated** and must be replaced by a calibrated golden frame in this phase.
- `docs/hardware_validation.md` — the checklist + results template to fill.
- Existing `tests/manual/smoke_socket.py` (8a, already works) and the mock for offline development.

## Scope — write the scripts + analysis (human executes on hardware)
- `tests/manual/stream_demo.py` (8b): minimal PsychoPy window with a gaze-contingent dot fed by the
  plugin (live gaze → screen). Must run against the mock for development.
- `tests/manual/calibration_demo.py` (8c): full `runSetupProcedure` on the device; prints/saves the
  accuracy report.
- A validation experiment + analysis (8d): present known on-screen targets, record gaze, and compute
  spatial accuracy (mean offset in °), precision (RMS), and a stimulus-onset-to-gaze timing figure;
  write results into `docs/hardware_validation.md`. Put reusable analysis (offset/RMS math) in a small
  PsychoPy-free, unit-tested helper so the numbers are trustworthy.
- A capture step that saves a **calibrated** golden frame and reconciles it into `frames.py` tests +
  the mock + `REFERENCES.md` if the real data differs from §3 (plan §2 discrepancy procedure).

## Do NOT
- Change pinned decisions or core behaviour except via the §2 discrepancy procedure (with the real
  frame as evidence). Keep the mock-based CI suite green after any reconciliation.

## Acceptance criteria (from the plan)
- 8a–8c run on the Windows machine against the ET1000 (human-run; evidence in `docs/hardware_validation.md`
  and `docs/REPORT.md`: device serial, Server version, Windows build, screenshots/recordings).
- 8d reports accuracy/precision (record actuals; ET-class typical ≈ 0.5–1°) and a characterized timing
  offset.
- After any reconciliation, the full mock-based CI suite still passes.

## Conventions (§6)
- Scripts under `tests/manual/` (PsychoPy/hardware); the analysis helper is PsychoPy-free + unit-tested.
  `ruff`/`black`/`isort`/`mypy` clean; existing tests green.
- Branch `phase-8-hardware-validation`; Conventional Commits; PR `Phase 8: Hardware validation` with the
  checklist + evidence; append a Phase 8 section to `docs/REPORT.md`. On success, tag `v1.0.0`.

## Dev/test commands
```
# develop/verify against the mock on any Python 3.10:
pip install -e .[dev] && pytest -m "not hardware" -q
# the human runs the hardware scripts on the Standalone, e.g.:
& "C:\Program Files\PsychoPy\python.exe" tests\manual\stream_demo.py
```
````
