# Human Task Checklists

This document lists everything **you (Daniel)** need to do by hand, phase by phase. The coding agents
write the code, tests, and CI, and keep `docs/REPORT.md` updated. Your role is the work that can't be
automated from inside the repo: **environment & account setup, things that need the real Windows +
PsychoPy machine, GUI checks, hardware/eye-tracking sessions, on-machine fact confirmation, and code
review / merge.**

Boxes are `[ ]`; tick them as you go. Commands are **PowerShell** (Windows). The Eye Tribe Server runs
only on Windows, so all on-machine steps assume the Windows box with PsychoPy 2026.1.3.

> **Division of labour at a glance**
> - **Agents + GitHub CI** do: implementation, unit/integration tests against the mock, lint, type
>   checks, and the PsychoPy-free + discovery tests on the `windows-latest` runner.
> - **You** do: the setup below, anything needing a real **display** (calibration window, Builder
>   dropdown) or **hardware** (the ET1000), the `[TO CONFIRM ON MACHINE]` facts in
>   `docs/REFERENCES.md`, and reviewing/merging each phase PR.

## Conventions (set once per shell)

```powershell
$py  = "C:\Program Files\PsychoPy\python.exe"   # Standalone interpreter (Python 3.10.11)
$repo = "C:\Users\danie\Documents\Claude\Projects\Eye Tribe Psychopy Plugin"
cd $repo
```

Installing **into the Standalone** writes to `C:\Program Files\...`, which is protected — run those
specific commands in a **PowerShell started "as Administrator"**. (Everything else runs in a normal
shell.) Installing into the Standalone is the faithful target; if you prefer not to touch
`Program Files`, a 3.10 venv works for the PsychoPy-free phases but won't exercise PsychoPy discovery.

---

## Setup — before Phase 0 work begins (one-time)

