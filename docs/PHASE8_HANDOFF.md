# Phase 8 handoff — SUPERSEDED (Phase 8 is complete)

**Phase 8 is done.** Its scope is now **"Validation tooling & hardware smoke"**: the manual scripts
(`tests/manual/stream_demo.py`, `calibration_demo.py`, `validation_experiment.py`), the PsychoPy-free
metrics helper (`psychopy_eyetracker_eyetribe/eyetribe/validation.py` + `tests/unit/test_validation.py`),
the `tests/manual/smoke_socket.py` hardware smoke (run 2026-06-15, PASS; `_captured_frame.json` saved),
and `docs/hardware_validation.md`. All merged and mock-verified — see the **Phase 8** section of
`docs/DEVELOPMENT_PLAN.md` and `docs/REPORT.md`.

There is no remaining agent task for Phase 8. The work that previously lived in "Phase 8" has been split:

- **Phase 9 — ioHub integration fixes & hardening** → `docs/PHASE9_HANDOFF.md`
  (coordinate-units fix, validity guard, reconnect hygiene, permanent `launchHubServer` regression test,
  doc reconciliation; code-first then human-in-the-loop verification).
- **Phase 11 — Hardware validation & release** → `docs/PHASE11_HANDOFF.md`
  (run this Phase 8 tooling on the real ET1000 *after* the Phase 9 fixes, record metrics, capture a
  calibrated golden frame, reconcile, tag `v1.0.0`).
