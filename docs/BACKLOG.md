# Backlog — minor polish & cleanup

Small, non-blocking items deferred for batch cleanup. None affect correctness or
behaviour today; they are code-cleanliness / consistency improvements. The plan is
to clear this list in a single **Phase 12 — Backlog cleanup** pass before tagging
`v1.0.0`.

Severity legend: **cosmetic** (naming/docs), **minor** (cleanliness, no behaviour
change), **nice-to-have** (optional hardening).

---

## Open

_(all items resolved — see Done section below)_

---

## Done

### B1 — Reconnect test name is misleading  · cosmetic
Renamed `test_stopping_heartbeats_causes_disconnect_and_reconnect` →
`test_server_drop_triggers_reconnect_without_duplicate_threads` in
`tests/integration/test_client_against_mock.py`; updated the two references in
`CHANGELOG.md` and `docs/REPORT.md`.
_Resolved: 7f4ccd0 (Phase 12)_

### B2 — `drop_clients` reaches into a private attribute  · minor
Added public `_ClientHandler.disconnect()` method (shutdown + close the socket
without setting stop_evt); `MockEyeTribeServer.drop_clients()` now calls
`handler.disconnect()` instead of `handler._conn.shutdown/close`.
_Resolved: 7f4ccd0 (Phase 12)_

### B3 — Broad `except Exception` in `eyetracker.py`  · nice-to-have
`setConnectionState` now catches only `OSError`; `_fetch_screen_resolution` catches
`(OSError, ValueError)`.  Both still log the exception, so the behaviour change is
cosmetic.
_Resolved: 7f4ccd0 (Phase 12)_

### B4 — Stale "PENDING" marker in `docs/REPORT.md`  · cosmetic
Added a resolution note to the Phase 1 acceptance list entry for the reconnect test
(now shows the renamed test and Phase 10/12 resolution).
_Resolved: 7f4ccd0 (Phase 12)_

### B5 — Builder demo experiment  · nice-to-have
Generated `examples/eyetribe_demo.psyexp` — a complete PsychoPy Builder experiment
(welcome → 9-pt calibration → freeview with live gaze dot → 9-target validation →
gaze-overlay heatmap) based on the 2026.1.3 psyexp XML schema.  Companion conditions
file `examples/validation_conditions.xlsx` provides 9 target positions (height units,
sequential order, centre-first).  No matplotlib dependency; heatmap uses
`visual.Circle` overlays via Code Components.
_Resolved: Phase 12 (this commit)_
