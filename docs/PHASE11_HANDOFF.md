# Phase 11 handoff prompt

Copy the fenced block below to brief the Phase 11 operator/agent.

**Prerequisite:** Phase 10 merged (post-review fixes & hardening; Phase 9 before it).
**Environment:** Windows + Eye Tribe Server + ET1000. This is the hardware-validation & release phase;
the validation **tooling already exists** (Phase 8) — Phase 11 *runs* it on real hardware. Mostly human
labour (see `docs/HUMAN_TASKS.md`, Phase 11); an agent's role is limited to small fixes if a script
misbehaves and to writing up results.

---

````
You are carrying out **Phase 11 — Hardware validation & release on the ET1000** of
`psychopy-eyetracker-eyetribe`. Phases 0–9 are merged. The validation scripts and the PsychoPy-free
metrics helper already exist and are mock-verified (Phase 8); your job is to run them on the real
device (after the Phase 9 + Phase 10 fixes), record the results, capture a calibrated golden frame,
reconcile any
real-frame differences, and tag the release.

## Read first
- `docs/DEVELOPMENT_PLAN.md` — the **Phase 11** section and §2 (discrepancy procedure).
- `docs/hardware_validation.md` — the checklist + results template to fill in.
- `docs/REFERENCES.md` — the `[TODO — Phase 11]` calibrated-golden-frame item and the §3 wire format.
- The tooling (already in repo): `tests/manual/stream_demo.py`, `tests/manual/calibration_demo.py`,
  `tests/manual/validation_experiment.py`, `psychopy_eyetracker_eyetribe/eyetribe/validation.py`.

## Steps (human-run on the Windows machine; record evidence for each)
- **11a** `& $py tests\manual\stream_demo.py --real` — gaze-contingent dot tracks the eyes. Save a short
  screen recording / screenshots.
- **11b** `& $py tests\manual\calibration_demo.py --real` — full 9-point calibration completes; accuracy
  reported; redo works; `calibration_result.json` saved.
- **11c** `& $py tests\manual\validation_experiment.py --real --screen-w-cm <w> --screen-h-cm <h>
  --dist-cm <d>` — record gaze to known targets; the script computes accuracy (mean offset °),
  precision (RMS), and a stimulus-onset-to-gaze timing figure. Paste the metrics table into
  `docs/hardware_validation.md`.
- **11d** Capture a **calibrated** golden frame: `… validation_experiment.py --real --capture-frame`
  (saves `tests/manual/_captured_frame_calibrated.json`). Compare it against the §3 schema; if anything
  differs, apply the §2 discrepancy procedure (update `frames.py` + the mock + `REFERENCES.md` + the
  golden fixture) and confirm the mock-based CI is still green.

## Acceptance criteria
- 11a–11c run on the ET1000; results recorded in `docs/hardware_validation.md` (device serial, Eye Tribe
  Server version, Windows build, date, operator, evidence paths).
- Accuracy / precision in the ET-class typical range (≈ 0.5–1°; record actuals); timing characterized.
- Calibrated golden frame captured; any reconciliation merged; full mock-based CI still green.
- Tag **`v1.0.0`** — CI builds the wheel and attaches it to the GitHub Release.

## Conventions (§6)
- Any code fixes are PsychoPy-free where possible and keep the suite green. Branch
  `phase-11-hardware-validation`; Conventional Commits; PR `Phase 11: Hardware validation & release`
  with the checklist + evidence; append a Phase 11 section to `docs/REPORT.md`; update `CHANGELOG.md`.
  On success, tag `v1.0.0`.

## Notes
- If `getPosition()` / gaze coordinates look wrong on hardware, that points back at the Phase 9
  coordinate fix — stop and re-verify Phase 9 rather than papering over it here.
````
