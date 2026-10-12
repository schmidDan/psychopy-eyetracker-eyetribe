# psychopy-eyetracker-eyetribe
[![CI](https://github.com/schmidDan/psychopy-eyetracker-eyetribe/actions/workflows/ci.yml/badge.svg)](https://github.com/schmidDan/psychopy-eyetracker-eyetribe/actions/workflows/ci.yml)

A native [PsychoPy](https://psychopy.org) ioHub eye-tracker plugin for **The Eye Tribe (ET1000)**.

Once installed, the device is selectable in the Builder *Eyetracker* component and usable from
Coder via the ioHub Common Eye Tracker Interface (config key
`eyetracker.hw.eyetribe.EyeTracker`), with PsychoPy-driven calibration.

---

## Contents

- [Requirements](#requirements)
- [Install](#install)
- [Quick start (Coder)](#quick-start-coder)
- [Quick start (Builder)](#quick-start-builder)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Requirements

- **Windows 10/11 x64** — the Eye Tribe Server runs reliably only on Windows.
- **PsychoPy 2026.1.3** Standalone (bundles Python 3.10.11).
- **Eye Tribe Server** — download from the
  [sdk-installers releases](https://github.com/EyeTribe/sdk-installers/releases) page;
  install and launch it before running experiments.  The server binds to
  `127.0.0.1:6555` by default.
- An **ET1000** connected via **USB 3.0** (for real use; development and CI use the
  bundled mock — no hardware needed).

---

## Install

### From a GitHub Release (recommended for end users)

Download the `.whl` from the
[Releases](https://github.com/schmidDan/psychopy-eyetracker-eyetribe/releases) page and install it into
the PsychoPy Standalone Python environment (run from an Administrator terminal):

```bat
"C:\Program Files\PsychoPy\python.exe" -m pip install psychopy_eyetracker_eyetribe-<version>-py3-none-any.whl
```

> **Distribution:** GitHub Release only (no public PyPI).

### Development install

```bash
# Python 3.10 environment with PsychoPy available
pip install -e .[dev]
```

---

## Quick start (Coder)

### Hardware-free demo (mock, no ET1000 required)

The bundled [examples/coder_demo.py](examples/coder_demo.py) starts the in-process mock
server and records one second of synthetic gaze data:

```bash
python examples/coder_demo.py
```

Expected output:

```
[demo] Mock Eye Tribe Server started on 127.0.0.1:<port>
[demo] Connecting …
[demo] Connected.  Sampling rate: 30 Hz
[demo] Mock mode: skipping visual calibration.
[demo] Recording for 1.0 s …
[demo] Recording stopped.
[demo] Collected 66 events: 30 BinocularEyeSamples, ...
[demo] First sample: time=... left_gaze=(...) pupil=... status=invalid/uncalibrated
[demo] Done.
[demo] Mock server stopped.
```

For a real ET1000 run:

```bash
python examples/coder_demo.py --no-mock
```

### In a PsychoPy experiment

Use `launchHubServer` to integrate the Eye Tribe with the full ioHub event loop:

```python
from psychopy import core, visual
from psychopy.iohub import launchHubServer

win = visual.Window([1920, 1080], fullscr=True, units="norm")

io = launchHubServer(**{
    "eyetracker.hw.eyetribe.EyeTracker": {
        "name": "tracker",
        "host": "127.0.0.1",
        "port": 6555,
        "gaze_source": "raw",          # "raw" (default) or "avg"
        "calibration": {"target_count": 9},  # 5, 9 (default), or 12
    }
})
tracker = io.devices.tracker

tracker.setConnectionState(True)
tracker.runSetupProcedure()        # PsychoPy-driven 9-point calibration

tracker.setRecordingState(True)
core.wait(2.0)                     # collect 2 s of gaze data

for event in tracker.getEvents():
    gaze_x = event.left_gaze_x    # display units (norm in this example)
    gaze_y = event.left_gaze_y
    pupil  = event.left_pupil_measure1  # arbitrary units — not mm

tracker.setRecordingState(False)
tracker.setConnectionState(False)
io.quit()
win.close()
```

**BinocularEyeSampleEvent key fields** (see
[docs/implementation_notes.md](docs/implementation_notes.md) for the full field table):

| Field | Description |
|-------|-------------|
| `left_gaze_x`, `left_gaze_y` | Left-eye gaze in display units (norm / pix / height) |
| `right_gaze_x`, `right_gaze_y` | Right-eye gaze in display units |
| `left_pupil_measure1`, `right_pupil_measure1` | Pupil size — **arbitrary units, not mm** |
| `left_eye_cam_x`, `left_eye_cam_y` | Left pupil-centre, normalised 0–1 |
| `status` | `0` = valid, `2` = invalid / uncalibrated |

---

## Quick start (Builder)

1. Install the plugin wheel into PsychoPy's Python environment (see [Install](#install)).
2. Open **PsychoPy Builder** and create or open an experiment.
3. Open **Experiment Settings** → **Online** tab → locate the *Eyetracker* dropdown and
   select **Eye Tribe**.
4. Configure host, port, gaze source, and calibration target count.
5. The Eyetracker component handles calibration, recording start/stop, and gaze-contingent
   stimuli automatically.

A ready-to-open Builder experiment is provided in
[examples/builder_example.psyexp](examples/builder_example.psyexp).

---

## Limitations

| Limitation | Detail |
|---|---|
| **Sampling rate** | Auto-adopted from the server: **30 Hz** (ET1000) or 60 Hz (Pro). Plan paradigms that tolerate a 33 ms inter-sample interval. |
| **Pupil size units** | Reported as **arbitrary units** (observed range ≈ 10–20), not millimetres. Do not interpret as physical pupil diameter. |
| **Gaze signal** | Default is **raw** (per-sample, unfiltered). Switch to `gaze_source: "avg"` for the server-side smoothed signal. |
| **Platform** | **Windows 10/11 x64 only.** The Eye Tribe Server does not run on macOS or Linux. |
| **Calibration required** | Uncalibrated gaze coordinates are meaningless (`0,0` or wildly out of range). Always run `runSetupProcedure()` before recording. |
| **No-gaze sentinel `(0, 0)`** | The Eye Tribe reports `raw/avg = (0, 0)` as a "no gaze this frame" sentinel even when `state == 7` (tracking active). The plugin treats combined gaze of exactly `(0, 0)` as invalid (`status = 2`) and does not update the last-known gaze position, so phantom origin samples never appear in valid gaze data. |
| **No ppd / velocity** | Pixels-per-degree and velocity fields in `BinocularEyeSampleEvent` are `UNDEFINED`; the Eye Tribe API does not provide them. |

---

## Troubleshooting

### Eye Tribe Server not running / connection refused

```
EyeTribeClient: connect attempt 1/3 failed: [WinError 10061] No connection could be made
```

- Ensure the Eye Tribe Server is installed and running (system tray icon visible).
- Check that the ET1000 is connected via USB 3.0 and the server shows `trackerstate 0`.
- The server binds to `127.0.0.1:6555` by default; verify no firewall blocks local
  loopback connections.

### Port conflict

If another process occupies port 6555, the Eye Tribe Server will fail to start.
Identify the conflicting process:

```bat
netstat -ano | findstr :6555
```

### Heartbeat timeout / disconnection mid-experiment

The plugin sends a heartbeat every `heartbeatinterval / 2` ms (default 1500 ms).
If the ioHub polling loop is blocked for longer than the server's `heartbeatinterval`
(default 3 s), the server drops the connection.

- Keep `device_timer.interval` at `0.005` s (the default 200 Hz poll rate).
- Avoid long blocking calls in the experiment loop.

### `trackerstate` ≠ 0 after connect

| `trackerstate` | Meaning |
|---|---|
| `0` | Connected, streaming — **normal** |
| `1` | Device not found |
| `2` | Connected, bad firmware |
| `3` | Connected, no USB 3.0 port |
| `4` | Connected, no stream |

- Ensure USB 3.0 (blue port).
- Reinstall / restart the Eye Tribe Server if firmware is flagged.

### Gaze is `(0, 0)` or wildly out of range after calibration

- Confirm calibration succeeded (`calibresult.result == True`, accuracy ≈ 0.5–1°).
- An uncalibrated tracker sets `STATE_TRACKING_GAZE` but reports `(0, 0)` — always
  calibrate first.
- Check `event.status == 0` before using gaze coordinates.

---

## Further reading

- [docs/implementation_notes.md](docs/implementation_notes.md) — device config keys,
  event field table, coordinate system, calibration protocol, known limitations.
- [docs/coordinate_systems.md](docs/coordinate_systems.md) — transform math, worked
  example, timing model.
- [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) — full design specification.
- [CHANGELOG.md](CHANGELOG.md) — version history.

---

## License

GPL-3.0. See [LICENSE](LICENSE).
