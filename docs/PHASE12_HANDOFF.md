# Phase 12 handoff prompt

Copy the fenced block below to brief the Phase 12 coding agent.

**Prerequisite:** Phase 11 hardware validation recorded in `docs/hardware_validation.md` (the device is
known-good before release). **Environment:** Python 3.10 (+ PsychoPy for the gated tests, which CI
installs). All work is software + CI — no ET1000, no hardware.

---

````
You are carrying out **Phase 12 — Backlog cleanup & release** of `psychopy-eyetracker-eyetribe`.
Phases 0–11 are done (Phase 11 validated the device on real hardware). Your job is to clear the
accumulated minor items in `docs/BACKLOG.md` in one pass and then cut the `v1.0.0` release. Everything
is PsychoPy-free or CI-only — no ET1000, no hardware.

## Read first
- `docs/BACKLOG.md` — the authoritative list of items to clear (the **Open** section).
- `docs/DEVELOPMENT_PLAN.md` — the **Phase 12** section and §6 (CI / conventions / versioning).
- `CHANGELOG.md` — the `[Unreleased]` section to finalize.

## Do these
1. **Clear the backlog.** Work through every item in the **Open** section of `docs/BACKLOG.md`. For each:
   make the change, keep `ruff`/`black`/`isort`/`mypy` and the full mock-based suite green, and move the
   item to the **Done** section with its resolving commit hash. If you judge an item not worth doing,
   do **not** delete it silently — record the decision and reasoning in the backlog instead.
   - Note for **B5** (Builder demo): before generating the `.psyexp`, read an existing
     Builder file from `C:\Program Files\PsychoPy\lib\site-packages\psychopy\demos\builder\`
     (or any `.psyexp` on the machine) to get the exact 2026.1.3 XML schema. Generate
     `examples/eyetribe_demo.psyexp` + `examples/validation_conditions.xlsx`.
   - Note for **B1** (rename the misleading reconnect test): when you rename
     `test_stopping_heartbeats_causes_disconnect_and_reconnect`, also update its two references in
     `CHANGELOG.md` and `docs/REPORT.md`.
2. **Finalize the changelog.** Move the `[Unreleased]` entries under a dated `## [1.0.0] — <date>`
   heading; leave a fresh empty `[Unreleased]` stub above it.
3. **Final pre-release gate.** `ruff check . && black --check . && isort --check-only . && mypy &&
   pytest -m "not hardware and not iohub" -q` — all green. The host-only `iohub` launchHubServer test is
   unaffected.
4. **Tag the release.** Tag **`v1.0.0`**; `.github/workflows/release.yml` builds the wheel and attaches
   it to the GitHub Release (no PyPI).

## Acceptance criteria
- `docs/BACKLOG.md` **Open** list is empty — every item either resolved (with commit) or explicitly
  deferred with a recorded reason.
- `CHANGELOG.md` has a dated `## [1.0.0]` section; `[Unreleased]` reset to empty.
- Lint / type / full mock-based test suite green on `windows-latest`.
- `v1.0.0` tagged; GitHub Release created with the attached wheel.

## Conventions (§6)
- Branch `phase-12-backlog-release`; Conventional Commits (one focused commit per backlog item is fine);
  PR `Phase 12: Backlog cleanup & release` with the backlog items as a ticked checklist + evidence
  (test output); append a Phase 12 section to `docs/REPORT.md`. Tag `v1.0.0` only after the PR is merged
  and CI is green.
````
