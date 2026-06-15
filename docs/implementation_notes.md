# Implementation Notes — psychopy-eyetracker-eyetribe

These notes document the device-specific behaviour of the Eye Tribe plugin for
developers and advanced users.  The primary audience is anyone extending the
plugin, debugging unexpected behaviour, or cross-referencing against sibling
plugins (Pupil Labs Neon, Tobii, GazePoint).

---

## Architecture overview

```
PsychoPy / ioHub process
  └── EyeTracker(EyeTrackerDevice)          psychopy_eyetracker_eyetribe/eyetribe/eyetracker.py
        │  uses
        ├── EyeTribeClient                   eyetribe_client.py   (no PsychoPy imports)
        │     ├── ReaderThread  ──► FrameBuffer (bounded, 1024 frames)
        │     └── HeartbeatThread
        ├── parse_frame()                    frames.py            (no PsychoPy imports)
        ├── ClockSync                        time_sync.py         (no PsychoPy imports)
        ├── eyetribe_pixels_to_display()     transforms.py        (no PsychoPy imports)
        └── CalibrationSequencer             calibration.py       (no PsychoPy imports)
              │  TCP JSON (protocol v1)
              ▼
        Eye Tribe Server (real ET1000)   OR   MockEyeTribeServer
```

The PsychoPy-free core (`eyetribe_client`, `frames`, `transforms`, `time_sync`,
`calibration`) is fully unit-testable without PsychoPy installed.  The ioHub
`EyeTracker` class and `settings.py` are the only modules that import PsychoPy.

---

## iohub config key

```
eyetracker.hw.eyetribe.EyeTracker
```

---

## Device configuration keys

All keys live under `eyetracker.hw.eyetribe.EyeTracker:` in your ioHub config
or in the dict passed to `launchHubServer`.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `host` | str | `"127.0.0.1"` | IP address or hostname of the Eye Tribe Server |
| `port` | int | `6555` | TCP port of the Eye Tribe Server |
| `api_version` | int | `1` | Eye Tribe API protocol version (pinned to 1) |
| `gaze_source` | `"raw"` \| `"avg"` | `"raw"` | Per-sample raw gaze or server-smoothed average |
| `runtime_settings.sampling_rate` | `"auto"` \| `30` \| `60` | `"auto"` | Auto-adopted from server `framerate` at connect |
| `runtime_settings.track_eyes` | `"BINOCULAR"` | `"BINOCULAR"` | Always binocular (ET1000 has two cameras) |
| `calibration.target_count` | `5` \| `9` \| `12` | `9` | Number of calibration points |
| `event_buffer_length` | int | `1024` | ioHub native-event buffer size |
| `device_timer.interval` | float | `0.005` | ioHub poll interval in seconds (200 Hz) |
| `auto_report_events` | bool | `False` | Set to `True` to auto-stream events without `getEvents()` |
| `monitor_event_types` | list | `[BinocularEyeSampleEvent, FixationStartEvent, FixationEndEvent]` | Event types to report |

`sampling_rate: auto` reads the `framerate` key from the Eye Tribe Server at
connect time (30 Hz on the ET1000, 60 Hz on the Pro) and adopts it.  The poll
interval (`device_timer.interval`) is set independently; 200 Hz polling gives
ample headroom even at 60 Hz.

---

## Events generated

### BinocularEyeSampleEvent (50 fields)

One event per pushed frame.  Key fields:

| Index | Field | Source |
|-------|-------|--------|
| 5 | `device_time` | `frame.time_ms * 0.001` (monotonic seconds) |
| 6 | `logged_time` | `Computer.getTime()` at poll |
| 7 | `time` (`iohub_time`) | `ClockSync.to_psychopy_time(frame.time_ms)` |
| 11–12 | `left_gaze_x`, `left_gaze_y` | Left-eye gaze in display units (via `transforms.py`) |
| 14–15 | `left_eye_cam_x`, `left_eye_cam_y` | Left `pcenter` (normalised 0–1, pupil-camera coords) |
| 19–20 | `left_raw_x`, `left_raw_y` | Left-eye raw gaze in screen pixels |
| 21 | `left_pupil_measure1` | Left `psize` (arbitrary units — **not mm**) |
| 22 | `left_pupil_measure1_type` | `EyeTrackerConstants.PUPIL_AREA` |
| 30–31 | `right_gaze_x`, `right_gaze_y` | Right-eye gaze in display units |
| 34–35 | `right_eye_cam_x`, `right_eye_cam_y` | Right `pcenter` (normalised 0–1) |
| 38–39 | `right_raw_x`, `right_raw_y` | Right-eye raw gaze in screen pixels |
| 40 | `right_pupil_measure1` | Right `psize` (arbitrary units) |
| 49 | `status` | `0` = valid, `2` = invalid / uncalibrated |

