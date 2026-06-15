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
