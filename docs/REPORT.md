# REPORT — progress log

Append-only; one section per phase (see DEVELOPMENT_PLAN.md section 6).

## Phase 0 — Repository scaffold & fact verification  (status: DONE — pending PR review/merge)
- Date: 2026-06-15
- Delivered:
  - Repo structure per section 5: packaging (`pyproject.toml` with both entry-point groups),
    `MANIFEST.in`, `LICENSE` (GPL-3.0), `README`, `CHANGELOG`, `CONTRIBUTING`, `.gitignore`,
    `.pre-commit-config.yaml`, CI + release workflows (Windows).
  - PsychoPy-free core stubs (`eyetribe_client`, `frames`, `transforms`, `time_sync`, `calibration`)
    that import without PsychoPy; lazy `EyeTracker` export (PEP 562) in `eyetribe/__init__.py`;
    `EyeTracker` and `EyeTribeEyetrackerBackend` stubs so both entry points resolve; valid device YAML;
    `MockEyeTribeServer` stub.
  - Tests: core import tests, entry-point registration + YAML-parse tests (PsychoPy-free), and
    PsychoPy-gated discovery/loader test; pre-Phase-0 hardware smoke script (`tests/manual/smoke_socket.py`).
  - `docs/REFERENCES.md` skeleton with CONFIRMED vs TO-CONFIRM items.
- Acceptance criteria status:
  - PASS (sandbox): ruff/black/isort clean; PsychoPy-free tests green; entry points + YAML verified.
  - PENDING (Windows + PsychoPy 2026.1.3): `pip install -e .[dev]`; full CI green; namespace
    `psychopy.iohub.devices.eyetracker.hw.eyetribe` resolves; ioHub loader test; complete REFERENCES.md.
- TO-CONFIRM handed forward: items marked [TO CONFIRM ON MACHINE] in `docs/REFERENCES.md`.
- **Hardware pre-flight gate (8a smoke), 2026-06-15: PASS** — ET1000 + Eye Tribe Server 0.9.77 stream
  at 30 Hz (1920×1080), `trackerstate 0`; `_captured_frame.json` captured. Two wire-format corrections
  recorded in `docs/REFERENCES.md` and reconciled into the plan + `time_sync.py`: (1) frame `time` is a
  monotonic ms counter, not epoch ms (separate `timestamp` is wall-clock); (2) pushed frames carry
  `request: "get"` — detect frames by `values.frame` presence, not the request string.
- **Repo:** initialised and pushed (private, single-contributor). `main` branch protection is a
  deferred TODO (see `docs/HUMAN_TASKS.md`).
- **Phase 0 on-machine acceptance (2026-06-15):** `pip install -e .[dev]` into the Standalone OK;
  ruff/black/isort clean; pytest **10 passed / 2 skipped** — `test_eyetracker_class_loads_under_psychopy`
  passes, confirming the `EyeTrackerDevice` base path. **Discovery mechanism pinned** (via
  `check_discovery.py`): `scanPlugins()` sees the plugin; PsychoPy creates no importable `hw.eyetribe`
  module — ioHub resolves the device from the entry point at `launchHubServer` time
  (`eyetracker.hw.eyetribe.EyeTracker`); verified end-to-end in Phase 1/3.
- **REFERENCES filled from installed source (2026-06-15):** EyeTrackerDevice method surface (base
  provides event buffering → Phase 3 implements only device-specific methods); `BinocularEyeSampleEvent`
  field names + the Eye Tribe→event mapping; settings backend base class **`EyetrackerBackend`** —
  **`settings.py` corrected** from the wrong `EyetrackingBackend`. `default_eyetracker.yaml` filename
  confirmed in-tree. **Remaining for Phase 0:** one quick check that the in-tree MouseGaze device uses
  `supported_config_settings.yaml` (rename ours if not), then PR review/merge.
- **Fact-finding closed (2026-06-15):** MouseGaze device confirms both YAML filenames
  (`default_eyetracker.yaml` + `supported_config_settings.yaml`) — no rename; backend MRO confirms it
  subclasses `EyetrackerBackend`. **All `[TO CONFIRM]` items resolved.** Only the Phase 0 PR
  review/merge (human) remains before Phase 1.

## Phase 1 — Transport layer + Mock server  (status: IN PROGRESS)

- Date: 2026-06-15 / Agent: Claude Sonnet 4.6 / Branch: `phase-1-transport` / PR: pending
- Delivered:
  - `psychopy_eyetracker_eyetribe/mock/mock_server.py` — `MockEyeTribeServer`: binds a free port;
    speaks `tracker set version`, `tracker get <keys>`, `tracker set push`; pushes synthesized frames
    at a configurable rate (default 30 Hz) using `{"category":"tracker","request":"get","values":{"frame":{…}}}`;
    enforces heartbeats (drops client if no heartbeat within `heartbeat_interval_ms`); scriptable
    calibration responder; context-manager + `start()`/`stop()`. Gaze models: `fixed_point_model`,
    `linear_sweep_model`; injectable blink/`STATE_TRACKING_LOST` segments via `_Segment`.
  - `psychopy_eyetracker_eyetribe/eyetribe/eyetribe_client.py` — `EyeTribeClient`: `connect()` steps
    1–5 per §3; `close()` teardown; reconnect (3 × 0.5 s backoff → `DISCONNECTED`); request/reply
    with 2 s timeout; `ReaderThread` detecting frames by `values.frame` presence → `FrameBuffer`
    (capacity 1024, drop oldest); `HeartbeatThread` at `heartbeat_interval_ms/2`; structured logging.
  - `tests/conftest.py` — `mock_server` fixture with thread-leak assertion.
  - `tests/unit/test_client.py` — framing, routing, timeout, FrameBuffer overflow, lifecycle.
  - `tests/integration/test_client_against_mock.py` — lifecycle, rate ±10%, heartbeat endurance,
    heartbeat-stop → disconnect → reconnect, buffer overflow.
  - `.github/workflows/ci.yml` — mypy gate (strict, PsychoPy-free core) + coverage gate (≥90%).
