# Contributing

This project is built in phases; see `docs/DEVELOPMENT_PLAN.md` (the authoritative plan) and
`docs/REPORT.md` (progress log).

## Workflow

- One branch + PR per phase: `phase-N-short-name`, PR title `Phase N: <title>`.
- The PR description restates the phase acceptance criteria as a ticked checklist with evidence
  (test output, coverage %, screenshots for `[HARDWARE]` steps). Squash-merge.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`/`fix:`/`test:`/`docs:`/`chore:`/`refactor:`).
- A phase is **done** only when its acceptance criteria are met, CI is green, and `docs/REPORT.md`
  is updated.

## Environment

- Windows 10/11, PsychoPy 2026.1.3 Standalone (Python 3.10.11), or a Python 3.10 venv with
  `pip install -e .[dev]`.

## Local checks

```bash
ruff check .
black --check .
isort --check-only .
pytest -m "not hardware" -q
```

The PsychoPy-free core (`eyetribe_client`, `frames`, `transforms`, `time_sync`, `calibration`) must
import and unit-test without PsychoPy installed. `mypy` (strict, core only) and the >=90% core
coverage gate are enabled from Phase 1.
