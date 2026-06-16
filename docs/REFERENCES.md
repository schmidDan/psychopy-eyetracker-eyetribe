# REFERENCES — verified, externally-fixed facts

Phase 0 fills this in by reading the **installed** PsychoPy 2026.1.3 and the Eye Tribe
documentation. Items marked **[CONFIRMED]** are already verified; **[TO CONFIRM ON MACHINE]**
must be checked against the installed PsychoPy / hardware before the dependent phase relies on them.
The discrepancy procedure (DEVELOPMENT_PLAN.md section 2) applies if any check fails.

## Environment
- **[CONFIRMED]** PsychoPy **2026.1.3** Standalone (Windows), at `C:\Program Files\PsychoPy`.
- **[CONFIRMED]** Bundled interpreter: **Python 3.10.11** (`"C:\Program Files\PsychoPy\python.exe" --version`).

## Packaging & discovery
- **[CONFIRMED]** Reference plugin `psychopy/psychopy-eyetracker-pupil-labs`: setuptools, flat layout,
  `[tool.setuptools.packages.find] where = ["", "<pkg>"]`, `package-data "*" = ["*.yaml"]`.
- **[CONFIRMED — corrected post-Phase-7]** Device entry-point group:
  `psychopy.iohub.devices.eyetracker.hw` (name -> module). The `.hw` suffix is required; verified working
  by the `launchHubServer` 32-event run, and `test_discovery.py` asserts this group.
- **[CONFIRMED]** Builder settings entry-point group: `psychopy.experiment.components.settings.eyetracking`.
- **[CONFIRMED — 2026-06-15]** Both entry points are registered after `pip install -e .[dev]`, and the
  `EyeTracker` class imports under PsychoPy (`test_eyetracker_class_loads_under_psychopy` passes).
- **[CONFIRMED — 2026-06-15, via `check_discovery.py`]** `psychopy.plugins.scanPlugins()` returns **1**
  (our plugin is seen) and `activatePlugins()` runs cleanly. PsychoPy does **NOT** create an importable
  module for the device: after activation, both
  `import psychopy.iohub.devices.eyetracker.hw.eyetribe` and `...eyetracker.eyetribe` raise
  `ModuleNotFoundError`. **Mechanism (pinned):** ioHub resolves the device class from the
  `psychopy.iohub.devices.eyetracker.hw` entry point **at `launchHubServer` time**, keyed by the config
  string `eyetracker.hw.eyetribe.EyeTracker`; there is no static importable `hw.<vendor>` module.
  Verified by a `launchHubServer` end-to-end run (32 events recorded). The earlier
  "bare import resolves" expectation was wrong and has been removed from the plan + HUMAN_TASKS.
  End-to-end device load is exercised in Phase 1/3 against the mock via
  `launchHubServer(**{'eyetracker.hw.eyetribe.EyeTracker': {...}})`.

## ioHub device YAML
- **[CONFIRMED — 2026-06-15]** `default_eyetracker.yaml` is the correct filename — present in the
  installed tree at `…/iohub/devices/eyetracker/default_eyetracker.yaml` and
  `…/iohub/devices/eyetracker/hw/mouse/default_eyetracker.yaml`.
- **[CONFIRMED — 2026-06-15]** The in-tree MouseGaze device dir contains exactly
  `default_eyetracker.yaml` + `supported_config_settings.yaml` (plus `eyetracker.py`, `calibration.py`,
  `__init__.py`) — so **both our YAML filenames are correct**; no rename. Use MouseGaze's YAMLs
  (4372 / 3548 bytes) as the key/token template when fleshing ours out in Phase 3.

## ioHub EyeTrackerDevice interface
- **[CONFIRMED — 2026-06-15]** The `psychopy.iohub.devices.eyetracker.EyeTrackerDevice` import path is
  correct and our `EyeTracker(EyeTrackerDevice)` subclass imports cleanly under PsychoPy 2026.1.3 (the
  `test_eyetracker_class_loads_under_psychopy` test passes). Method surface confirmed below.
