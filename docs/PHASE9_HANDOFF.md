# Phase 9 handoff prompt

Copy the fenced block below to brief the Phase 9 coding agent.

**Prerequisite:** Phases 1–8 merged. **Environment:** Part A (code/tests) needs only Python 3.10;
Part B (human-in-the-loop verification) needs PsychoPy 2026.1.3 + a display.

---

````
You are implementing **Phase 9 — ioHub integration fixes & hardening** of
`psychopy-eyetracker-eyetribe`. Phases 0–8 are merged. A pre-handoff code review found a small set of
issues, almost all on the real `launchHubServer` path that the existing tests don't exercise (they read
`tracker._native_event_buffer` directly). Do the coding/tests first (Part A), then the human runs the
on-machine verification (Part B).

## Read first (authoritative)
- `docs/DEVELOPMENT_PLAN.md` — §3 (wire format), §4 (architecture), §6 (conventions), and the
  **Phase 9** section.
- `docs/REFERENCES.md` — confirmed ioHub facts; note the `BinocularEyeSampleEvent` field mapping and the
  validity note ("calibrated + in-bounds, not the `STATE_TRACKING_GAZE` bit alone").
- `docs/REPORT.md` — the Phase 3/4/6 entries (the coordinate fallback, the `_is_reporting_events`
  decision, and the post-Phase-7 launchHubServer fixes incl. the `.pth` step).
- The base ioHub source on the machine:
  `C:\Program Files\PsychoPy\Lib\site-packages\psychopy\iohub\devices\eyetracker\__init__.py` — read
  `_eyeTrackerToDisplayCoords` (base default uses `self._display_device._pixel2DisplayCoord(gaze_x,
  gaze_y, self._display_device.getIndex())`) and the MouseGaze device for reference.
- Files you will touch: `psychopy_eyetracker_eyetribe/eyetribe/eyetracker.py`,
  `psychopy_eyetracker_eyetribe/eyetribe/eyetribe_client.py`, and tests under `tests/`.

## What already works — do NOT "re-fix"
- Discovery + the event pipeline are verified: a prior `launchHubServer` run recorded 32 events. The
  entry-point group is `psychopy.iohub.devices.eyetracker.hw`; `eyetribe/__init__.py` exports the event
  classes; `setRecordingState` setting `_is_reporting_events` directly is a deliberate, working choice
  (the base `enableEventReporting` calls into `_iohub_server`, which is absent in the test harness).
  Leave these as-is.

## Part A — code & tests (no hardware)
1. **Coordinate units (primary).** `EyeTracker._eyeTrackerToDisplayCoords` /
   `_displayToEyeTrackerCoords` currently call `self._display_device.getBounds()` — **not a real ioHub
   Display method**. It raises, the silent `except` returns raw top-left pixels, so a real experiment
   gets gaze in pixels (Y-down), not the window's units. Replace the body with the base pattern:
   `self._display_device._pixel2DisplayCoord(gaze_x, gaze_y, self._display_device.getIndex())` for the
   forward map and `self._display_device.display2PixelCoord(...)` (confirm the exact method name in the
   installed base — the base source spells it `display2PIxelCoord`) for the inverse. Keep a pixel
   pass-through **only** as the no-display test fallback. Remove `_get_display_bounds` and the
   `transforms.py` dependency from the device path. **Delete `transforms.py` and
   `tests/unit/test_transforms.py`**, drop them from the `[tool.mypy]` files list + the coverage scope,
   and update the doc references (§5 repo tree, Principle 4, the §4 architecture footnote, and
   `docs/coordinate_systems.md` §1.6). Add a **CI-runnable** test that injects a stub `_display_device`
   (`_pixel2DisplayCoord`/`getIndex`) and asserts `_eyeTrackerToDisplayCoords` delegates correctly — so
   the coordinate fix is regression-guarded in CI even though the full `launchHubServer` test is
   host-only.
2. **Validity guard.** In `_process_frame`, set `status = 0` only when the sample is state-valid
   (`frame.is_gaze_valid()`) **and** the combined gaze is in-bounds (`0 ≤ x ≤ screen_w`,
   `0 ≤ y ≤ screen_h`); otherwise `status = 2`. Don't set `_latest_gaze_position` for invalid samples.