Fields not listed above (z, angle, ppd, velocity, `measure2`) are
`EyeTrackerConstants.UNDEFINED`.

**Validity rule:** `status == 0` when `STATE_TRACKING_GAZE` is set **and** neither
`STATE_TRACKING_FAIL` nor `STATE_TRACKING_LOST` is set in the frame's `state`
bitmask (see §3 of DEVELOPMENT_PLAN.md).  Note that an uncalibrated tracker
can set `STATE_TRACKING_GAZE` but reports `(0, 0)` or out-of-range coordinates —
always calibrate before interpreting gaze.

### FixationStartEvent (29 fields)

Emitted when `frame.fix` transitions `False → True`.  Gaze / pupil values are
taken from the left eye at the moment of the transition.

### FixationEndEvent (65 fields)

Emitted when `frame.fix` transitions `True → False`.  Contains start, end, and
average gaze/pupil fields plus duration.

---

## Coordinate system

Eye Tribe gaze coordinates are in **screen pixels**, origin **top-left** (Y
increases downward).  The transform pipeline:

1. Normalise by server resolution: `norm_x = x_px / screenresw`,
   `norm_y = y_px / screenresh`.
2. Map to ioHub Display bounds `(left, top, right, bottom)` where, in Y-up
   display units (norm, height, pix), `top > bottom`.

See [docs/coordinate_systems.md](coordinate_systems.md) for worked examples and
the full transform equations.

---

## Time synchronisation

The Eye Tribe `time` field is a **monotonic millisecond counter** (relative,
~uptime — **not** Unix epoch; observed ≈ 1.889 × 10⁸ ms at start-up).

`ClockSync` pairs the first frame's `time` with the local PsychoPy `getTime()`
at receipt and computes an offset:

```
offset = local_time_s - tracker_time_ms / 1000
psychopy_time = tracker_time_ms / 1000 + offset
```

The offset is re-estimated every 5 s (configurable) to track slow drift.
Residual latency = 1/framerate ≈ 33 ms at 30 Hz (sampling jitter) plus socket
transport (typically < 1 ms on localhost).

---

## Calibration

`runSetupProcedure(calibration_args)` opens a full-screen PsychoPy window and
drives the Eye Tribe calibration protocol:

1. Sends `calibration start {pointcount}`.
2. For each normalised target position (see `calibration.point_layout()`):
   - Displays outer (red) + inner (white) concentric circles at the target
     position.
   - Waits 750 ms settle time while the participant fixates.
   - Sends `calibration pointstart {x_px, y_px}`.
   - Waits 1000 ms sample window.
   - Sends `calibration pointend`; collects `calibresult` from the reply.
3. Shows an accuracy summary (overall `deg`, per-point `ad`).
4. Offers **accept** (Space), **redo** (R), or **abort** (Escape).

Supported `target_count` values: **5, 9** (default), **12**.

The calibration window is always closed on exit (even on abort).

`CalibrationResult` fields:
- `success` — `bool`, `True` if the server reports `calibresult.result == True`
- `avg_error_deg` — mean accuracy across both eyes in degrees
- `per_point` — tuple of per-point dicts with `ad`, `adl`, `adr`, `cp`, `mecp`

---

## Mock server

`psychopy_eyetracker_eyetribe.mock.MockEyeTribeServer` ships with the package
and is used by the test suite and the coder demo.  It:

- Binds to a configurable port (pass `port=0` for OS-assigned free port).
- Speaks the Eye Tribe protocol (v1): `tracker set version`, `tracker get`,
  `tracker set push`, heartbeat enforcement.
- Pushes synthesized frames at a configurable rate (default 30 Hz) using
  `fixed_point_model` (centred at 960, 540) or a custom `GazeModel`.
- Supports injectable blink/lost segments via `make_blink_segment` /
  `make_lost_segment`.
- Provides a scriptable calibration responder (`calib_result` constructor arg).
- Thread-safe `get_calib_log()` for asserting calibration message sequences.

---

## Known limitations

- **Windows only** — the Eye Tribe Server is Windows-only; CI and the plugin are
  also Windows-only.
- **30 Hz** on the ET1000 (60 Hz on the Pro).  Plan paradigms that tolerate a
  33 ms inter-sample interval.
- **Pupil size in arbitrary units** — `psize` is reported as-is from the server.
  Do not interpret as physical pupil diameter in mm.
- **Calibration required** — uncalibrated gaze is meaningless (see Validity rule
  above).
- **No ppd / velocity fields** — `BinocularEyeSampleEvent` fields for pixels-
  per-degree and velocity are `UNDEFINED`; the Eye Tribe API does not provide
  them.
- **No `measure2`** — only `pupil_measure1` (psize) is populated.