- Acceptance criteria:
  - PENDING — rate ±10%: test_frame_rate_within_10_percent parametrized over [10, 30] Hz
  - PENDING — heartbeat ≥30 s: test_heartbeat_keeps_link_alive_30s (sped up via short interval)
  - PENDING — stop heartbeat → disconnect → reconnect: test_stopping_heartbeats_causes_disconnect_and_reconnect
  - PENDING — no leaked threads/sockets: asserted in unit + conftest teardown
  - PENDING — zero PsychoPy imports: verified by module-level import test + mypy
  - PENDING — ruff/black/isort/mypy clean; pytest green; coverage ≥90%
- Deviations from plan: none
- Open issues handed to Phase 2: implement `frames.py` (parse raw frame dicts from `FrameBuffer`)

## Phase 2 — Frame parsing & data model  (status: DONE)

- Date: 2026-06-15 / Agent: Claude Sonnet 4.6 / Branch: `phase-2-frames` / PR: pending
- Delivered:
  - `psychopy_eyetracker_eyetribe/eyetribe/frames.py` — implemented in full:
    - Frozen dataclasses: `Point`, `EyeData(raw, avg, psize, pcenter)`, `Frame(time_ms, fix, state,
      raw, avg, left, right)`.
    - `TrackingState` frozen dataclass with `from_int(state: int)` classmethod decoding all 5 bitmask
      flags into named booleans (`gaze`, `eyes`, `presence`, `fail`, `lost`).
    - `parse_frame(payload: dict) -> Frame` — parses `lefteye`/`righteye` keys; stores `time` as
      `time_ms`; `timestamp` string is intentionally discarded (not in Frame schema); raises
      `FrameParseError` on any malformed input (missing keys, wrong types, non-dict).
    - `Frame.gaze(source: "raw"|"avg") -> Point` — returns `self.raw` or `self.avg`.
    - `Frame.is_gaze_valid() -> bool` — state-level check: GAZE set AND neither FAIL nor LOST.
      Boundary documented in docstring: uncalibrated trackers may set GAZE but report 0,0;
      the calibrated + in-bounds guard lives in the EyeTracker (Phase 3).
    - Private helpers `_parse_point` / `_parse_eye` with context strings in error messages.
  - `tests/unit/test_frames.py` — 59 tests covering all acceptance criteria:
    - `TestParseFrameVariants` — round-trips valid binocular, eyes-only, blink (FAIL), LOST, and
      5 malformed-input cases (missing key, bad point type, nested bad value, non-dict, missing eye
      key, eye non-dict).
    - `TestCapturedFrame` — parses `tests/manual/_captured_frame.json` and asserts exact field values
      (time_ms=188928052, state=8/FAIL, raw=(0,0), is_gaze_valid()=False).
    - `TestGazeHelper` — raw, avg, and default (raw) variants.
    - `test_tracking_state_all_32_combinations` — parametrized over `range(32)`, checks each
      boolean against the expected bitmask value deterministically.
    - `test_is_gaze_valid` — 9 parametrized boundary cases (GAZE alone, GAZE+EYES+PRESENCE, state=0,
      EYES+PRESENCE, GAZE+FAIL, GAZE+LOST, GAZE+FAIL+LOST, FAIL alone, LOST alone).
    - `TestEyeDataFields` — field values and frozen-dataclass enforcement.
- Acceptance criteria:
  - PASS — round-trips every mock variant: valid binocular, eyes-only (no gaze), blink, LOST,
    malformed → FrameParseError. Test output: 59 passed in 0.23 s.
  - PASS — all 32 representable low-5-bit state combinations decode deterministically
    (parametrized table-driven test `test_tracking_state_all_32_combinations[0-31]`).
  - PASS — ruff/black/isort clean (2 files, 0 errors).
  - PASS — mypy --strict: "Success: no issues found in 1 source file".
  - PASS — coverage: `frames.py` 100% (70 stmts, 0 miss).
- Deviations from plan: none.
- Verified facts: no new wire-format discrepancies. `timestamp` field present in real frames is
  intentionally not stored in Frame (not in the schema per plan); `time` (monotonic ms) stored as
  `time_ms` as specified.
- Open issues handed to Phase 3: wire `parse_frame` into `EyeTribeClient.ReaderThread`; implement
  `EyeTracker._poll()` to drain `FrameBuffer` and emit `BinocularEyeSampleEvent`.