3. **Reconnect hygiene.** In `eyetribe_client.py`, a server-EOF reconnect (`_on_server_eof` →
   `_reconnect_bg` → `_connect_once`) can leave the previous heartbeat thread running and re-clear the
   shared `_stop_evt`. Make reconnect stop/join the old reader + heartbeat before starting new ones.
4. **Permanent launchHubServer regression test — host-run, NOT in the CI gate.** Add
   `tests/integration/test_launchhub_against_mock.py` under a **dedicated marker `@pytest.mark.iohub`**
   (plus `pytest.importorskip("psychopy")`): start `MockEyeTribeServer`, call `launchHubServer` with
   `{'eyetracker.hw.eyetribe.EyeTracker': {...}}`, record ≥ 1 s, then assert
   `io.devices.tracker.getEvents()` is non-empty **and** `io.devices.tracker.getPosition()` is inside the
   active Display's bounds (this catches the coordinate bug). It spawns a **real ioHub subprocess +
   display**, which the GitHub runner can't do reliably — so **exclude it from CI**: register the `iohub`
   marker in `pyproject.toml` and change the CI pytest step to `-m "not hardware and not iohub"`. The
   test is run **locally on the Windows host** (with the `.pth` step) as the first action of Part B. Do
   NOT mark it `integration` (the existing `integration` tests drive the device directly, no subprocess,
   and must keep running headless in CI). Also correct the now-misleading `integration` marker
   description in `pyproject.toml` (those tests drive the device directly; they do not launch a server).
5. **Doc reconciliation.** Ensure `DEVELOPMENT_PLAN.md` §5.1 and `REFERENCES.md` state the entry-point
   group `psychopy.iohub.devices.eyetracker.hw`. Add the ioHub-subprocess `.pth` developer step to
   `docs/HUMAN_TASKS.md` (so the editable install is visible to the server subprocess; not needed for a
   wheel install).
6. **Verify the Builder path.** Diff `settings.py` `getParams` / `writeDeviceCode` against the in-tree
   `MouseGazeEyetrackerBackend` (`…/psychopy/experiment/components/settings/eyetracking.py`); fix any
   signature/format mismatch so Builder code-gen is valid.

## Part B — human-in-the-loop verification (Windows + PsychoPy, second half of the phase)
- Run `pytest -m iohub -q` on the host; confirm `test_launchhub_against_mock` passes.
- Run a minimal real experiment (or the README `launchHubServer` snippet) and confirm
  `tracker.getPosition()` is in the window's units (e.g. centred for `pix`), not raw `0–1920`.
- Record both outcomes in the `docs/REPORT.md` Phase 9 section.

## Acceptance criteria
- Coordinate conversion goes through the Display device. A **CI-runnable** test (stub `_display_device`
  with `_pixel2DisplayCoord`/`getIndex`) asserts the delegation + a known device pixel mapping inside the
  Display bounds — guarding the fix in CI without the ioHub subprocess.
- Out-of-bounds / uncalibrated gaze → `status = 2`.
- No duplicate client threads after a reconnect (asserted).
- `test_launchhub_against_mock` (marker `iohub`) passes **on the Windows host** (`getEvents()` non-empty;
  `getPosition()` in bounds) — recorded in `REPORT.md`; it is **not** part of the CI gate.
- Entry-point group + `.pth` step documented; `ruff`/`black`/`isort`/`mypy` clean; the **CI suite**
  (`-m "not hardware and not iohub"`) is green on `windows-latest`.
- Human-in-the-loop verification recorded in `REPORT.md`.

## Conventions (§6)
- `eyetracker.py`/`settings.py` are PsychoPy-coupled (excluded from strict mypy); the PsychoPy-free core
  stays strict-clean. Branch `phase-9-integration-fixes`; Conventional Commits; PR
  `Phase 9: ioHub integration fixes & hardening` with the acceptance checklist + evidence; append a
  Phase 9 section to `docs/REPORT.md`; update `CHANGELOG.md`.

## Dev/test commands
```
pip install -e .[dev]
ruff check . && black --check . && isort --check-only . && mypy && pytest -m "not hardware and not iohub" -q
# on the Windows host only (spawns the ioHub subprocess): pytest -m iohub -q
```
````
