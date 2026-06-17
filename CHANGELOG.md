# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/); the project uses
[Semantic Versioning](https://semver.org/). `CHANGELOG.md` is updated for every release tag.

## [Unreleased]

_(nothing yet)_

---

## [1.0.0] — 2026-06-17

### Added
- **Builder demo (Phase 12 / B5):** `examples/eyetribe_demo.psyexp` — full Builder
  experiment (welcome → 9-pt calibration → freeview → 9-target validation → gaze
  heatmap overlay) with companion `examples/validation_conditions.xlsx`.

### Fixed
- **Reconnect test (Phase 10):** Rewrote
  `test_server_drop_triggers_reconnect_without_duplicate_threads` to trigger
  reconnect via a server-side socket drop (`MockEyeTribeServer.drop_clients()`)
  instead of manually setting `client._stop_evt`, so the real EOF→reconnect path
  is actually exercised.  Test now asserts state `CONNECTED` after reconnect and
  stable `EyeTribe*` thread count (Phase 9 reconnect-hygiene guarantee).
- **`(0,0)` no-gaze sentinel (Phase 10):** `EyeTracker._process_frame` now
  treats combined gaze of exactly `(0, 0)` as invalid (`status = 2`), preventing
  the Eye Tribe's "no gaze this frame" sentinel from appearing as valid gaze data
  at the screen origin.
- **Coordinate-method exception narrowing (Phase 10):** `_eyeTrackerToDisplayCoords`
  and `_displayToEyeTrackerCoords` now catch only `(AttributeError, TypeError)`
  instead of a bare `except Exception`, so genuine errors in
  `_pixel2DisplayCoord` / `display2PIxelCoord` surface rather than silently
  falling back to raw pixels.
- **`setConnectionState` / `_fetch_screen_resolution` exception narrowing (Phase 12 / B3):**
  Both methods now catch specific network/parse exceptions (`OSError`, `ValueError`)
  instead of a broad `except Exception`.

### Changed
- **Coverage gate broadened (Phase 10):** CI now measures the full PsychoPy-free
  core (`eyetribe_client`, `frames`, `time_sync`, `calibration`, `validation`,
  `mock_server`) at ≥ 90%; was previously only `eyetribe_client` + `mock_server`.

### Removed
- **Stale `pyproject.toml` comment (Phase 10):** Removed the obsolete
  "ENABLED FROM PHASE 1 … not run in Phase 0 CI" comment above `[tool.mypy]`.

### Fixed
- **Coordinate units (Phase 9):** `EyeTracker._eyeTrackerToDisplayCoords` /
  `_displayToEyeTrackerCoords` now delegate to the ioHub Display device
  (`_pixel2DisplayCoord` / `display2PIxelCoord`) instead of the defunct `getBounds()`
  path.  Gaze positions in real experiments are now reported in the experiment's display
  unit (`pix`, `norm`, `height`, `deg`) rather than raw top-left pixels.
- **Validity guard (Phase 9):** `_process_frame` sets `status = 0` only when the Eye
  Tribe frame is state-valid **and** the combined gaze is within the screen bounds
  (`0 ≤ x ≤ screen_w`, `0 ≤ y ≤ screen_h`); uncalibrated or out-of-range gaze yields
  `status = 2`, matching the REFERENCES.md validity rule.
- **Reconnect hygiene (Phase 9):** `EyeTribeClient._reconnect_bg` now stops and joins
  the previous reader and heartbeat threads before starting new ones in `_connect_once`,
  eliminating the potential for duplicate background threads after a server-EOF reconnect.

### Removed
- **`transforms.py` (Phase 9):** deleted; coordinate conversion is now handled entirely
  by the ioHub Display device.  `tests/unit/test_transforms.py` removed accordingly.

### Added
- **Phase 7 documentation & examples**: expanded `README.md` with prerequisites
  (Eye Tribe Server install source), install instructions, Coder and Builder quick
  starts, limitations table, and troubleshooting section. Added
  `examples/coder_demo.py` (runs end-to-end against the bundled mock — no hardware
  required), `examples/builder_example.psyexp` (ready-to-open Builder template with
  Eye Tribe configured), and `docs/implementation_notes.md` (device config keys,
  event field table, coordinate system, calibration protocol, known limitations).
  All public API now has docstrings. CI extended with a coder-demo step (runs the
  demo against the mock) and a doc-link check.
- **Phase 6 packaging & Builder backend**: fleshed out `EyeTribeEyetrackerBackend` with `key`,
  `getParams()` (host, port, gaze source, calibration target count), and `writeDeviceCode()` so the
  Eye Tribe device appears in the PsychoPy Builder Eyetracker component dropdown. Added a CI
  `wheel-smoke` job that builds the wheel, installs it into a clean environment (no source tree), and
  asserts entry points, YAML, and settings backend attributes resolve correctly.
- **Phase 0 scaffold**: repository structure, packaging & discovery configuration (`pyproject.toml`
  entry points), Windows CI skeleton, PsychoPy-free core module stubs, ioHub device YAML, mock-server
  stub, and the documentation skeleton. See `docs/DEVELOPMENT_PLAN.md`.
