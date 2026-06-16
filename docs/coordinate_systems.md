# Coordinate Systems & Time Synchronisation

## 1. Coordinate systems

### 1.1 Eye Tribe pixel space

| Property | Value |
|---|---|
| Origin | **Top-left corner** of the screen |
| X axis | Increases to the right (0 → `screen_w`) |
| Y axis | Increases **downward** (0 → `screen_h`) |
| Units | Screen pixels (float) |
| Resolution | `screenresw` × `screenresh` from the Eye Tribe Server at connect |
| Source fields | `frame.raw`, `frame.avg`, `frame.lefteye.raw`, `frame.righteye.avg`, … |

### 1.2 ioHub display coordinate space

| Property | Value |
|---|---|
| Origin | **Centre** of the display (for `pix`, `norm`, `height`) |
| X axis | Increases to the right (negative = left) |
| Y axis | Increases **upward** — opposite to Eye Tribe pixel space |
| Units | Determined by the ioHub `Display` device configuration |

### 1.3 Transform pipeline

```
Eye Tribe pixel (x_px, y_px)
        │  ÷ screen_w / screen_h
        ▼
Normalised [0, 1]:   norm_x = x_px / screen_w     (0 = left,   1 = right)
                     norm_y = y_px / screen_h     (0 = top,    1 = bottom)
        │  linear map onto display_bounds
        ▼
Display units (disp_x, disp_y)
```

**Forward** (`eyetribe_pixels_to_display`):

```
norm_x = x_px / screen_w
norm_y = y_px / screen_h

disp_x = left  + norm_x × (right  − left)
disp_y = top   + norm_y × (bottom − top)     ← Y-flip: bottom < top in Y-up space
```

**Inverse** (`display_to_eyetribe_pixels`):

```
norm_x = (disp_x − left)   / (right  − left)
norm_y = (disp_y − top)    / (bottom − top)

x_px = norm_x × screen_w
y_px = norm_y × screen_h
```

### 1.4 Worked example — 1920 × 1080 screen, `norm` units

Bounds: `(left=−1, top=1, right=1, bottom=−1)`

| Eye Tribe pixel | norm_x | norm_y | disp_x | disp_y | Description |
|---|---|---|---|---|---|
| (0, 0) | 0 | 0 | −1 | 1 | top-left corner |
| (960, 540) | 0.5 | 0.5 | 0 | 0 | screen centre |
| (1920, 1080) | 1 | 1 | 1 | −1 | bottom-right corner |
| (480, 270) | 0.25 | 0.25 | −0.5 | 0.5 | upper-left quadrant centre |

### 1.5 Display bounds per coordinate unit (1920 × 1080 monitor)

| Unit | left | top | right | bottom | Notes |
|---|---|---|---|---|---|
| `pix` | −960 | 540 | 960 | −540 | centre origin, Y-up, pixels |
| `norm` | −1 | 1 | 1 | −1 | centre origin, Y-up, unitless |
| `height` | −8/9 ≈ −0.889 | 0.5 | 8/9 ≈ 0.889 | −0.5 | Y-up, height = 1 |
| `deg` | *(monitor-calibration-dependent)* | | | | e.g. (−12.85, 7.2, 12.85, −7.2) |
| *(no display device)* | 0 | 0 | 1920 | 1080 | Y-down pixel passthrough |

### 1.6 EyeTracker wiring (Phase 9)

`EyeTracker._eyeTrackerToDisplayCoords(pixel_point)`:

Delegates directly to the ioHub `Display` device:

```python
self._display_device._pixel2DisplayCoord(gaze_x, gaze_y, self._display_device.getIndex())
```

Eye Tribe gaze coordinates are already in screen pixels with a top-left origin,
which is exactly the input format expected by `_pixel2DisplayCoord`.  The Display
device converts them to whatever unit system the experiment is using (`pix`, `norm`,
`height`, `deg`) and handles multi-monitor index resolution.  This matches the
base-class default implementation.

Falls back to a raw pixel pass-through `(gaze_x, gaze_y)` when no Display device
is available (unit-test harness without ioHub subprocess).

`EyeTracker._displayToEyeTrackerCoords(x, y)`:

```python
self._display_device.display2PIxelCoord(x, y, self._display_device.getIndex())
```

Note the capitalisation (`PIxelCoord`), matching the spelling in the installed
PsychoPy 2026.1.3 source.

> **Pre-Phase-9 behaviour (removed):** the override called
> `self._display_device.getBounds()`, which is not an ioHub Display method.  It
> raised, the silent `except` returned raw top-left pixels, and gaze appeared in
> pixel coords (0–1920) regardless of the experiment's unit setting.  Fixed in
> Phase 9 (`psychopy_eyetracker_eyetribe/eyetribe/eyetracker.py`); `transforms.py`
> is no longer part of the device path and has been deleted.

---

## 2. Time synchronisation

### 2.1 Eye Tribe `time` field

The `time` field in every pushed frame is a **monotonic millisecond counter**
(~uptime), **NOT** a Unix epoch timestamp.  Confirmed on hardware (ET1000,
Server 0.9.77, 2026-06-15): observed ≈ 1.889 × 10⁸ ms (+33 ms/frame at 30 Hz).

The companion `timestamp` string field is the local wall-clock time
(`"2026-06-15 14:30:14.068"`); it is *not* used for synchronisation because it
is subject to wall-clock jumps.

### 2.2 Clock offset model

At the start of each recording session `ClockSync` pairs the first arriving
frame's `time` field with the PsychoPy clock at receipt:

```
tracker_s       = tracker_time_ms / 1000
corrected_local = local_time_s − rtt_s / 2
offset          = corrected_local − tracker_s
```

The `rtt_s / 2` term corrects for the one-way transmit delay estimated from a
measured request/reply round-trip time.  For streaming frames (no per-frame RTT)
pass `rtt_s=0.0`.

Subsequent timestamp conversions:

```
psychopy_time = tracker_time_ms / 1000 + offset
```

The offset is re-estimated at most once every 5 s (`REESTIMATE_INTERVAL_S`) to
track slow clock drift without over-reacting to individual noisy samples.

### 2.3 Residual latency budget (@ 30 Hz)

| Source | Latency |
|---|---|
| Sampling period (1 / frame_rate) | ≈ 33 ms |
| USB transfer + Eye Tribe Server processing | ~2–5 ms (manufacturer spec) |
| TCP loopback transport | < 1 ms |
| ioHub poll interval (`device_timer.interval = 0.005 s`) | ≤ 5 ms |
| **Total worst-case** | **≤ ~44 ms** |

The dominant contributor is the 30 Hz sampling rate.  The clock-sync offset
compensates for systematic latency; residual jitter is bounded within one
sampling interval (≈ 33 ms at 30 Hz).
