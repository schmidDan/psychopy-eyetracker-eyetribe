# Phase 3 handoff prompt

Copy the fenced block below to brief the Phase 3 coding agent.

**Prerequisite:** Phases 1–2 merged. **Environment:** needs **PsychoPy 2026.1.3** (the integration test
launches a real ioHub server) — run on the Windows machine or CI.

---

````
You are implementing **Phase 3 — ioHub EyeTracker class (recording & polling)** of
`psychopy-eyetracker-eyetribe`. Phases 0–2 are merged: the transport (`EyeTribeClient`), the mock
server, and the frame model (`frames.parse_frame`) all exist and are tested.

## Read first (authoritative)
- `docs/DEVELOPMENT_PLAN.md` — §3 (wire format), §4 (architecture), §6, and the **Phase 3** section.
- `docs/REFERENCES.md` — especially "ioHub EyeTrackerDevice interface" (CONFIRMED): the base class
  provides `getEvents`/`clearEvents`/`getConfiguration`/`getLastSample`/`getLastGazePosition`/
  `getPosition`/`isReportingEvents` and the native-event buffer — **rely on the base; do not
  re-implement them.** Also read the confirmed `BinocularEyeSampleEvent` field mapping there.
- The base class source on the machine:
  `C:\Program Files\PsychoPy\Lib\site-packages\psychopy\iohub\devices\eyetracker\__init__.py`, and the
  in-tree MouseGaze device (`…/eyetracker/hw/mouse/eyetracker.py`) as a concrete reference.
- Stubs: `psychopy_eyetracker_eyetribe/eyetribe/eyetracker.py`, plus
  `default_eyetracker.yaml` / `supported_config_settings.yaml` (mirror MouseGaze's two YAMLs as the
  key/token template).
- `tests/integration/test_eyetracker_against_mock.py` (placeholder to implement).

## Scope — implement ONLY the device class + its YAML
- `EyeTracker(EyeTrackerDevice)` — implement only device-specific methods: `__init__`,
  `setConnectionState`/`isConnected`, `setRecordingState`/`isRecordingEnabled`, `enableEventReporting`,
  `_poll()`, `trackerTime`/`trackerSec`. Use `EyeTribeClient` for the connection and the bounded frame
  buffer.
- `_poll()` drains buffered raw frame dicts, parses them with `frames.parse_frame`, and emits one
  `BinocularEyeSampleEvent` per frame via the base native-event buffer, with the confirmed mapping
  (REFERENCES.md): `left/right_gaze_x,y` ← per-eye gaze (per `gaze_source`, default `raw`);
  `left/right_eye_cam_x,y` ← `pcenter`; `left/right_pupil_measure1` (+ `_type`) ← `psize` (arbitrary
  units); `status` ← validity (state-level + in-bounds). Derive fixation start/end events from `fix`
  transitions.
- **Interim for this phase** (full versions are Phase 4): coordinate conversion may be a simple
  normalize-by-screen-resolution pass-through, and `trackerTime` may use a fixed offset captured at
  recording start. Leave `_eyeTrackerToDisplayCoords`/`_displayToEyeTrackerCoords` as thin hooks that
  Phase 4 will back with `transforms.py`; do not implement the full transform/clock model here.
- `default_eyetracker.yaml` with the concrete defaults listed in the plan's Phase 3 (host 127.0.0.1,
  port 6555, api_version 1, `runtime_settings.sampling_rate: auto`, track_eyes BINOCULAR,
  gaze_source raw, calibration.target_count 9, event_buffer_length 1024, device_timer.interval 0.005,
  auto_report_events False, monitor_event_types). `supported_config_settings.yaml` enumerates the same
  keys with allowed values/types (use MouseGaze's file as the schema template).

## Do NOT touch
- `eyetribe_client.py`, `mock/`, `frames.py` (done — read only). `transforms.py`/`time_sync.py`
  (Phase 4), `calibration.py`/`runSetupProcedure` (Phase 5 — leave `runSetupProcedure` a stub),
  `settings.py` (Phase 6). Don't change pinned decisions (plan §2 procedure for genuine discrepancies).

## Acceptance criteria (from the plan)
- `launchHubServer(**{'eyetracker.hw.eyetribe.EyeTracker': {...}})` starts against the **mock**; samples
  flow through `io.devices.tracker.getEvents()` with correct field values; recording toggles on/off.
- Sample timestamps are in the PsychoPy timebase (interim fixed offset acceptable).
- `gaze_source` config switches raw vs avg, asserted in the test.
- `tests/integration/test_eyetracker_against_mock.py` runs a real ioHub server process against the mock
  and asserts event counts, field ranges, validity propagation, recording state changes.

## Conventions (§6)
- `eyetracker.py` is PsychoPy-coupled (excluded from `mypy --strict`); keep all PsychoPy-free logic in
  the existing core modules. `ruff`/`black`/`isort` clean. Integration test marked `@pytest.mark.integration`.
- Branch `phase-3-eyetracker`; Conventional Commits; PR `Phase 3: ioHub EyeTracker (recording & polling)`
  with acceptance checklist + evidence; append a Phase 3 section to `docs/REPORT.md`.

## Dev/test commands (PsychoPy required)
```
& "C:\Program Files\PsychoPy\python.exe" -m pip install -e .[dev]
& "C:\Program Files\PsychoPy\python.exe" -m ruff check .
& "C:\Program Files\PsychoPy\python.exe" -m pytest -m "not hardware" -q
```
````
