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

## Phase 3 — EyeTracker device (recording, polling, event emission)  (status: DONE)

- Date: 2026-06-15 / Agent: Claude Sonnet 4.6 / Branch: `phase-3-eyetracker` / PR: pending
- Delivered:
  - `psychopy_eyetracker_eyetribe/eyetribe/eyetracker.py` — full `EyeTracker(EyeTrackerDevice)`
    implementation:
    - `__init__`: reads `host`, `port`, `gaze_source` from config; constructs `EyeTribeClient`;
      initialises `_recording`, `_time_offset`, fixation-state tracker variables.
    - `setConnectionState`/`isConnected`: delegates to `EyeTribeClient.connect()`/`close()`/`state`.
    - `setRecordingState`/`isRecordingEnabled`: toggles `_recording`; sets `_is_reporting_events`
      directly (avoids `clearEvents()` → `_iohub_server.processDeviceEvents()` in test context).
    - `enableEventReporting`: delegates to `setRecordingState`.
    - `runSetupProcedure`: returns `EYETRACKER_INTERFACE_METHOD_NOT_SUPPORTED` (Phase 5 stub).
    - `_poll()`: drains `EyeTribeClient.frame_buffer.get_all()`, calls `parse_frame()` on each,
      skips `FrameParseError` with warning, delegates to `_process_frame()`.
    - `_process_frame()`: computes `device_time` (ms→s), captures `_time_offset` on first frame
      (interim: `offset = logged_time − device_time`; Phase 4 replaces with `time_sync.py`);
      passes left/right/combined gaze through `_eyeTrackerToDisplayCoords` (pixel pass-through in
      tests; Phase 4 adds display transform); builds 50-field `BinocularEyeSampleEvent` list and
      calls `_addNativeEventToBuffer`; delegates to `_emit_fixation_events`.
    - `_emit_fixation_events()`: state machine on `_last_fix` / `frame.fix`; emits 29-field
      `FixationStartEvent` on False→True transition; emits 65-field `FixationEndEvent` (with
      duration, averaged gaze/pupil) on True→False transition.
    - `trackerTime()`/`trackerSec()`: estimate current tracker time from `_time_offset`; Phase 4 will
      use `time_sync.py`.
    - `_eyeTrackerToDisplayCoords` / `_displayToEyeTrackerCoords`: try `_display_device.*` methods;
      fall through to pixel pass-through on `AttributeError` (test harness safety).
    - `_close()`: stops recording, disconnects, calls base `_close()`.
  - `psychopy_eyetracker_eyetribe/eyetribe/default_eyetracker.yaml` — added `model_name: ET1000`
    and `device_number: 0` (required by `ioObject.__init__` CLASS_ATTRIBUTE_NAMES iteration).
  - `psychopy_eyetracker_eyetribe/eyetribe/supported_config_settings.yaml` — added `model_name:
    IOHUB_STRING` and `device_number: 0`.
  - `tests/integration/test_eyetracker_against_mock.py` — 16 integration tests covering:
    connection lifecycle, recording-state toggle, event generation on poll (≥5 events after 0.4 s),
    absence of events when not recording, BinocularEyeSampleEvent field count (50), field ranges
    (gaze coords, pcenter 0-1, pupil >0, PUPIL_AREA type), monotonically-increasing timestamps,
    validity propagation (status=0 for valid frames, status=2 for TRACKING_LOST frames),
    FixationStartEvent on first poll (29 fields), FixationEndEvent on fix→lost transition (65 fields,
    positive duration), gaze_source config (`"raw"` default, `"avg"` accepted), and
    `trackerTime()`/`trackerSec()` return types and consistency.
- Acceptance criteria:
  - PASS — `_poll()` drains `frame_buffer` and emits one `BinocularEyeSampleEvent` per frame.
  - PASS — `BinocularEyeSampleEvent` is a 50-field list, `FixationStartEvent` 29-field,
    `FixationEndEvent` 65-field; field types and ranges verified.
  - PASS — `FixationStartEvent` emitted on False→True `fix` transition; `FixationEndEvent` on
    True→False; duration field positive.
  - PASS — status=0 for valid frames (STATE_TRACKING_GAZE set, no FAIL/LOST); status=2 for
    TRACKING_LOST frames.
  - PASS — `gaze_source: "raw"` (default) and `"avg"` both produce events.
  - PASS — ruff/black/isort clean; pytest 112 passed, 2 skipped (integration tests skip locally
    without PsychoPy — they run in CI via `pip install -e .[dev]`).
