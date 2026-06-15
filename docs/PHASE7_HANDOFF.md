# Phase 7 handoff prompt

Copy the fenced block below to brief the Phase 7 coding agent.

**Prerequisite:** Phases 1–6 merged. **Environment:** PsychoPy available for running the bundled demo;
the Coder demo runs against the **mock** (no hardware).

---

````
You are implementing **Phase 7 — Documentation & examples** of `psychopy-eyetracker-eyetribe`. Phases
0–6 are merged: an installable, Builder-visible plugin with calibration. Make it usable by a researcher
who is not the author.

## Read first (authoritative)
- `docs/DEVELOPMENT_PLAN.md` — §6 and the **Phase 7** section; skim §0/§3 for the user-facing facts.
- `docs/REFERENCES.md` — for accurate user notes (30 Hz; pupil size arbitrary units; raw default;
  Windows-only; Eye Tribe Server install source: `github.com/EyeTribe/sdk-installers` releases).
- Existing `README.md` (expand it), `docs/` (mirror sibling plugins' implementation-notes style),
  `tests/manual/*` and `tests/conftest.py` (the mock) for the demo wiring.

## Scope — docs + runnable examples
- Expand `README.md`: prerequisites (incl. where to get the Eye Tribe Server), install, quick start, and
  the limitations (30/60 Hz sampling, pupil arbitrary units, raw vs avg, Windows-only).
- A **Coder example** experiment using `eyetracker.hw.eyetribe.EyeTracker` that runs end-to-end against
  the **mock** (so a new user can try it with no hardware), and a **Builder** example `.psyexp`.
- An implementation-notes doc mirroring sibling plugins (device config keys, events, calibration).
- Troubleshooting: Server not running, port conflict, heartbeat drop, `trackerstate != 0`.
- Ensure all public API has docstrings.

## Do NOT touch
- Functional code/behaviour. This phase is docs + examples only (plus tiny docstring additions). Don't
  change pinned decisions.

## Acceptance criteria (from the plan)
- A new user can follow the README to run the bundled Coder demo **against the mock** end-to-end.
- All public API has docstrings; the Coder demo runs against the mock in CI.
- CI: doc-link check + the example script executed against the mock.

## Conventions (§6)
- `ruff`/`black`/`isort`/`mypy` still clean; existing tests still green.
- Branch `phase-7-docs`; Conventional Commits; PR `Phase 7: Documentation & examples` with the
  acceptance checklist + evidence; append a Phase 7 section to `docs/REPORT.md`. Update `CHANGELOG.md`.

## Dev/test commands
```
pip install -e .[dev]
ruff check . && black --check . && isort --check-only . && mypy && pytest -m "not hardware" -q
```
````
