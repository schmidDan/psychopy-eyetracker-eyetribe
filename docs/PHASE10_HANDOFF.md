# Phase 10 handoff prompt

Copy the fenced block below to brief the Phase 10 coding agent.

**Prerequisite:** Phase 9 merged. **Environment:** Python 3.10 (+ PsychoPy for the PsychoPy-gated tests,
which CI installs). All work is software + CI — no ET1000, no hardware.

---

````
You are implementing **Phase 10 — Post-review fixes & hardening** of `psychopy-eyetracker-eyetribe`.
Phases 0–9 are merged. A pre-Phase-11 codebase review found a small set of issues; fix them **in the
order below**. Everything is PsychoPy-free or CI-only — no ET1000, no hardware.

## Read first
- `docs/DEVELOPMENT_PLAN.md` — the **Phase 10** section (authoritative) and §6 (CI / coverage conventions).
- `docs/REPORT.md` — the **Phase 10** entry (the review findings).
- Files you'll touch: `tests/integration/test_client_against_mock.py`,
  `psychopy_eyetracker_eyetribe/mock/mock_server.py`, `psychopy_eyetracker_eyetribe/eyetribe/eyetracker.py`,
  `pyproject.toml`, `.github/workflows/ci.yml`, `README.md`, `docs/implementation_notes.md`.

## Do these IN ORDER

1. **Fix the false-confidence reconnect test.**
   `tests/integration/test_client_against_mock.py::test_stopping_heartbeats_causes_disconnect_and_reconnect`
   sets `client._stop_evt` manually — which suppresses `_on_server_eof` (the reader only calls it when
   `_stop_evt` is NOT set), so the reconnect path never runs and the final assertion is trivially true.
   Rewrite it so the **server** drops the client *without* touching `client._stop_evt`: add a small public
   helper to `MockEyeTribeServer` (e.g. `drop_clients()`) that closes its connected `_ClientHandler`(s)
   while the listening socket stays up; call it, then assert (a) the client detects EOF and reconnects
   (`client.state == STATE_CONNECTED`) against the still-listening mock, and (b) no duplicate threads
   remain (snapshot `threading.enumerate()` names before/after; the count of `EyeTribe*` threads is
   stable — this is the Phase 9 reconnect-hygiene guarantee). PsychoPy-free → runs in CI as `integration`.

2. **Broaden the coverage gate to the full PsychoPy-free core.**
   In `.github/workflows/ci.yml`, change the pytest coverage step to measure every PsychoPy-free core
   module (one `--cov=` each), keeping `--cov-fail-under=90`:
   `eyetribe_client`, `frames`, `time_sync`, `calibration`, `validation` (under
   `psychopy_eyetracker_eyetribe.eyetribe.…`), and `mock_server` (under `…mock.mock_server`).
   Do **NOT** add `eyetracker.py` or `settings.py` — they are PsychoPy-coupled and their window / Builder
   code can't run headless, so including them would push coverage down for non-reasons. Run pytest with
   that coverage; if any listed module is < 90%, add focused unit tests until the whole set is ≥ 90%
   (likely gaps: `calibration` sequencer methods, `eyetribe_client` error/reconnect branches — step 1
   already helps the latter). A temporary red CI is acceptable; finish green. Update `DEVELOPMENT_PLAN.md`
   §6 so its coverage description matches the broadened gate.

3. **`(0,0)` no-gaze validity exclusion.**
   The Eye Tribe reports `raw/avg = (0,0)` as a "no gaze this frame" sentinel even on `state == 7` frames
   (confirmed in the smoke capture). Currently `(0,0)` passes the in-bounds check and is marked valid. In
   `EyeTracker._process_frame` (`eyetracker.py`), make a combined gaze of exactly `(0,0)` invalid:
   `status = 0 if (frame.is_gaze_valid() and in_bounds and not (combined.x == 0.0 and combined.y == 0.0))
   else 2`. Do not update `_latest_gaze_position` for invalid samples. Add a test (extend
   `tests/integration/test_eyetracker_against_mock.py`) using the mock with a fixed `(0,0)` gaze model
   → assert emitted samples have `status == 2`.

4. **Narrow the coordinate-method exception handling.**
   In `eyetracker.py`, `_eyeTrackerToDisplayCoords` / `_displayToEyeTrackerCoords` use a bare
   `except Exception` that silently falls back to raw pixels. Narrow to `except (AttributeError,
   TypeError)` with a one-time `log.debug(...)` on fallback, so a genuine `_pixel2DisplayCoord` error
   surfaces instead of silently emitting raw pixels. Keep the no-display passthrough and the existing
   `tests/unit/test_eyetracker_coords.py` passing (its no-display case sets `_display_device = None` →
   `AttributeError`, still caught).

5. **Remove the stale `pyproject.toml` comment** above `[tool.mypy]`
   ("Strict type-checking … ENABLED FROM PHASE 1 … not run in Phase 0 CI") — obsolete.

6. **Documentation.**
   - Document the `(0,0)` / no-gaze behaviour **prominently in `README.md`** (Limitations): the plugin
     drops the Eye Tribe's `(0,0)` "no-gaze" sentinel as invalid (`status = 2`), so analysis never sees
     phantom samples at the screen origin.
   - Add the same note to `docs/implementation_notes.md`.

## Acceptance criteria
- Reconnect test triggers the real EOF→reconnect path and asserts reconnection + stable thread count;
  green in CI.
- Coverage gate measures the full PsychoPy-free core (`eyetribe_client`, `frames`, `time_sync`,
  `calibration`, `validation`, `mock_server`) at ≥ 90%, green on `windows-latest`.
- `(0,0)` combined gaze → `status = 2` (asserted); README + implementation notes document it.
- Coordinate methods catch only `(AttributeError, TypeError)` (+ debug log); stale `pyproject` comment gone.
- `ruff`/`black`/`isort`/`mypy` clean; full CI suite (`-m "not hardware and not iohub"`) green; the
  host-only `iohub` launchHubServer test is unaffected.

## Conventions (§6)
- Branch `phase-10-fixes`; Conventional Commits; PR `Phase 10: Post-review fixes & hardening` with the
  acceptance criteria as a ticked checklist + evidence (test output, coverage %); append a Phase 10
  section to `docs/REPORT.md`; update `CHANGELOG.md`.

## Dev/test commands
```
pip install -e .[dev]
ruff check . && black --check . && isort --check-only . && mypy && pytest -m "not hardware and not iohub" -q
```
````
