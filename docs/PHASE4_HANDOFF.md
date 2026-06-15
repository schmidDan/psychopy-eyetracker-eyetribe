# Phase 4 handoff prompt

Copy the fenced block below to brief the Phase 4 coding agent.

**Prerequisite:** Phases 1–3 merged. **Environment:** the two new modules are PsychoPy-free (test on any
Python 3.10); wiring them into `EyeTracker` is verified under PsychoPy.

---

````
You are implementing **Phase 4 — Coordinate transforms & time synchronization** of
`psychopy-eyetracker-eyetribe`. Phases 0–3 are merged: the EyeTracker streams samples with interim
coordinate/clock handling, which you now replace with proper, tested implementations.

## Read first (authoritative)
- `docs/DEVELOPMENT_PLAN.md` — §3, §4, §6, and the **Phase 4** section.
- `docs/REFERENCES.md` — confirmed facts. Critical:
  - Gaze is reported in **screen pixels, origin top-left**; screen resolution comes from the Server
    (`screenresw`/`screenresh`, read at connect).
  - Frame `time` is a **monotonic millisecond counter** (relative; ~uptime) — NOT epoch. Convert ms→s.
    A monotonic counter is preferable for offset estimation (no wall-clock jumps).
- Stubs: `psychopy_eyetracker_eyetribe/eyetribe/transforms.py` and `…/time_sync.py` (signatures already
  declared). The Tobii implementation pattern (normalize → map to display bounds) is the model.
- `eyetracker.py` — the Phase 3 interim hooks you will back with these modules.

## Scope — implement ONLY `transforms.py`, `time_sync.py`, and wire them into `EyeTracker`
- `transforms.py` (PsychoPy-free): pure functions converting Eye Tribe pixels — normalized by the
  Server screen resolution into 0–1 — to/from the ioHub Display coordinate bounds, with the Display
  bounds + unit passed in as **plain numbers** (no PsychoPy import). Provide forward and inverse.
- `time_sync.py` (PsychoPy-free): `ClockSync` — at recording start pair the first frame's `time`
  (monotonic ms → s) with the local PsychoPy time at receipt, correcting for half the measured
  request/reply RTT; `to_psychopy_time(tracker_time_ms)` applies `tracker_s + offset`; re-estimate the
  offset every 5 s and keep the latest.
- Replace the Phase 3 interim code: `EyeTracker._eyeTrackerToDisplayCoords` /
  `_displayToEyeTrackerCoords` become thin wrappers that read the Display bounds from ioHub and delegate
  to `transforms.py`; `trackerTime`/`trackerSec` delegate to `ClockSync`.
- Document both in `docs/coordinate_systems.md` (a diagram + worked example for space; the latency
  budget for time = sampling latency (1/rate ≈ 33 ms @ 30 Hz) + transport).

## Do NOT touch
- `eyetribe_client.py`, `mock/`, `frames.py` (read only). `calibration.py`/`runSetupProcedure`
  (Phase 5), `settings.py` (Phase 6). Don't change pinned decisions (plan §2 for discrepancies).

## Acceptance criteria (from the plan)
- Known device pixel coords map to expected display-unit coords for `pix`, `norm`, `height`, and (with
  a monitor calibration) `deg`, asserted numerically; forward∘inverse round-trips to within **1e-6** in
  normalized space.
- Synthetic frames with known `time` map to expected PsychoPy times within **1 ms** in unit tests
  (deterministic math).
- `tests/unit/test_transforms.py` (parametrized over units × resolutions, incl. inverse round-trip) and
  `tests/unit/test_time_sync.py` (offset estimation, drift re-estimation, RTT correction).

## Conventions (§6)
- PsychoPy-free modules; full type hints; pass `mypy --strict` (already in `[tool.mypy]`).
  `ruff`/`black`/`isort` clean. Extend the coverage gate to include `transforms.py` + `time_sync.py`
  at ≥ 90%.
- Branch `phase-4-transforms-timesync`; Conventional Commits; PR `Phase 4: Coordinate transforms & time
  synchronization` with acceptance checklist + evidence; append a Phase 4 section to `docs/REPORT.md`.

## Dev/test commands (no PsychoPy needed for the unit tests)
```
pip install -e .[dev]
ruff check . && black --check . && isort --check-only . && mypy && pytest -m "not hardware" -q
```
````
