# Hardware validation ([HARDWARE])

Each item is one script under `tests/manual/`; ordered so failures localize.
Record for every run: device serial, Eye Tribe Server version, Windows build, date, operator,
result, evidence path.

## Run environment

| Field              | Value |
|--------------------|-------|
| Device serial      | _fill in_ |
| Eye Tribe Server   | _fill in (e.g. 0.9.77)_ |
| Windows build      | _fill in_ |
| PsychoPy version   | 2026.1.3 |
| Python             | 3.10.11 |
| Date               | _fill in_ |
| Operator           | _fill in_ |

---

## Checklist

### 1. Server reachable
**Script:** `tests/manual/smoke_socket.py`

Connect to `:6555`; `get` returns `framerate`, `screenresw/h`, `trackerstate`.

**Pass criteria:** values returned, `trackerstate == 0`.

**Command:**
```
"C:\Program Files\PsychoPy\python.exe" tests/manual/smoke_socket.py
```

**Result:** _PASS / FAIL_

**Evidence:** `tests/manual/_captured_frame.json` (uncalibrated, state 8).

---

### 2. Stream
**Script:** (covered by `smoke_socket.py` above)

Push enabled; ≥ 100 frames received. Pass: rate ≈ 30 Hz, plausible gaze pixels, sane `state`.

**Result:** _PASS / FAIL_

**Evidence:** console output from `smoke_socket.py` (frame rate, pixel values).

---

### 3. Heartbeat endurance
Stream 60 s with heartbeats. Pass: no disconnect.

This is verified implicitly when the 60-second integration test
(`tests/integration/test_client_against_mock.py::test_heartbeat_keeps_link_alive_30s`)
passes in CI. For the real device, leave `smoke_socket.py` running for 60 s (increase `N`
to ≥ 1800 frames) or use `stream_demo.py` and observe no disconnect.

**Result:** _PASS / FAIL_

**Evidence:** _describe observation_.

---

### 4. Plugin stream (10a)
**Script:** `tests/manual/stream_demo.py`

Gaze dot tracks the eyes in the PsychoPy window.

**Command:**
```
"C:\Program Files\PsychoPy\python.exe" tests/manual/stream_demo.py --real
```

**Pass criteria:** white dot visibly follows gaze direction; no crash or disconnect.

**Result:** _PASS / FAIL_

**Evidence:** screenshot or screen recording (path: _fill in_).

---

### 5. Calibration (10b)
**Script:** `tests/manual/calibration_demo.py`

Full 9-point `runSetupProcedure` on the device. Pass: completes, accuracy reported, redo works.

**Command:**
```
"C:\Program Files\PsychoPy\python.exe" tests/manual/calibration_demo.py --real
```

**Pass criteria:** calibration completes; accuracy summary shows overall `deg` value;
redo path (R key) restarts cleanly; accept saves `calibration_result.json`.

**Result:** _PASS / FAIL_

**Evidence:**
- `calibration_result.json` (saved by script): _path_
- Screenshot of accuracy summary screen: _path_
- Calibration overall accuracy: _fill in_ °

---

### 6. Accuracy / precision / timing (10c)
**Script:** `tests/manual/validation_experiment.py`

Present 9 known on-screen targets, record gaze, compute metrics.

**Command (run after calibration_demo.py succeeds):**
```
"C:\Program Files\PsychoPy\python.exe" tests/manual/validation_experiment.py --real ^
    --screen-w-cm 53.1 --screen-h-cm 29.9 --dist-cm 60 ^
    --capture-frame
```
Adjust `--screen-w-cm`, `--screen-h-cm`, and `--dist-cm` for your setup.

**Pass criteria:** all metrics recorded; accuracy ≈ 0.5–1° (ET-class typical).

**Result:** _PASS / FAIL_

**Metrics:**

| Metric                    | Value |
|---------------------------|-------|
| Accuracy (mean offset, °) | _fill in_ |
| Precision (RMS, °)        | _fill in_ |
| Timing median (ms)        | _fill in_ |
| Timing mean (ms)          | _fill in_ |
| n targets                 | 9 |

**Evidence:**
- `validation_results.json`: _path_
- `tests/manual/_captured_frame_calibrated.json` (if `--capture-frame` used): _path_

---

## Calibrated golden frame reconciliation

After running step 6 with `--capture-frame`:

1. Compare `tests/manual/_captured_frame_calibrated.json` with the schema in
   `docs/DEVELOPMENT_PLAN.md` §3 and the current `tests/manual/_captured_frame.json`.
2. If the field names, types, or structure differ, apply the discrepancy procedure
   (`docs/DEVELOPMENT_PLAN.md` §2):
   - Update the affected fields in `psychopy_eyetracker_eyetribe/eyetribe/frames.py`.
   - Record the correction in `docs/REFERENCES.md`.
   - Update `tests/unit/test_frames.py` (fixture + assertions).
   - Keep mock-based CI green.
3. Overwrite `tests/manual/_captured_frame.json` with the calibrated frame
   (so the golden fixture reflects real calibrated data).

**Reconciliation status:** _None — Phase 10 not yet run on hardware._

## Results

_None yet — populated after Phase 10 hardware run._
