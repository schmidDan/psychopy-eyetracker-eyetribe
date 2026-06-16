# Phase 2 handoff prompt

Copy the fenced block below to brief the Phase 2 coding agent.

**Prerequisite:** Phase 1 (transport + mock) merged. **Environment:** PsychoPy-free — any Python 3.10.

---

````
You are implementing **Phase 2 — Frame parsing & data model** of `psychopy-eyetracker-eyetribe`, a
native PsychoPy ioHub plugin for The Eye Tribe ET1000. Phases 0–1 are merged. Your work is pure,
PsychoPy-free domain code.

## Read first (authoritative)
- `docs/DEVELOPMENT_PLAN.md` — §3 (Eye Tribe wire format), §6 (conventions/CI), and the **Phase 2**
  section. Implement what it says; it has no open design decisions.
- `docs/REFERENCES.md` — the "Eye Tribe Tracker API" CONFIRMED/CORRECTION/OBSERVED items. Critical:
  - Frame `time` is a **monotonic millisecond counter** (relative; ~uptime) — NOT epoch. Store it as
    `time_ms`. The separate `timestamp` is a wall-clock string.
  - `state` bitmask: GAZE=0x1, EYES=0x2, PRESENCE=0x4, FAIL=0x8, LOST=0x10.
  - OBSERVED: `state == 7` does NOT guarantee a usable gaze point (uncalibrated gaze is `0,0` or wildly
    out of range). So `is_gaze_valid()` here is the **state-level** check (GAZE set AND not FAIL/LOST);
    the calibrated + in-bounds check lives in the EyeTracker (Phase 3) — document this boundary.
- `tests/manual/_captured_frame.json` — a real frame; mirror its exact shape.
- `psychopy_eyetracker_eyetribe/eyetribe/frames.py` — the stub (dataclasses + signatures already
  declared). `psychopy_eyetracker_eyetribe/mock/mock_server.py` — emits the frame variants you test.

## Scope — implement ONLY `frames.py`
- Frozen dataclasses: `Point`, `EyeData(raw, avg, psize, pcenter)`, `Frame(time_ms, fix, state, raw,
  avg, left, right)`.
- `parse_frame(payload: dict) -> Frame` — parse a raw Eye Tribe frame dict; malformed input raises
  `FrameParseError` (callers log + skip; the parser must never crash the reader).
- `TrackingState` decoder turning `state` into named booleans (per the bitmask above).
- Helpers: `Frame.gaze(source: "raw"|"avg") -> Point` and `Frame.is_gaze_valid() -> bool`
  (state-level: GAZE set and neither FAIL nor LOST).

## Do NOT touch (later phases)
- `eyetribe_client.py`/`mock/` (Phase 1 — done; you may read them). Do not change the reader to parse
  frames — it intentionally buffers raw dicts; parsing is invoked by the EyeTracker in Phase 3.
- `transforms.py`/`time_sync.py` (Phase 4), `calibration.py` (Phase 5), `eyetracker.py` (Phase 3),
  `settings.py` (Phase 6). Leave as stubs.
- Do not change pinned decisions; if the protocol genuinely differs, follow the plan §2 discrepancy
  procedure (record in `REFERENCES.md` + `REPORT.md`).

## Acceptance criteria (from the plan)
- `parse_frame` round-trips every variant the mock emits: valid binocular, eyes-only (no gaze), blink,
  `STATE_TRACKING_LOST`, and malformed (→ `FrameParseError`).
- All 32 representable low-5-bit `state` combinations decode deterministically (table-driven test).
- Tests in `tests/unit/test_frames.py` using mock-generated fixtures. (A real **calibrated** golden
  frame is added in Phase 11; the current `_captured_frame.json` is uncalibrated — fine for schema.)

## Conventions (§6)
- PsychoPy-free; full type hints; pass `mypy --strict` (the module is already in `[tool.mypy]`).
- `ruff`/`black`/`isort` clean (line length 100). Extend the CI coverage gate to include `frames.py`
  at ≥ 90%.
- Branch `phase-2-frames`; Conventional Commits; PR titled `Phase 2: Frame parsing & data model` with
  the acceptance criteria as a ticked checklist + evidence; append a Phase 2 section to `docs/REPORT.md`.

## Dev/test commands (no PsychoPy needed)
```
pip install -e .[dev]
ruff check . && black --check . && isort --check-only . && mypy && pytest -m "not hardware" -q
```
````
