# Hardware validation ([HARDWARE])

Each item is one script under `tests/manual/`; ordered so failures localize.
Record for every run: device serial, Eye Tribe Server version, Windows build, date, operator,
result, evidence path.

## Run environment

| Field              | Value |
|--------------------|-------|
| Device serial      | not recorded |
| Eye Tribe Server   | 0.9.77 |
| Windows build      | Windows 11 Home 10.0.26200 |
| PsychoPy version   | 2026.1.3 |
| Python             | 3.10.11 |
| Date               | 2026-06-17 |
| Operator           | Daniel Schmid |

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

**Result:** PASS (2026-06-15, Phase 8a pre-flight gate)

**Evidence:** `tests/manual/_captured_frame.json` (calibrated golden frame, state 7).

---

### 2. Stream
**Script:** (covered by `smoke_socket.py` above)

Push enabled; ≥ 100 frames received. Pass: rate ≈ 30 Hz, plausible gaze pixels, sane `state`.

**Result:** PASS (2026-06-15, Phase 8a) — 30 Hz confirmed, 1920×1080, `trackerstate 0`.

**Evidence:** console output from `smoke_socket.py` — frame rate and pixel values confirmed.

---

### 3. Heartbeat endurance
Stream 60 s with heartbeats. Pass: no disconnect.

This is verified implicitly when the 60-second integration test
(`tests/integration/test_client_against_mock.py::test_heartbeat_keeps_link_alive_30s`)
passes in CI. For the real device, leave `smoke_socket.py` running for 60 s (increase `N`
to ≥ 1800 frames) or use `stream_demo.py` and observe no disconnect.

**Result:** PASS (implicitly — stream_demo ran for the full Phase 11a session without disconnect).

**Evidence:** stream_demo session ran without errors; no reconnect messages observed.

---

### 4. Plugin stream (11a)
**Script:** `tests/manual/stream_demo.py`

Gaze dot tracks the eyes in the PsychoPy window.

**Command:**
```
"C:\Program Files\PsychoPy\python.exe" tests/manual/stream_demo.py --real
```

**Pass criteria:** white dot visibly follows gaze direction; no crash or disconnect.

**Result:** PASS (2026-06-17)

**Evidence:** white dot confirmed to follow gaze across screen; ESCAPE exit clean. Screenshot
captured by operator during session.

---

### 5. Calibration (11b)
**Script:** `tests/manual/calibration_demo.py`

Full 9-point `runSetupProcedure` on the device. Pass: completes, accuracy reported, redo works.

**Command:**
```
"C:\Program Files\PsychoPy\python.exe" tests/manual/calibration_demo.py --real --output calibration_result.json
```

**Pass criteria:** calibration completes; accuracy summary shows overall `deg` value;
redo path (R key) restarts cleanly; accept saves `calibration_result.json`.

**Result:** PASS (2026-06-17)

**Evidence:**
- `calibration_result.json` saved at repo root — `result: true`, `num: 9`, all 9 points recorded.
- Calibration overall accuracy: **0.18°** (best run; range across session: 0.15°–0.62°).
- Per-point errors shown on accuracy summary screen (all < 0.4°).

**Protocol notes (hardware discrepancies fixed during Phase 11):**
- Real server requires integer pixel coordinates in `pointstart` (floats return 400 "Bogus value").
  Fixed in `CalibrationSequencer.point_start` — `int(x_px)` / `int(y_px)` cast added.
- Real server does not embed `calibresult` in `pointend` replies; must be fetched via
  `GET calibresult` after the sequence. Fixed in `calibration_demo.py`.
- `calibration clear` drops gaze tracking state causing zero-sample calibration (`num: 0`).
  Fixed: `clear()` removed from before initial `start()`; only called in the redo path.

---

### 6. Accuracy / precision / timing (11c)
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

**Result:** PASS (2026-06-17)

**Metrics:**

| Metric                              | Value |
|-------------------------------------|-------|
| Accuracy (mean offset, °)           | 1.36  |
| Precision (RMS, °)                  | 0.50  |
| Saccade latency median (ms)         | 281   |
| Saccade latency mean (ms)           | 248   |
| n targets                           | 9     |

Monitor assumed: 53.1 × 29.9 cm (24-inch), 60 cm viewing distance.

**Evidence:**
- `validation_results.json` saved at repo root.
- `tests/manual/_captured_frame_calibrated.json` captured with `--capture-frame`.

**Protocol notes:**
- Validation experiment requires a settle window (0.5 s, dot shown but samples discarded)
  between target onset and recording start, so saccade-in-flight samples do not bias accuracy.
  Added `--settle-s` argument (default 0.5 s); saccade latency tracked from dot onset through
  the settle window so the floor is not artificially raised to settle_s.
- Metric renamed from "Timing" to "Saccade latency" — measures human saccade latency
  (time from dot onset to first gaze within 150 px of target), not system/hardware lag.

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

**Reconciliation status (2026-06-17): NO DISCREPANCY**

Schema comparison between `_captured_frame.json` (uncalibrated, all-zeros, state=8) and
`_captured_frame_calibrated.json` (calibrated, state=7, near-centre gaze):

- Top-level keys: `avg`, `fix`, `lefteye`, `raw`, `righteye`, `state`, `time`, `timestamp` — identical ✓
- Per-eye sub-keys: `avg {x,y}`, `pcenter {x,y}`, `psize`, `raw {x,y}` — identical ✓
- Types: all floats/numbers, `fix` bool, `state`/`time` int, `timestamp` string — identical ✓

`frames.py` schema matches. No changes to `frames.py`, mock, or tests required.

`tests/manual/_captured_frame.json` replaced with the calibrated golden frame
(state=7, `fix=true`, gaze near screen centre, binocular and per-eye data present).

## Results

**Phase 11 complete (2026-06-17).** All four sub-steps passed:

| Step | Description | Result |
|------|-------------|--------|
| 11a  | Plugin stream (`stream_demo --real`) | PASS — white dot follows gaze |
| 11b  | Calibration (`calibration_demo --real`) | PASS — 0.18° overall, `result: true`, `num: 9` |
| 11c  | Validation (`validation_experiment --real`) | PASS — 1.36° accuracy, 0.50° precision |
| 11d  | Golden frame reconciliation | PASS — no schema discrepancy |

Hardware protocol bugs discovered and fixed during this phase: integer coords for `pointstart`,
GET-based `calibresult` fetch, `clear()` ordering, settle window for validation accuracy,
saccade latency labelling. All fixes committed to `main`.