- **[CONFIRMED — 2026-06-15]** Base class source: `…/psychopy/iohub/devices/eyetracker/__init__.py`.
  Every method our stub overrides exists on the base, plus `DEVICE_TIMEBASE_TO_SEC` (class attr — our
  `0.001` hook is valid), `getPos`, `getCalibrationDict`, `getCurrentDeviceState`, `sendCommand`,
  `sendMessage`, `resetState`, `isReportingEvents`, filter helpers, and the native-event plumbing
  (`_addNativeEventToBuffer`, `_handleNativeEvent`, `_getIOHubEventObject`, `_iohub_event_buffer`).
  **Phase 3 guidance:** the base already implements
  `getEvents`/`clearEvents`/`getConfiguration`/`getLastSample`/`getLastGazePosition`/`getPosition`/
  `isReportingEvents` — do **not** re-implement them; generate events in `_poll()` and push them through
  the base buffer. Device-specific overrides only: `setConnectionState`/`isConnected`,
  `setRecordingState`/`isRecordingEnabled`, `enableEventReporting`, `_poll`, `trackerTime`/`trackerSec`,
  `runSetupProcedure`, `_eyeTrackerToDisplayCoords`/`_displayToEyeTrackerCoords`.
- **[CONFIRMED — 2026-06-15]** `BinocularEyeSampleEvent` fields (from `CLASS_ATTRIBUTE_NAMES`). Mapping
  Eye Tribe frame → event: `left/right_gaze_x,y` ← transform(per-eye `lefteye`/`righteye` gaze, per
  `gaze_source`); `left/right_eye_cam_x,y` ← per-eye `pcenter` (normalized 0–1, no transform);
  `left/right_pupil_measure1` ← per-eye `psize`, with `left/right_pupil_measure1_type` set to a pupil-type
  constant (document arbitrary units); `left/right_raw_x,y` ← per-eye device `raw` px (optional);
  `status` ← 0 valid / 2 invalid per the validity rule below. Unused fields (z, angle, ppd, velocity,
  `measure2`) left at defaults. The combined binocular gaze (`frame.raw`/`avg`) feeds `getLastGazePosition`.
- **[CONFIRMED — 2026-06-15]** Builder settings backend base class is **`EyetrackerBackend`** in
  `psychopy.experiment.components.settings.eyetracking` (module also exposes `MouseGazeEyetrackerBackend`
  — the Phase 6 template — `knownEyetrackerBackends`, and `Param`). `settings.py` corrected to import
  `EyetrackerBackend` (the earlier `EyetrackingBackend` guess was wrong). MRO verified on machine:
  `EyeTribeEyetrackerBackend → EyetrackerBackend → object`.

## Eye Tribe Tracker API
- **[CONFIRMED via docs]** Message envelope, `state` bitmask, calibration sequence, heartbeat — see
  DEVELOPMENT_PLAN.md section 3.
- **[CONFIRMED via 8a smoke, 2026-06-15]** Live ET1000 + Server **0.9.77** stream confirmed:
  `framerate: 30`, `screenresw/h: 1920/1080`, `trackerstate: 0`; `_captured_frame.json` saved.
  `pcenter` normalized 0–1; `psize` arbitrary units (~10–20 observed); per-eye blocks present (the
  other eye may read `0,0` in a given frame).
- **[CORRECTION — frame `time`]** `time` is a **monotonic millisecond counter** (relative, ~uptime —
  observed ≈1.889e8 ms, +33 ms/frame at 30 Hz), **NOT** Unix epoch. The separate `timestamp` field is
  the wall-clock string (e.g. `"2026-06-15 14:30:14.068"`). Time-sync pairs `time` (ms) with the
  PsychoPy clock via an offset — the monotonic counter is preferable (no wall-clock jumps).
  Reconciled in DEVELOPMENT_PLAN.md §3 + §Phase 4 and in `time_sync.py`.
- **[CORRECTION — push framing]** In push mode this Server build sends frames as
  `{"category":"tracker","request":"get","values":{"frame":{...}}}` — `request` is **"get"**, not
  "push". The reader MUST detect frame messages by **presence of `values.frame`**, not by the
  `request` string. (Affects the Phase 1 `EyeTribeClient` reader.)
- **[OBSERVED — gaze validity]** Uncalibrated gaze `raw`/`avg` are `0,0` on most frames and wildly
  out-of-range when present (e.g. x≈15369 on a 1920-wide screen). `state == 7`
  (GAZE|EYES|PRESENCE) does **not** guarantee a usable gaze point. Validity logic (Phase 2/3) must
  require **calibrated + gaze within screen bounds**, not the `STATE_TRACKING_GAZE` bit alone; gaze is
  only meaningful after a successful calibration.
- **[TODO — Phase 10]** Capture a **calibrated** golden frame (the current `_captured_frame.json` is
  uncalibrated) for realistic parser/transform fixtures.