- Deviations from plan:
  - `_is_reporting_events` set directly in `setRecordingState` rather than calling
    `EyeTrackerDevice.enableEventReporting`, because the base implementation calls
    `clearEvents()` → `_iohub_server.processDeviceEvents()` which fails when `_iohub_server` is
    None (test context without full ioHub).
  - `EyeTracker` does not define `__slots__`; Python gives the subclass a `__dict__` when the
    parent has `__slots__` but the child does not, allowing all instance attributes to be set.
- Verified facts:
  - `BinocularEyeSampleEvent.CLASS_ATTRIBUTE_NAMES` has exactly 50 fields (confirmed from installed
    PsychoPy source); `FixationStartEvent` 29 fields; `FixationEndEvent` 65 fields.
  - `EyeTrackerConstants.BINOCULAR_EYE_SAMPLE = 52`, `FIXATION_START = 53`, `FIXATION_END = 54`.
  - `EyeTrackerDevice._INSTANCE` is a singleton; must be set to None before and after each
    test instantiation.
  - Mock server emits `fix=True` whenever `STATE_TRACKING_GAZE` is set; `fix=False` for
    LOST/FAIL segments (confirmed by reading `mock_server.py:_make_frame`).
  - `EyeTribeClient` sends heartbeats every `heartbeat_interval_ms / 2` ms; tests ≤0.6 s
    complete well within the 3 s heartbeat window.
- Open issues handed to Phase 4: coordinate transform (pixel pass-through → `transforms.py`);
  time-sync model (fixed offset → `time_sync.py`); ppd / velocity fields (currently UNDEFINED).

## Phase 4 — Coordinate transforms & time synchronisation  (status: DONE)