- [x] **Install the Eye Tribe Server** and connect the **ET1000** (USB 3). The company is defunct, but
      the official installers are preserved on GitHub at **`EyeTribe/sdk-installers`** → *Releases*:
      <https://github.com/EyeTribe/sdk-installers/releases>. Download the Windows SDK installer
      (`TheEyeTribeSDK-0.9.77-x86.exe`, the last release, 2016) and run it — it installs both the
      **EyeTribe Server** and the **EyeTribe UI** into `C:\Program Files (x86)\EyeTribe\`. It is 32-bit
      but runs fine on 64-bit Windows. Then launch **EyeTribe Server** (it listens on TCP
      `localhost:6555` — the port this plugin connects to) and open the **EyeTribe UI** once to confirm
      it sees the tracker and shows the eye image.
- [x] PsychoPy **2026.1.3** / Python **3.10.11** installed and confirmed.
- [x] **Full GPLv3 text in `LICENSE`** — done (written directly into the repo; no action needed).
- [x] **Set the GitHub owner**: replace `<ORG>` in `pyproject.toml` (`[project.urls]`) with your
      GitHub user/org.
- [x] **Initialise git and push** — done (private repo):
      ```powershell
      git init
      git add .
      git commit -m "chore: Phase 0 scaffold"
      git branch -M main
      git remote add origin https://github.com/<ORG>/psychopy-eyetracker-eyetribe.git
      git push -u origin main
      ```
- [x] *(Deferred TODO)* On GitHub: **protect `main`** (require PR + passing CI before merge).
      **Deferred** while this is a **private, single-contributor** repo; re-enable before adding
      collaborators or going public. Until then, the per-phase PR flow is followed by convention.
- [x] **CRITICAL GATE — hardware smoke** (confirms the Server + ET1000 actually stream *before* any
      further investment; needs only a socket, no plugin/PsychoPy):
      ```powershell
      & $py "$repo\tests\manual\smoke_socket.py"
      ```
      Expect a burst of frame dicts and a saved `tests\manual\_captured_frame.json`.
      **If this fails, stop and resolve the Server/driver/hardware first** — nothing downstream works
      without a live stream. (Risk-register item #1.)

---

## Phase 0 — Repository scaffold & fact verification

The scaffold already exists and passed lint + the PsychoPy-free tests in a sandbox. Your job is to run
it **inside the real PsychoPy** and capture the machine-only facts.

- [x] **Install editable into the Standalone** — done (`pip install -e .[dev]` succeeded).
- [x] **Lint + tests on the real interpreter** — done: ruff/black/isort clean; **10 passed / 2 skipped**
      (`test_eyetracker_class_loads_under_psychopy` passed → the `EyeTrackerDevice` base path is correct;
      the 2 skips are the Phase 1/3 mock placeholders). Commands for reference:
      ```powershell
      cd $repo
      & $py -m ruff check .
      & $py -m black --check .
      & $py -m isort --check-only .
      & $py -m pytest -m "not hardware" -q
      ```
- [x] **Plugin-discovery mechanism pinned** (via `check_discovery.py`, 2026-06-15): `scanPlugins()`
      sees the plugin (returns 1); `activatePlugins()` runs. PsychoPy creates **no** importable
      `hw.eyetribe` module — by design. ioHub resolves the device from the entry point at
      `launchHubServer` time via `eyetracker.hw.eyetribe.EyeTracker`. Recorded in `docs/REFERENCES.md`;
      end-to-end load is verified in Phase 1/3 against the mock. Nothing more to do here for Phase 0.
- [x] **Capture the `[TO CONFIRM ON MACHINE]` facts** into `docs/REFERENCES.md` — done 2026-06-15
      (EyeTrackerDevice surface, `BinocularEyeSampleEvent` fields + mapping, settings base
      `EyetrackerBackend` → `settings.py` fixed). Commands used, for reference:
      ```powershell
      # EyeTrackerDevice source file + method surface
      & $py -c "import inspect, psychopy.iohub.devices.eyetracker as e; print(inspect.getsourcefile(e.EyeTrackerDevice))"
      & $py -c "import psychopy.iohub.devices.eyetracker as e; print('\n'.join(sorted(m for m in dir(e.EyeTrackerDevice) if not m.startswith('__'))))"
      # BinocularEyeSampleEvent field names (esp. pupil-size + per-eye cam fields)
      & $py -c "from psychopy.iohub.devices.eyetracker.eye_events import BinocularEyeSampleEvent as B; print(getattr(B,'CLASS_ATTRIBUTE_NAMES', dir(B)))"
      # Builder eyetracking settings backend base class
      & $py -c "import psychopy.experiment.components.settings.eyetracking as s; print(dir(s))"
      # A sibling device's YAML, to align our key set/schema tokens
      Get-ChildItem -Recurse -ErrorAction SilentlyContinue "C:\Program Files\PsychoPy" -Filter "default_eyetracker.yaml" | Select-Object FullName
      ```
- [x] **Phase 0 fact-finding closed** (2026-06-15): the in-tree MouseGaze device uses exactly
      `default_eyetracker.yaml` + `supported_config_settings.yaml` → our filenames are correct (no
      rename); and `EyeTribeEyetrackerBackend.__mro__` is `(…, EyetrackerBackend, object)` → the backend
      subclasses cleanly. All `[TO CONFIRM]` items in `docs/REFERENCES.md` are resolved.
- [ ] **Review & merge** the Phase 0 PR once CI is green and `REFERENCES.md` is complete.

---

## Phases 1–7 — what you do each time

Phases 1–7 are pure software validated against the **mock** on CI, so for most of them your only job is
**review + merge**. The exceptions below are the steps CI can't do (no display, or a human judgement).
The generic per-PR checklist is in the last section.

### Phase 1 — Transport + mock server
- [ ] Review PR; confirm CI green (the mock-based client tests now run).
- [ ] *(optional)* Locally run a quick smoke of the mock + client if you want hands-on confidence.
- No hardware, no GUI.

### Phase 2 — Frame parsing & data model
- [ ] Review PR; confirm CI green. No machine-specific work.

### Phase 3 — ioHub EyeTracker (recording & polling)
- [ ] Review PR; confirm CI green.
- [ ] Confirm the `BinocularEyeSampleEvent` field names you captured in Phase 0 were used (the field
      mapping in the PR matches `REFERENCES.md`).
- [ ] *(if CI can't launch ioHub headlessly)* run the ioHub-against-mock integration once locally:
      `& $py -m pytest tests\integration\test_eyetracker_against_mock.py -q`.

### Phase 4 — Coordinate transforms & time-sync
- [ ] Review PR; confirm CI green. Pure math — no machine-specific work.

### Phase 5 — Calibration (`runSetupProcedure`)
- [ ] Review PR; confirm CI green (sequencing tested against the mock).
- [ ] **GUI check (needs a display):** run the calibration flow against the mock on your machine and
      eyeball it — targets present in the right places, animate, the accuracy summary shows, and
      **accept / redo / keyboard-abort** all behave and restore the screen cleanly.

### Phase 6 — Packaging & Builder backend
- [ ] Review PR; confirm CI green (wheel builds, clean-env import works).
- [ ] **GUI check:** open **PsychoPy Builder**, add/inspect the **Eyetracker** component, and confirm
      **"Eye Tribe"** appears in the dropdown with its fields (host, port, gaze source, calibration
      target count). Record the result in `docs/REPORT.md`.
- [ ] *(optional)* Build the wheel and test a clean install:
      ```powershell
      & $py -m build --wheel
      & $py -m pip install --force-reinstall (Get-ChildItem dist\*.whl | Select-Object -First 1).FullName
      ```

### Phase 7 — Documentation & examples
- [ ] Review PR; confirm CI green.
- [ ] **Be the "new user":** follow the README quick-start yourself and run the bundled Coder demo
      **against the mock** end-to-end. Note anything confusing — docs bugs are best caught by a human.

---

## Phase 8 — Hardware validation on the ET1000 (the heavy human phase)

This is the phase that genuinely needs you, the tracker, and a person to look at. Run each step on the
Windows machine with the Eye Tribe Server running; record evidence in `docs/hardware_validation.md`
(device serial, Server version, Windows build, date, result, evidence path) for every run.

- [ ] **8a — raw stream** (already partly done as the setup gate): `& $py tests\manual\smoke_socket.py`.
      Commit the resulting `_captured_frame.json` as the golden fixture; hand it to the agent to feed
      `tests/unit/test_frames.py` and to reconcile against `§3` of the plan.
- [ ] **8b — plugin stream:** `& $py tests\manual\stream_demo.py`. Sit in front of the tracker; confirm
      the gaze dot follows your eyes. Capture a short screen recording / screenshots.
- [ ] **8c — calibration on hardware:** `& $py tests\manual\calibration_demo.py`. Run a full 9-point
      calibration; confirm it completes, the accuracy is reported, and **redo** works. Save the
      accuracy report + screenshots.
- [ ] **8d — validation experiment:** present known on-screen targets, record gaze, and compute
      spatial accuracy (mean offset, °), precision (RMS), and a stimulus-onset-to-gaze timing figure.
      Write the numbers into `docs/hardware_validation.md`.
- [ ] **Reconcile:** if any real-frame detail differs from the plan's `§3`, hand the findings to the
      agent to update `frames.py` + the mock + `REFERENCES.md` + golden fixtures, and confirm the
      mock-based CI still passes (plan §2 discrepancy procedure).
- [ ] Once 8a–8d pass and are recorded: tag the **`1.0.0`** release (CI builds + attaches the wheel to
      the GitHub Release).

---

## Recurring — every phase PR

- [ ] Read the PR: code, tests, and the acceptance-criteria checklist with evidence.
- [ ] Confirm **CI is green** on `windows-latest`.
- [ ] Confirm `docs/REPORT.md` has the phase section filled (status, evidence, deviations, hand-offs).
- [ ] Confirm any `[TO CONFIRM ON MACHINE]` items touched by the phase are now `[CONFIRMED]` in
      `docs/REFERENCES.md`.
- [ ] **Squash-merge.** Tag a `0.x` release if you want a checkpoint build; `1.0.0` after Phase 8.

---

### Notes on CI vs. local

GitHub's `windows-latest` runners are reliable for lint, the PsychoPy-free core, and the
discovery/entry-point/YAML tests, and for building/installing the wheel. They are **not** reliable for
opening a real PsychoPy **window** (calibration UI) or the **Builder GUI** — those are the items called
out above as your local/GUI checks. If a windowed integration test proves flaky on CI, the agents will
mark it so CI skips it and it stays in your local checklist instead.
