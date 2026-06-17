# Backlog — minor polish & cleanup

Small, non-blocking items deferred for batch cleanup. None affect correctness or
behaviour today; they are code-cleanliness / consistency improvements. The plan is
to clear this list in a single **Phase 12 — Backlog cleanup** pass before tagging
`v1.0.0`.

Severity legend: **cosmetic** (naming/docs), **minor** (cleanliness, no behaviour
change), **nice-to-have** (optional hardening).

---

## Open

### B1 — Reconnect test name is misleading  · cosmetic
`tests/integration/test_client_against_mock.py::test_stopping_heartbeats_causes_disconnect_and_reconnect`
no longer stops heartbeats — Phase 10 rewrote it to drop the client **server-side**
via `MockEyeTribeServer.drop_clients()`. Rename to reflect what it does, e.g.
`test_server_drop_triggers_reconnect_without_duplicate_threads`, and update the two
references: `CHANGELOG.md` (`[Unreleased]`) and `docs/REPORT.md` (Phase 10 section).
_Found: Phase 10 review._

### B2 — `drop_clients` reaches into a private attribute  · minor
`MockEyeTribeServer.drop_clients()` closes each handler via `handler._conn` directly.
Cleaner: add a public `close()`/`disconnect()` method on `_ClientHandler` and call
that. Test/mock-only code, so low impact.
_Found: Phase 10 review._

### B3 — Broad `except Exception` in `eyetracker.py`  · nice-to-have
`setConnectionState` (~line 78) and `_fetch_screen_resolution` (~line 95) catch
`Exception` broadly. They **do log** (so not silent swallows like the coordinate
methods Phase 10 fixed), but for consistency consider narrowing to the expected
network/parse exceptions (`OSError`, `socket.timeout`, JSON/`ValueError`, etc.).
_Found: Phase 10 review._

### B4 — Stale "PENDING" marker in `docs/REPORT.md`  · cosmetic
The historical Phase 1 acceptance list (~line 69) still marks the reconnect test
"PENDING" although it now exists and passes. `REPORT.md` is an append-only log, so
this is just a historical artifact — optionally add a one-line "resolved (Phase 1 /
hardened Phase 10)" note for clarity.
_Found: Phase 10 review._

### B5 — Builder demo experiment  · nice-to-have

A PsychoPy Builder (`.psyexp`) example that demonstrates the full plugin workflow in one
file: 9-point calibration → freeview panel with live gaze dot → 9-point validation →
heatmap overlay of gaze clusters vs target positions.

Implementation notes:
- Read an existing `.psyexp` from the installed PsychoPy (`C:\Program Files\PsychoPy\`)
  to get the exact 2026.1.3 XML schema before generating.
- Routines: `welcome`, `calibration`, `freeview`, `validation_intro`,
  `validation_trial` (looped over `validation_conditions.xlsx`), `heatmap`.
- Visual stimuli (gaze dot, target circles, heatmap blobs) via Builder Polygon components
  or Code Components using `psychopy.visual`; no matplotlib dependency.
- Calibration via `eyetracker.calibrate(win)` (Builder's eyetracking integration calls
  `runSetupProcedure` automatically).
- Save to `examples/eyetribe_demo.psyexp` + `examples/validation_conditions.xlsx`.
_Found: Phase 11 / hardware validation session._

---

## Done

_(move items here as Phase 12 clears them, with the resolving commit/PR)_