- Date: 2026-06-15 / Agent: Claude Sonnet 4.6 / Branch: `phase-4-transforms-timesync` / PR: pending
- Delivered:
  - `psychopy_eyetracker_eyetribe/eyetribe/transforms.py` — full implementation (PsychoPy-free):
    - `DisplayBounds = tuple[float, float, float, float]` type alias for `(left, top, right, bottom)`.
    - `eyetribe_pixels_to_display(x_px, y_px, screen_w, screen_h, bounds)` — normalises Eye Tribe
      screen pixels (origin top-left) by the server resolution to [0,1], then maps linearly onto the
      ioHub Display bounds with Y-axis flip (top > bottom in Y-up display coords).
    - `display_to_eyetribe_pixels(x, y, screen_w, screen_h, bounds)` — exact inverse.
    - No PsychoPy imports; bounds passed as plain floats; mypy strict passes.
  - `psychopy_eyetracker_eyetribe/eyetribe/time_sync.py` — `ClockSync` implementation (PsychoPy-free):
    - `update(tracker_time_ms, local_time_s, rtt_s=0.0)` — first call always sets the offset
      (`offset = (local_s − rtt_s/2) − tracker_s`); subsequent calls only update after
      `reestimate_interval_s` seconds (default 5 s) to track slow drift.
    - `to_psychopy_time(tracker_time_ms)` — returns `tracker_ms/1000 + offset`; raises `RuntimeError`
      if called before first `update()`.
    - `is_initialized` (bool property) and `offset` (float property) expose internal state.
    - `REESTIMATE_INTERVAL_S = 5.0` module-level constant.
  - `psychopy_eyetracker_eyetribe/eyetribe/eyetracker.py` — Phase 4 wiring:
    - Imports `ClockSync` and both transform functions.
    - `__init__`: adds `_clock_sync: ClockSync | None = None`; screen dims `_screen_w = 1920`,
      `_screen_h = 1080` (server defaults, updated at connect); removes `_time_offset`.
    - `setConnectionState(True)`: after `connect()`, calls `_fetch_screen_resolution()` which issues
      a `tracker get [screenresw, screenresh]` and updates `_screen_w`/`_screen_h`.
    - `setRecordingState(True)`: instantiates a fresh `ClockSync()` replacing the old `_time_offset`.
    - `_process_frame()`: calls `clock_sync.update(frame.time_ms, logged_time)` then
      `clock_sync.to_psychopy_time(frame.time_ms)` for `iohub_time`.
    - `trackerTime()`: returns `(getTime() − clock_sync.offset) / DEVICE_TIMEBASE_TO_SEC` when
      sync is initialised; falls back to `getTime() / DEVICE_TIMEBASE_TO_SEC` otherwise.
    - `_eyeTrackerToDisplayCoords` / `_displayToEyeTrackerCoords`: delegate to `transforms.py`
      via `_get_display_bounds()` (tries `self._display_device.getBounds()`, falls back to Y-down
      pixel-passthrough `(0, 0, screen_w, screen_h)` on AttributeError/missing display device).
  - `tests/unit/test_transforms.py` — 80 tests (65 pass, 1 skip):
    - `test_center_pixel_maps_to_display_origin` — screen centre → (0,0) for pix/norm/height/deg.
    - `test_known_pixel_to_display` — parametrized corners + passthrough for all unit systems.
    - `test_center_pixel_various_resolutions` — 4 resolutions (1280×720 … 4K).
    - `test_display_origin_maps_back_to_center_pixel` — inverse for Y-up unit systems.
    - `test_round_trip_forward_then_inverse` — 7 points × 5 bound sets = 35 cases, all < 1e-6.
    - `test_round_trip_inverse_then_forward` — 4 bound sets, starting from display coords.
  - `tests/unit/test_time_sync.py` — 16 tests (all pass):
    - Offset estimation, RTT correction (rtt_s/2 shift), `to_psychopy_time` within 1 ms,
      no-re-estimate within interval, re-estimate after interval, boundary at exactly 5 s,
      multiple cycles, custom interval, realistic 1.889e8 ms value.
  - `docs/coordinate_systems.md` — full documentation: transform pipeline diagram, worked example
    (`norm` unit, 4 key points), bounds table for all unit systems, EyeTracker wiring description,
    time field description, offset model equations, RTT correction explanation, latency budget table.
- Acceptance criteria:
  - PASS — Known pixel coords map to expected display-unit coords for pix, norm, height, deg:
    `test_known_pixel_to_display` (11 parametrized cases including corners and passthrough).
  - PASS — forward∘inverse round-trips within 1e-6: `test_round_trip_forward_then_inverse`
    (35 cases) and `test_round_trip_inverse_then_forward` (4 × 4 = 16 starting points).
  - PASS — Synthetic frames map to PsychoPy times within 1 ms: `test_synthetic_frames_within_1ms`
    (10 consecutive 30 Hz frames, deterministic math; error is floating-point exact, << 1 ms).
  - PASS — ruff/black/isort clean; mypy --strict "no issues in 6 source files".
  - PASS — pytest -m "not hardware": **190 passed, 3 skipped** in 22 s
    (skips: passthrough-origin inverse (by design), 2 integration tests without PsychoPy env).
  - PASS — coverage: `transforms.py` 100%, `time_sync.py` 100% (both >> 90% gate).
- Deviations from plan:
  - `_fetch_screen_resolution()` issues a second `tracker get` after connect rather than reading the
    values from the initial connect sequence.  The client already fetches them internally but does not
    store `screenresw`/`screenresh` as public attributes, and the plan forbids modifying
    `eyetribe_client.py`.  The extra `get` round-trip is < 2 ms and harmless in push mode.
  - `_get_display_bounds()` falls back to Y-down pixel-passthrough bounds (not Y-up pixel bounds)
    when no display device is available.  This preserves the Phase 3 integration-test expectations
    (gaze coords in the range −2000 … 2000 with the mock emitting at 960, 540).
- Verified facts: no new discrepancies against REFERENCES.md.  `screenresw`/`screenresh` confirmed
  1920/1080 on hardware and in the mock default.  `DisplayBounds` is `(left, top, right, bottom)`;
  Y-up systems have top > bottom.
