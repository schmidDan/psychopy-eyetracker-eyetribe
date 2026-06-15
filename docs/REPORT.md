# REPORT — progress log

Append-only; one section per phase (see DEVELOPMENT_PLAN.md section 6).

## Phase 0 — Repository scaffold & fact verification  (status: IN PROGRESS)
- Date: 2026-06-15
- Delivered:
  - Repo structure per section 5: packaging (`pyproject.toml` with both entry-point groups),
    `MANIFEST.in`, `LICENSE` (GPL-3.0), `README`, `CHANGELOG`, `CONTRIBUTING`, `.gitignore`,
    `.pre-commit-config.yaml`, CI + release workflows (Windows).
  - PsychoPy-free core stubs (`eyetribe_client`, `frames`, `transforms`, `time_sync`, `calibration`)
    that import without PsychoPy; lazy `EyeTracker` export (PEP 562) in `eyetribe/__init__.py`;
    `EyeTracker` and `EyeTribeEyetrackerBackend` stubs so both entry points resolve; valid device YAML;
    `MockEyeTribeServer` stub.
  - Tests: core import tests, entry-point registration + YAML-parse tests (PsychoPy-free), and
    PsychoPy-gated discovery/loader test; pre-Phase-0 hardware smoke script (`tests/manual/smoke_socket.py`).
  - `docs/REFERENCES.md` skeleton with CONFIRMED vs TO-CONFIRM items.
- Acceptance criteria status:
  - PASS (sandbox): ruff/black/isort clean; PsychoPy-free tests green; entry points + YAML verified.
  - PENDING (Windows + PsychoPy 2026.1.3): `pip install -e .[dev]`; full CI green; namespace
    `psychopy.iohub.devices.eyetracker.hw.eyetribe` resolves; ioHub loader test; complete REFERENCES.md.
- TO-CONFIRM handed forward: items marked [TO CONFIRM ON MACHINE] in `docs/REFERENCES.md`.