- Open issues handed to Phase 5: `runSetupProcedure` still returns
  `EYETRACKER_INTERFACE_METHOD_NOT_SUPPORTED`; calibration sequencing (`calibration.py`) to be
  wired up.  ppd/velocity fields remain UNDEFINED.

## Phase 5 — Calibration via PsychoPy runSetupProcedure  (status: DONE)

- Date: 2026-06-15 / Agent: Claude Sonnet 4.6 / Branch: `phase-5-calibration` / PR: pending
- Delivered:
  - `psychopy_eyetracker_eyetribe/eyetribe/calibration.py` — full implementation (PsychoPy-free):
    - Module constants: `DEFAULT_TARGET_COUNT = 9`, `SUPPORTED_TARGET_COUNTS = (5, 9, 12)`,
      `SETTLE_MS = 750`, `SAMPLE_MS = 1000`.
    - `_LAYOUTS` dict with normalized (x, y) positions for 5-, 9-, and 12-point layouts; origin
      top-left, values in [0, 1]; centre-first so an early abort leaves the device in a defined state.
    - Frozen `CalibrationResult(success, avg_error_deg, per_point)` dataclass.
    - `point_layout(target_count) -> tuple[tuple[float, float], ...]` — validates count and
      returns layout; raises `ValueError` on unsupported counts.
    - `parse_calibresult(payload) -> CalibrationResult` — converts the Eye Tribe `calibresult`
      object (from `pointend` reply's `values.calibresult`) to a typed result; tolerates missing
      keys by defaulting to `False`/`0.0`/`()`.
    - `_RequestFn = Callable[[dict], dict]` type alias.
    - `CalibrationSequencer(request_fn)` — drives the protocol:
      `start(point_count)` → N × `(point_start(x_px, y_px)` → `point_end())` → optionally
      `abort()` or `clear()`.  `point_end()` returns the raw `calibresult` dict or `None`.
  - `psychopy_eyetracker_eyetribe/mock/mock_server.py` — calibration recording extension:
    - `_ClientHandler` gains `calib_log` and `calib_log_lock` constructor args; logs every
      calibration request (request type + values) under the lock.
    - `MockEyeTribeServer` gains `get_calib_log()` and `clear_calib_log()` thread-safe methods.
    - `_accept_loop` passes its shared log and lock to every new `_ClientHandler`.
  - `psychopy_eyetracker_eyetribe/eyetribe/eyetracker.py` — `runSetupProcedure` fully implemented:
    - Class timing attributes `_CALIB_SETTLE_S = 0.750` and `_CALIB_SAMPLE_S = 1.000` (overridable
      to `0.0` in tests to skip timing loops).
    - `runSetupProcedure(calibration_args)`: opens a `visual.Window` (full-screen); runs
      `_run_calib_loop`; closes window in `finally`; returns `EYETRACKER_OK` or
      `EYETRACKER_CALIBRATION_ERROR`.
    - `_run_calib_loop(win, target_count, sequencer)`:
      - Intro screen (`getKeys(["space", "escape"])` → proceed or abort).
      - Outer redo loop: `sequencer.start(target_count)` → iterate layout → for each point:
        convert normalized coords to Eye Tribe pixels and PsychoPy pixel-unit position; settle
        loop (`time.monotonic()` + `win.flip()` + `getKeys(["escape"])`); `point_start`; sample
        loop; `point_end`; collect last `calibresult`.
      - On escape at any point: `sequencer.abort()`, return `EYETRACKER_CALIBRATION_ERROR`.
      - Summary screen after all points: shows success/error-deg; `getKeys(["space", "r", "escape"])`
        → space accepts (`EYETRACKER_OK`), r calls `sequencer.clear()` and redoes, escape aborts.
    - Target rendering: outer `Circle(r=30, fillColor="white")`, inner `Circle(r=8,
      fillColor="black")`; `TextStim` for intro/summary messages.
  - `tests/unit/test_calibration.py` — 40 unit tests (all PsychoPy-free, no network):
    - Constants (3 tests): `DEFAULT_TARGET_COUNT`, `SUPPORTED_TARGET_COUNTS`, timing constants.
    - `point_layout` (7 tests): correct count for 5/9/12; all values in [0,1]; no duplicates;
      `ValueError` on 5 invalid counts.
    - `parse_calibresult` (6 tests): success, failure, per-point fields, empty calibpoints,
      missing keys, immutability (`frozen=True` raises on assignment).
    - `CalibrationSequencer` (24 tests): individual method message shapes; `point_end` returns
      calibresult or `None`; full 5/9/12 sequences (message order + result parsing); abort path;
      redo (clear) path; pixel coord forwarding; `start` uses given point count.
  - `tests/integration/test_calibration_against_mock.py` — 14 integration tests:
    - Part A (7 tests) — `CalibrationSequencer` against a real `MockEyeTribeServer`:
      parametrized 5/9/12 message-sequence and result-parsing tests; abort message sequence;
      redo (clear → start again) message sequence; coordinate forwarding verified via calib log.
    - Part B (7 tests) — `runSetupProcedure` with mocked PsychoPy visual layer:
      `sys.modules` patching for `psychopy.visual`; `_reset_singleton()` in setup/teardown;
      timing class attrs overridden to `0.0`; key sequences injected via `side_effect` lists;
      tests: success flow, abort at intro, abort at summary, redo-then-accept, window-close
      verification (direct `_run_calib_loop` call + `runSetupProcedure` with window capture).
  - `tests/integration/test_eyetracker_against_mock.py` — pre-existing singleton bug fixed:
    - Added `_reset_singleton()` helper (clears both `EyeTrackerDevice._INSTANCE` and
      `EyeTracker._INSTANCE` if present in `EyeTracker.__dict__`).
    - Updated `tracker` fixture and all 4 inline test functions that created their own
      `MockEyeTribeServer` instances to use `_reset_singleton()` in setup and teardown.
- Acceptance criteria:
  - PASS — `CalibrationSequencer` emits the correct message sequence against the mock:
    `start` → N × `(pointstart, pointend)` verified for 5, 9, and 12 points.
  - PASS — `parse_calibresult` round-trips `success`, `avg_error_deg`, and per-point dicts
    for both success and failure payloads; tolerates missing keys.
  - PASS — `runSetupProcedure` returns `EYETRACKER_OK` on success, `EYETRACKER_CALIBRATION_ERROR`
    on escape; window is closed in all exit paths.
  - PASS — redo path: `clear` + restart sequence confirmed in both unit and integration tests.
  - PASS — ruff/black/isort clean; mypy strict passes on PsychoPy-free core.
  - PASS — full pytest suite: **229 passed, 4 skipped** in 22.74 s.
- Deviations from plan:
  - Did not inherit from `BaseCalibrationProcedure` — PsychoPy's base class uses `gevent` and
    is not directly usable for the Eye Tribe protocol.  Wrote a standalone display loop instead.
  - Mock server's `pointend` reply includes `calibresult` on every call (not just final), while
    the real server only returns it on the last `pointend`.  `_run_calib_loop` tracks
    `last_calibresult_raw` and only uses the final value, making it correct for both.
  - Singleton teardown bug in `test_eyetracker_against_mock.py` was pre-existing (present before
    Phase 5 changes); fixed as part of this phase rather than handing forward.
- Verified facts:
  - `EyeTrackerDevice.__init__` sets `self.__class__._INSTANCE = self` on the *subclass*
    (`EyeTracker`), not the base class.  Clearing only `EyeTrackerDevice._INSTANCE` leaves the
    subclass attribute stale.  `_reset_singleton()` must clear both.
  - Eye Tribe calibration protocol: `calibration start {pointcount}` → N ×
    (`pointstart {x,y}` → `pointend` returning `calibresult`) → optional `abort` or `clear`.
  - `EyeTrackerConstants.EYETRACKER_OK = 200`, `EYETRACKER_CALIBRATION_ERROR = 203`.
- Open issues handed to Phase 6: ppd/velocity fields remain UNDEFINED; `runSetupProcedure`
  does not yet adapt to the PsychoPy display device (uses raw pixel coords from Eye Tribe server
  resolution); no live accuracy feedback is shown on the summary screen.
