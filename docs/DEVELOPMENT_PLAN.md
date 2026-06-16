# Eye Tribe → PsychoPy Eye Tracker Plugin — Development Plan

**Project:** `psychopy-eyetracker-eyetribe`
**Goal:** A native PsychoPy ioHub eye-tracker extension for The Eye Tribe (ET1000), giving the same
class of integration that first-party plugins (Pupil Labs Neon, Tobii, GazePoint) provide — selectable
in the Builder Eyetracker component, usable from Coder via the ioHub Common Eye Tracker Interface, with
PsychoPy-driven calibration.
**Audience:** the coding agents (Claude Sonnet) who will implement the project. This plan is the
contract. **It contains no open design decisions** — every choice is made here. Agents implement; they
do not choose. Where the plan says "verify", it means confirming an *externally-fixed fact* (an Eye
Tribe wire-format detail or an ioHub framework convention) against its source — never selecting between
design options. The procedure to follow if a verification finds a discrepancy is specified inline, so
even those paths are deterministic.

---

## 0. Pinned environment & global decisions (binding for all phases)

| Item | Decision |
|---|---|
| Target application | PsychoPy **2026.1.3** Standalone (Windows build) |
| OS | **Windows 10/11 x64 only.** The Eye Tribe Server runs reliably only on Windows; the device, the Server, and therefore all CI/test runners and the published support matrix are Windows-only. No Linux/macOS support or CI. |
| Python | **3.10** (confirmed **3.10.11**) — the interpreter bundled with PsychoPy 2026.1.3 Standalone at `C:\Program Files\PsychoPy\python.exe`. `requires-python = ">=3.10"`. The dev/test environment uses that exact bundled interpreter (or a 3.10 venv with `psychopy` installed). |
| License | **GPL-3.0** (`GNU General Public License v3 (GPLv3)`), matching the PsychoPy ecosystem. |
| Build backend | **setuptools** (`setuptools.build_meta`) via `pyproject.toml`, mirroring `psychopy-eyetracker-pupil-labs`. |
| Package layout | **Flat** (no `src/`), mirroring the reference plugin. |
| pip / distribution name | `psychopy-eyetracker-eyetribe` |
| Import (top) package | `psychopy_eyetracker_eyetribe` |
| ioHub device subpackage | `psychopy_eyetracker_eyetribe/eyetribe/` |
| ioHub device namespace | `psychopy.iohub.devices.eyetracker.hw.eyetribe` |
| ioHub config key (Coder) | `eyetracker.hw.eyetribe.EyeTracker` |
| Runtime dependencies | **None beyond the Python standard library** (`socket`, `json`, `threading`, `queue`, `struct`, `logging`) plus `numpy` (already present in PsychoPy) for the validation metrics (`validation.py`). The transport speaks the Eye Tribe JSON protocol directly; no third-party Eye Tribe SDK. |
| Eye Tribe API protocol version | **1** (set explicitly on connect). |
| Transport mode | **Push** streaming (`tracker set push=true`), not pull. |
| Sampling rate | **Auto-adopt the Server-reported frame rate** (`framerate`, read at connect): 30 Hz on the ET1000, 60 Hz on the Pro. Not hard-coded; the value is read, recorded, and used for the latency budget. |
| Tracking mode / events | **Binocular** → `BinocularEyeSampleEvent`. Fixation events derived from the frame `fix` flag. |
| Gaze source exposed as samples | **Raw** gaze is the default written to `gaze_x`/`gaze_y` (faithful per-sample data for research); **smoothed (`avg`)** is selectable via config (`gaze_source: raw\|avg`, default `raw`). Both eyes' raw and avg are always retained internally. |
| Distribution | **GitHub release + built wheel** (pip-installable from the release asset). **No public PyPI publication.** |
| Pupil size units | Reported **as-is (arbitrary units)** in `pupil_measure1`; documented as not millimetres. No fabricated conversion. |
| Calibration | PsychoPy-drawn targets driving the Eye Tribe calibration API; **default 9 points**, also supports 5 and 12 via config (`calibration.target_count: 9`). |

These values are the single source of truth. Any string (package name, namespace, config key) appears
identically everywhere it is used.

---

## 1. Guiding principles

1. **Hardware-independent development.** Everything except Phase 11 (hardware validation) is built and tested
   *without* the ET1000, against a **mock Eye Tribe server** (Phase 1 deliverable). Hardware steps are
   isolated, scripted, and marked `[HARDWARE]`.
2. **Vertical slices behind stable interfaces.** Transport → data model → ioHub device → transforms/
   time-sync → calibration → packaging. Each layer has its own tests and runs independently.
3. **Mirror the reference plugin** `psychopy/psychopy-eyetracker-pupil-labs` exactly for structure,
   packaging, and discovery so the result is familiar to PsychoPy maintainers.
4. **Clean core / framework boundary.** `EyeTribeClient`, `frames`, time-sync, and calibration
   sequencing contain **zero PsychoPy imports** and are fully unit-testable standalone.
   ioHub/PsychoPy types appear only in the `EyeTracker` device class and the Builder settings backend.
   (Phase 9: `transforms.py` was removed; coordinate conversion is handled by the ioHub Display device.)
5. **Every phase ends in one reviewable, mergeable PR** with green CI and a `REPORT.md` entry. A phase
   is done only when its acceptance criteria are demonstrably met.

---

## 2. Authoritative sources (for verification of externally-fixed facts)

| Topic | Source | Used to verify |
|---|---|---|
| Eye Tribe Tracker API (wire format, frames, calibration, heartbeat) | `github.com/EyeTribe/documentation` — API Reference + Developer's Guide | That the concrete schema in §3 matches the documentation, and (Phase 11) a captured real frame |
| ioHub Common Eye Tracker Interface & required methods | `psychopy.org/api/iohub/device/eyetracker.html`; MouseGaze/Tobii/GazePoint implementation notes; the installed `psychopy.iohub.devices.eyetracker.EyeTrackerDevice` source | Exact `EyeTracker` method signatures and the device-YAML key structure for the pinned PsychoPy (filenames are pinned in §0/§5) |
| Packaging & discovery | `github.com/psychopy/psychopy-eyetracker-pupil-labs` (`pyproject.toml`, `__init__.py`, package layout) — already captured in §5 | That entry-point groups/values resolve in PsychoPy 2026.1.3 |
| Working transport reference | `peyetribe` (Baekgaard) and PyGaze's eyetribe backend | Cross-check the socket/heartbeat behaviour of `EyeTribeClient` |

**Phase 0 produces `docs/REFERENCES.md`** recording the verified facts (confirmed field names, method
signatures, the pinned ioHub YAML filenames, PsychoPy/Python versions) so no later phase re-researches.
**Discrepancy procedure (deterministic):** if a source contradicts this plan, the real device/installed
framework is ground truth — update the affected module, record the correction in `REFERENCES.md`, add a
golden fixture reproducing it in the mock, and note it in `REPORT.md`. This is a fix procedure, not a
design choice.

---

## 3. Eye Tribe wire format (authoritative for implementation)

All messages are JSON objects over the TCP socket, one object per message:
`{"category": <str>, "request": <str>, "values": {...}}`. Replies include `"statuscode"` (200 = OK).
Categories: `tracker`, `calibration`, `heartbeat`.

**Connect sequence (client):**
1. Open TCP socket to host/port (defaults `127.0.0.1` : `6555`).
2. `{"category":"tracker","request":"set","values":{"version":1}}` — set protocol version.
3. `{"category":"tracker","request":"get","values":["heartbeatinterval","framerate","screenresw","screenresh","iscalibrated","trackerstate"]}` — read session params.
4. `{"category":"tracker","request":"set","values":{"push":true}}` — begin streaming.
5. Start the heartbeat thread (see below).

**Pushed frame** — in push mode the Server (build 0.9.77, confirmed on hardware 2026-06-15) emits frames
as `{"category":"tracker","request":"get","values":{"frame":{…}}}`. Note `request` is **`"get"`**, not
`"push"`; the reader MUST detect frame messages by the **presence of `values.frame`**, not the request
string.
```
frame = {
  "timestamp": "2026-06-15 14:30:14.068",   # wall-clock string (absolute local time)
  "time": 188928052,                        # MONOTONIC milliseconds (relative, ~uptime) -- NOT epoch
  "fix": true,                              # bool: is the gaze currently fixating
  "state": 7,                              # int: 32-bit status bitmask (see below)
  "raw":  {"x": 1024.5, "y": 720.3},        # gaze in SCREEN PIXELS, origin top-left
  "avg":  {"x": 1027.2, "y": 715.7},        # smoothed gaze, screen pixels
  "lefteye":  {"raw": {"x":..,"y":..}, "avg": {"x":..,"y":..}, "psize": 20.5, "pcenter": {"x":0.41,"y":0.55}},
  "righteye": {"raw": {"x":..,"y":..}, "avg": {"x":..,"y":..}, "psize": 21.0, "pcenter": {"x":0.59,"y":0.55}}
}
```

**`state` bitmask** (decode each bit into an explicit flag):
| Bit | Hex | Meaning |
|---|---|---|
| `STATE_TRACKING_GAZE` | `0x1` | Gaze coordinates are available (tracker calibrated & tracking) |
| `STATE_TRACKING_EYES` | `0x2` | Eyes were located this frame |
| `STATE_TRACKING_PRESENCE` | `0x4` | A user is present in front of the tracker |
| `STATE_TRACKING_FAIL` | `0x8` | Tracking failed for this frame |
| `STATE_TRACKING_LOST` | `0x10` | Tracking lost (no valid data for a sustained period) |

**Sample validity mapping → ioHub `status`:** `0` (valid) when `STATE_TRACKING_GAZE` set and neither
`FAIL` nor `LOST` set; otherwise `2` (missing/invalid), matching the MouseGaze convention
(0 = valid, 2 = missing).

**`trackerstate` values:** `0` CONNECTED, `1` NOT_CONNECTED, `2` CONNECTED_BADFW, `3` CONNECTED_NOUSB3,
`4` CONNECTED_NOSTREAM. Connection is healthy only at `0`.

**Heartbeat:** `{"category":"heartbeat"}` with no `request`. Must be sent at an interval shorter than the
server's `heartbeatinterval` (milliseconds, read at connect). **Decision:** send every
`heartbeatinterval / 2` ms from a dedicated thread.

**Calibration messages:**
- Start: `{"category":"calibration","request":"start","values":{"pointcount":9}}`
- Per point (after the target is displayed and the participant has settled):
  `{"category":"calibration","request":"pointstart","values":{"x":<px>,"y":<px>}}`, hold the dwell,
  then `{"category":"calibration","request":"pointend"}`.
- After the final `pointend`, the reply carries `calibresult` (below).
- Abort: `{"category":"calibration","request":"abort"}`. Clear: `{"category":"calibration","request":"clear"}`.

**`calibresult`:**
```
calibresult = {
  "result": true,            # bool: calibration successful
  "deg": 0.71,               # average error, degrees (both eyes)
  "degl": 0.66, "degr": 0.77,# avg error left / right eye, degrees
  "calibpoints": [
    {"state": 1,
     "cp":   {"x":..,"y":..},  # calibration point (target) location, pixels
     "mecp": {"x":..,"y":..},  # mean estimated gaze location at the point, pixels
     "ad": .., "adl": .., "adr": ..,   # accuracy distance, degrees (avg/left/right)
     "mep": .., "mepl": .., "mepr": ..}# mean error, pixels (avg/left/right)
  ]
}
```

**Screen geometry:** obtain the pixel resolution the Server is using from `screenresw`/`screenresh`
(via `tracker get`). The coordinate transform (Phase 4) uses these, not assumptions.

This section is authoritative. Phase 0 verifies it against the documentation; Phase 11 verifies it against
one captured real frame and applies the discrepancy procedure (§2) if needed.

---

## 4. Target architecture

```
┌───────────────────────────── ioHub server process ─────────────────────────────┐
│  EyeTracker (psychopy.iohub...hw.eyetribe.EyeTracker)  ── PsychoPy/ioHub types   │
│    • lifecycle: setConnectionState / setRecordingState / enableEventReporting    │
│    • _poll(): drains FrameBuffer → BinocularEyeSampleEvent (+ fixation events)   │
│    • runSetupProcedure(): PsychoPy-drawn calibration, drives calibration API     │
│    • trackerTime()/clock offset; _eyeTrackerToDisplayCoords / inverse            │
│            │ uses                                                                 │
│            ▼                                                                      │
│  EyeTribeClient  ── NO PsychoPy imports (pure stdlib + numpy)                    │
│    • connect / close / reconnect (3 attempts, 0.5 s backoff, then DISCONNECTED)  │
│    • ReaderThread → frames.parse() → thread-safe bounded FrameBuffer (len 1024)  │
│    • HeartbeatThread → every heartbeatinterval/2 ms                              │
│    • request/reply API: set version/push, get params, calibration *             │
│            │ TCP 127.0.0.1:6555 (JSON, protocol v1)                              │
└────────────┼─────────────────────────────────────────────────────────────────────┘
             ▼
   Eye Tribe Server (real ET1000)   OR   MockEyeTribeServer (dev / CI)
```

*Diagram labels are shorthand. The parser function is `frames.parse_frame()` (Phase 2); `EyeTribeClient`
itself is stdlib-only, while `numpy` is used by the validation metrics (`validation.py`) — not the client.
`transforms.py` was removed in Phase 9; coordinate conversion is delegated to the ioHub Display device.*

---

## 5. Repository structure (flat layout, mirrors the reference plugin)

```
psychopy-eyetracker-eyetribe/
├── pyproject.toml                 # setuptools build + entry points (see §5.1)
├── MANIFEST.in                    # include *.yaml in sdist/wheel
├── README.md
├── CHANGELOG.md
├── LICENSE                        # GPL-3.0
├── CONTRIBUTING.md
├── .gitignore
├── .pre-commit-config.yaml        # ruff, black, isort, end-of-file/trailing-whitespace fixers
├── .github/workflows/
│   ├── ci.yml                     # runs-on: windows-latest, python 3.10 — lint + type + tests
│   └── release.yml                # build wheel + attach to GitHub Release on tag (windows-latest)
├── docs/
│   ├── REFERENCES.md              # verified API facts (Phase 0)
│   ├── DEVELOPMENT_PLAN.md        # this file
│   ├── REPORT.md                  # running progress log (§6)
│   ├── ARCHITECTURE.md
│   ├── coordinate_systems.md      # transform math + diagram
│   └── hardware_validation.md     # [HARDWARE] checklists + recorded results (§8)
├── psychopy_eyetracker_eyetribe/  # top import package
│   ├── __init__.py                # GPL header only (matches reference; discovery is via entry points)
│   ├── eyetribe/                  # ioHub device package -> hw.eyetribe
│   │   ├── __init__.py            # lazy `EyeTracker` export (PEP 562) — keeps core importable w/o PsychoPy
│   │   ├── eyetracker.py          # EyeTracker(EyeTrackerDevice)
│   │   ├── eyetribe_client.py     # EyeTribeClient transport (no psychopy imports)
│   │   ├── frames.py              # Frame/EyeData dataclasses + parser + state bitmask
│   │   ├── time_sync.py           # tracker<->psychopy clock-offset model (no psychopy imports)
│   │   ├── calibration.py         # calibration sequencing helpers (no psychopy imports)
│   │   ├── settings.py            # EyeTribeEyetrackerBackend (Builder dropdown integration)
│   │   ├── default_eyetracker.yaml          # ioHub default device settings (confirmed ioHub name)
│   │   └── supported_config_settings.yaml   # ioHub supported-settings schema (confirmed ioHub name)
│   └── mock/
│       ├── __init__.py
│       └── mock_server.py         # MockEyeTribeServer (dev, CI, and shipped for hardware-free trials)
└── tests/
    ├── conftest.py                # fixture: start/stop MockEyeTribeServer on a free port
    ├── unit/
    │   ├── test_frames.py
    │   ├── test_client.py
    │   ├── test_eyetracker_coords.py  # Phase 9: stub-display coordinate delegation
    │   └── test_time_sync.py
    ├── integration/
    │   ├── test_client_against_mock.py
    │   ├── test_eyetracker_against_mock.py
    │   └── test_launchhub_against_mock.py  # Phase 9: iohub marker, host-only
    └── manual/                    # [HARDWARE] — require ET1000 + Eye Tribe Server
        ├── smoke_socket.py
        ├── stream_demo.py
        └── calibration_demo.py
```

### 5.1 `pyproject.toml` — build & discovery sections
```toml
[build-system]
requires = ["setuptools>=40.8.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "psychopy-eyetracker-eyetribe"
requires-python = ">=3.10"
license = {text = "GNU General Public License v3 (GPLv3)"}
dependencies = ["numpy"]              # numpy ships with PsychoPy; transport is stdlib-only

[project.optional-dependencies]
tests = ["psychopy", "pytest", "pytest-cov"]
dev   = ["psychopy", "pytest", "pytest-cov", "ruff", "black", "isort", "mypy", "pre-commit"]

[tool.setuptools.packages.find]
where = ["", "psychopy_eyetracker_eyetribe"]

[tool.setuptools.package-data]
"*" = ["*.yaml"]

[project.entry-points."psychopy.iohub.devices.eyetracker.hw"]
eyetribe = "psychopy_eyetracker_eyetribe.eyetribe"

[project.entry-points."psychopy.experiment.components.settings.eyetracking"]
EyeTribeEyetrackerBackend = "psychopy_eyetracker_eyetribe.eyetribe.settings:EyeTribeEyetrackerBackend"
```
Standard project metadata (`version`, `description`, `readme`, `authors`, `classifiers`, `urls`) is also
required and is included as usual; it is omitted above only for brevity. The sections shown — build
system, dependencies, packaging `find`/`package-data`, and the two entry-point groups — must appear
verbatim, as they drive discovery. **The device group must end in `.hw`** (`psychopy.iohub.devices.eyetracker.hw`):
PsychoPy builds the full module path `psychopy.iohub.devices.eyetracker.hw.eyetribe` and matches the
entry-point group by prefix, so the shorter group never matches (verified post-Phase-7).

There are **no** `psychopy.experiment.components` entry points and no Builder component icons: the Eye
Tribe integrates purely as an eyetracker backend, so no custom Builder components (and therefore no
icon assets) are required.

### 5.2 ioHub YAML filenames (pinned)
The two device YAML filenames are dictated by the ioHub loader and are **pinned**:
`default_eyetracker.yaml` (defaults) and `supported_config_settings.yaml` (settings schema) — the names
used by the in-tree GazePoint device. They are not subject to choice. To remove any residual risk that
the loader expects a different name in PsychoPy 2026.1.3, **Phase 0 adds a test that loads the device
through ioHub's own config loader and asserts both files are found and parsed**; a wrong name fails CI
mechanically, so there is nothing to confirm by hand. Their **contents** are fully specified in Phase 3.

---

## 6. Engineering conventions, CI & reporting

**Branching / PRs.** `main` protection is a **deferred TODO** (private, single-contributor repo for
now; re-enable — require PR + passing CI — before adding collaborators or going public). The flow is
still followed by convention: one branch + PR per phase: `phase-N-short-name`, title
`Phase N: <title>`. The PR description restates the phase acceptance criteria as a ticked checklist with
evidence (test output, coverage %, screenshots for `[HARDWARE]`). Squash-merge.

**Commits.** Conventional Commits (`feat:`/`fix:`/`test:`/`docs:`/`chore:`/`refactor:`).

**Versioning.** Semantic Versioning. Pre-hardware development releases are tagged `0.x`; the first
`1.0.0` tag follows successful Phase 11 hardware validation **and** the Phase 12 backlog-cleanup pass
(`v1.0.0` is cut at the end of Phase 12). `CHANGELOG.md` is updated for every release tag.

**CI (`ci.yml`) — `runs-on: windows-latest`, Python 3.10, single configuration (no matrix):**
1. `ruff check` + `black --check` + `isort --check` — must be clean.
2. `mypy` on the PsychoPy-free core (`eyetribe_client.py`, `frames.py`, `time_sync.py`,
   `calibration.py`, `mock_server.py`) — strict; no errors. The ioHub `EyeTracker` class and
   `settings.py` are excluded (loose framework base types). (`transforms.py` was removed in Phase 9.)
3. `pytest -m "not hardware and not iohub"` — unit + the device-against-mock integration tests, all
   green. These construct `EyeTracker` **directly** against the mock (no ioHub subprocess, no display),
   so they run headless on the runner.
4. Coverage gate: **≥ 90%** on the full PsychoPy-free core — `eyetribe_client`, `frames`, `time_sync`,
   `calibration`, `validation`, and `mock_server` (each measured with a separate `--cov=` flag,
   `--cov-fail-under=90`).  `eyetracker.py` and `settings.py` are excluded from the gate because their
   window / Builder paths cannot run headless.  The ioHub `EyeTracker` class is covered best-effort via
   the device-against-mock tests (no numeric gate).

**Not in the CI gate — host-run only.** Tests marked `@pytest.mark.iohub` spawn a real ioHub subprocess
via `launchHubServer` and need a display (+ the `.pth` dev step); the GitHub runner can't do this
reliably, so they are **excluded from CI** (`-m "... and not iohub"`) and run locally on the Windows
host (Phase 9 Part B). `@pytest.mark.hardware` likewise needs the ET1000 (Phase 11).

CI is Windows-only by design: the device, the Eye Tribe Server, and the target PsychoPy build are
Windows-only, so there is no value in other-OS runners even though the mock-based tests are
OS-agnostic.

**Reporting — `docs/REPORT.md`** (append-only; one section per phase):
```
## Phase N — <title>  (status: DONE | IN PROGRESS | BLOCKED)
- Date / agent / PR link / merge commit
- Delivered (mapped to the phase deliverables)
- Acceptance criteria: each item -> PASS/FAIL + evidence (test names, coverage %, screenshot path)
- Deviations from plan + rationale  (expected: none, since the plan fixes all decisions)
- Verified facts fed back into docs/REFERENCES.md
- Open issues / TODOs handed to the next phase
- [HARDWARE] results, if any (device serial, Eye Tribe Server version, Windows build)
```
A phase that cannot meet a criterion is logged `BLOCKED` with the specific blocker and is **not** marked
done. The task tracker mirrors this.

**Definition of Done (per phase):** acceptance criteria met + CI green + `REPORT.md` updated +
`REFERENCES.md`/`ARCHITECTURE.md` updated where facts were verified + PR merged.

---

## 7. Phased plan

Linear dependencies. Phases 0–7 are software (mock-tested). **Phase 8** (validation tooling) and
**Phase 9** (ioHub integration fixes) are complete. **Phase 10** (post-review fixes & hardening) is
software + CI work; **Phase 11** is hardware validation on the ET1000; **Phase 12** is the backlog-cleanup
& release phase (where `v1.0.0` is tagged).

### Phase 0 — Repository scaffold & fact verification
**Objective.** Stand up repo, tooling, CI skeleton; verify all externally-fixed facts.
**Deliverables.**
- Repo structure per §5. Python stubs **import cleanly** (method bodies raise `NotImplementedError`,
  never at import); the stub `EyeTracker` **and** a stub `EyeTribeEyetrackerBackend` both exist so the
  two §5.1 entry points resolve, and `default_eyetracker.yaml` / `supported_config_settings.yaml` are
  minimal but **valid, loadable** YAML.
- `pyproject.toml` per §5.1 (build/discovery sections verbatim, plus standard project metadata);
  `.pre-commit-config.yaml`; `ci.yml` running lint + an empty (passing) pytest on `windows-latest`/py3.10.
- `docs/REFERENCES.md` recording: (a) confirmation that §3 matches the Eye Tribe documentation, with any
  corrections applied; (b) the actual `EyeTrackerDevice` method signatures read from the installed
  PsychoPy 2026.1.3 source; (c) the ioHub device-YAML key structure read from the installed GazePoint/
  Tobii device (filenames are pinned: `default_eyetracker.yaml`, `supported_config_settings.yaml`);
  (d) confirmed PsychoPy 2026.1.3 / Python 3.10 versions.
- The stub device's entry point is registered and the `EyeTracker` class imports under PsychoPy; the
  exact plugin-activation path that exposes `eyetracker.hw.eyetribe` is recorded in `REFERENCES.md`.
**Acceptance criteria.**
- `pip install -e .[dev]` succeeds in a PsychoPy 2026.1.3 / Python 3.10 environment.
- CI green (lint + empty pytest) on `windows-latest`.
- Both §5.1 entry points are registered (asserted by `test_discovery.py`), and the `EyeTracker` class
  imports under PsychoPy. **Note:** a bare `import psychopy.iohub.devices.eyetracker.hw.eyetribe` does
  NOT resolve at import time — PsychoPy exposes plugin devices via its plugin system / at
  `launchHubServer`, not as a plain importable module. The activation mechanism is pinned in
  `REFERENCES.md`; end-to-end device load is verified in Phase 3 against the mock.
- A test loads the stub device through ioHub's own config loader and asserts both
  `default_eyetracker.yaml` and `supported_config_settings.yaml` are found and parsed (a wrong filename
  fails CI — no manual verification).
- `REFERENCES.md` complete.

### Phase 1 — Transport layer + Mock server
**Objective.** Reliable, hardware-free socket client and a faithful mock.
**Deliverables.**
- `MockEyeTribeServer`: binds a configurable port; speaks the §3 protocol (`set version`, `get` params,
  `set push`); pushes synthesized frames at a configurable rate (default 30 Hz) following a configurable
  gaze model (fixed point, linear sweep, and injectable blink/`STATE_TRACKING_LOST` segments); enforces
  heartbeats (disconnects the client if none arrives within `heartbeatinterval`, default 3000 ms); and
  provides a scriptable calibration responder returning a configurable `calibresult`.
- `EyeTribeClient`: connect (steps 1–5 of §3), close, reconnect (3 attempts × 0.5 s backoff → state
  `DISCONNECTED`), request/reply with a 2 s timeout, `ReaderThread` parsing pushed frames into a
  thread-safe **bounded** `FrameBuffer` (capacity 1024, oldest dropped on overflow), `HeartbeatThread`
  (interval = server `heartbeatinterval` / 2), and structured `logging`.
**Acceptance criteria.**
- Client connects to the mock, enables push, receives frames within ±10% of the configured rate.
- Heartbeat keeps the link alive ≥ 30 s; stopping heartbeats triggers a mock disconnect the client
  detects, reports, and (per policy) attempts to reconnect.
- No leaked threads/sockets after `close()` (asserted in teardown).
- `eyetribe_client.py` and `mock/` contain zero PsychoPy imports.
**Tests.** `tests/integration/test_client_against_mock.py` (lifecycle, rate, heartbeat timeout,
reconnect, overflow drop); `tests/unit/test_client.py` (message framing, request/reply timeout).

### Phase 2 — Frame parsing & data model
**Objective.** Typed, validated domain objects from raw JSON frames.
**Deliverables.**
- `frames.py`: frozen `EyeData` (raw, avg, psize, pcenter) and `Frame` (time, fix, state, raw, avg,
  left, right) dataclasses; `parse_frame(dict) -> Frame`; a `TrackingState` decoder turning `state` into
  named booleans (per §3 table); helpers `is_gaze_valid()`, `gaze(source: "raw"|"avg")`; malformed input
  raises `FrameParseError` (the `ReaderThread` logs and skips — never crashes).
**Acceptance criteria.**
- Parser round-trips every frame variant the mock emits: valid binocular, eyes-only (no gaze), blink,
  `STATE_TRACKING_LOST`, and malformed (→ `FrameParseError`).
- All 32 representable low-5-bit `state` combinations decode deterministically (table-driven test).
**Tests.** `tests/unit/test_frames.py` with fixture frames generated by the mock; one real captured
frame is added as a golden fixture in Phase 11.

### Phase 3 — ioHub EyeTracker class (recording & polling)
**Objective.** A working ioHub device streaming samples (calibration/transforms follow).
**Deliverables.**
- `EyeTracker(EyeTrackerDevice)` — implement only the **device-specific** methods (confirmed in
  `REFERENCES.md`): `__init__`, `setConnectionState`/`isConnected`, `setRecordingState`/
  `isRecordingEnabled`, `enableEventReporting`, `_poll()`, `trackerTime`/`trackerSec`. **Rely on the
  base class** for `getEvents`/`clearEvents`/`getConfiguration`/`getLastSample`/`getLastGazePosition`/
  `getPosition`/`isReportingEvents` and its native-event buffer — do not re-implement them. `_poll()`
  drains the `FrameBuffer` and pushes one `BinocularEyeSampleEvent` per frame with the confirmed
  mapping (REFERENCES.md): `left/right_gaze_x,y` ← transformed per-eye gaze (per `gaze_source`, default
  `raw`); `left/right_eye_cam_x,y` ← `pcenter`; `left/right_pupil_measure1` (+ `_type`) ← `psize`
  (arbitrary units); `status` ← §3 validity (calibrated + in-bounds). Fixation start/end events from
  `fix` transitions.
- `default_eyetracker.yaml` with the concrete defaults: `host: 127.0.0.1`, `port: 6555`,
  `api_version: 1`, `runtime_settings.sampling_rate: auto` (adopt the Server-reported `framerate`;
  resolved to the actual value at connect and used to set the poll interval), `track_eyes: BINOCULAR`,
  `gaze_source: raw`, `calibration.target_count: 9`, `event_buffer_length: 1024`,
  `device_timer.interval: 0.005` (200 Hz poll — ample headroom for 30/60 Hz frames),
  `auto_report_events: False`,
  `monitor_event_types: [BinocularEyeSampleEvent, FixationStartEvent, FixationEndEvent]`.
  `supported_config_settings.yaml` enumerates the same keys with allowed values/types.
**Acceptance criteria.**
- `launchHubServer(**{'eyetracker.hw.eyetribe.EyeTracker': {...}})` starts against the mock; samples
  flow through `io.devices.tracker.getEvents()` with correct field values; recording toggles on/off.
- Sample timestamps are in the PsychoPy timebase (interim fixed offset acceptable; refined in Phase 4).
- `gaze_source` config switches raw vs avg as asserted in the test.
**Tests.** `tests/integration/test_eyetracker_against_mock.py` running a real ioHub server process
against the mock: assert event counts, field ranges, validity propagation, recording state changes,
config-driven gaze source.

### Phase 4 — Coordinate transforms & time synchronization
**Objective.** Correct spatial and temporal alignment with PsychoPy.
**Deliverables.**
- `transforms.py` (PsychoPy-free): pure functions converting Eye Tribe pixel coords — normalized by the
  Server screen resolution (`screenresw/h`, read at connect) into 0–1 — to/from the ioHub Display
  coordinate bounds, with the Display bounds and unit passed in as plain numbers (no PsychoPy import).
  `EyeTracker._eyeTrackerToDisplayCoords()` / `_displayToEyeTrackerCoords()` are thin wrappers that read
  the Display bounds from ioHub and delegate to `transforms.py`, following the Tobii pattern. Documented
  in `docs/coordinate_systems.md` with a diagram and worked example.
- `time_sync.py` (PsychoPy-free) backing `trackerTime()`/`trackerSec()`: at recording start, pair the
  first frame's `time` (**monotonic milliseconds**, relative/~uptime — not epoch; ÷1000 for seconds)
  with the local PsychoPy time at receipt, correcting for half the measured request/reply RTT; apply
  `psychopy_time = tracker_time_s + offset`. Re-estimate the offset every 5 s and keep the latest.
  `docs/coordinate_systems.md` (timing section) states the residual latency budget
  = sampling latency (1/rate ≈ 33 ms @ 30 Hz) + transport.
**Acceptance criteria.**
- Known device pixel coordinates map to expected display-unit coordinates for `pix`, `norm`, `height`,
  and (with a monitor calibration) `deg`, asserted numerically; forward∘inverse round-trips to within
  **1e-6** in normalized space.
- Synthetic frames with known `time` map to expected PsychoPy times within **1 ms** in unit tests
  (deterministic math; no hardware jitter).
**Tests.** `tests/unit/test_time_sync.py` (offset estimation, drift re-estimation, RTT correction).
*(Phase 4 originally included `test_transforms.py`; this was removed in Phase 9 when `transforms.py`
was replaced by the ioHub Display device delegation.)*

### Phase 5 — Calibration via PsychoPy (`runSetupProcedure`)
**Objective.** PsychoPy-drawn calibration driving the Eye Tribe calibration API.
**Deliverables.**
- `runSetupProcedure(calibration_args)`: presents targets in the PsychoPy window for the configured
  `target_count` (default 9; 5 and 12 supported) in a standard grid layout, with target animation and a
  fixed pre-sample settle of 750 ms then a 1000 ms sample window per point; sequences
  `calibration start` → per-point `pointstart`/dwell/`pointend`; handles keyboard abort
  (`calibration abort`) and `clear`; parses `calibresult`; renders an accuracy summary (overall `deg`
  and per-point `ad`); offers accept/redo. Restores window state on exit. Calibration sequencing logic
  lives in `calibration.py` (PsychoPy-free, unit-tested); `runSetupProcedure` is the thin PsychoPy
  drawing/loop wrapper.
**Acceptance criteria.**
- Against the mock's scriptable responder, full 5-, 9-, and 12-point runs complete, parse `calibresult`,
  and report per-point + overall accuracy; abort and redo paths work and leave the device in a clean
  recordable state.
- Calibration is keyboard-interruptible; window state is restored after accept, redo, and abort.
**Tests.** `tests/unit` for `calibration.py` (message-sequence + result parsing against the mock
responder, no window); `tests/integration` driving `runSetupProcedure` with a headless/offscreen window
where supported, asserting the exact message sequence sent to the mock.

### Phase 6 — Packaging, plugin discovery & Builder backend
**Objective.** Real, installable plugin that PsychoPy auto-loads and exposes in Builder.
**Deliverables.**
- Finalized `pyproject.toml` (§5.1), `MANIFEST.in` shipping `*.yaml`, and `settings.py` defining
  `EyeTribeEyetrackerBackend` (Builder Eyetracker dropdown entry + its parameter fields: host, port,
  gaze source, calibration target count), registered via the §5.1 settings entry point. Sampling rate is
  **not** a field — it is auto-adopted from the Server (§0).
- `release.yml` building a wheel on tag and attaching it to a **GitHub Release** (`windows-latest`).
  **No PyPI publication** — install is `pip install <wheel-from-release>`.
**Acceptance criteria.**
- Building the wheel and `pip install`-ing it into a **clean** PsychoPy 2026.1.3 env (no source tree
  present) makes `eyetracker.hw.eyetribe.EyeTracker` importable and usable.
- "Eye Tribe" appears in the Builder Eyetracker component dropdown with its parameter fields.
**Tests.** CI job that builds the wheel, installs it into a clean PsychoPy 2026.1.3 environment (no
plugin source tree present), imports the namespace, and loads the device config; a documented manual
Builder dropdown check recorded in `REPORT.md`.

### Phase 7 — Documentation & examples
**Objective.** Usable by a researcher who is not the author.
**Deliverables.**
- `README.md` (prerequisites incl. Eye Tribe Server, install, quick start, the 30 Hz limitation, pupil-
  units caveat, Windows-only note), a Coder example using `eyetracker.hw.eyetribe.EyeTracker`, a Builder
  example `.psyexp`, an implementation-notes doc mirroring sibling plugins, and troubleshooting (Server
  not running, port conflict, heartbeat drop, `trackerstate` ≠ 0).
**Acceptance criteria.**
- A new user can follow the README to run the bundled Coder demo **against the mock** end-to-end.
- All public API has docstrings; the Coder demo runs against the mock in CI.
**Tests.** Doc-link check + the example script executed against the mock in CI.

### Phase 8 — Validation tooling & hardware smoke (COMPLETE)
**Objective.** Provide the scripts + analysis needed for hardware validation — all developed and verified
against the **mock** — plus the one-off hardware stream smoke (the pre-Phase-0 gate). The on-hardware
*execution* of this tooling is **Phase 11** (after the Phase 9 fixes).
**Status.** DONE, mock-verified (see `docs/REPORT.md`).
**Deliverables (in repo).**
- `tests/manual/smoke_socket.py` — raw-socket stream check (run on hardware 2026-06-15, PASS;
  `_captured_frame.json` saved).
- `tests/manual/stream_demo.py` — gaze-contingent dot via `EyeTribeClient` (mock + `--real`).
- `tests/manual/calibration_demo.py` — standalone 9-point calibration via `CalibrationSequencer`.
- `tests/manual/validation_experiment.py` — target-grid accuracy / precision / timing experiment.
- `psychopy_eyetracker_eyetribe/eyetribe/validation.py` — PsychoPy-free metrics
  (`compute_accuracy` / `compute_precision` / `compute_timing_stats`) + `tests/unit/test_validation.py`.
- `docs/hardware_validation.md` — run-environment table, per-step checklist, metrics table, and the
  calibrated-golden-frame reconciliation procedure.
**Acceptance criteria (met).** All scripts run against the mock; `validation.py` unit tests green;
lint/type clean. Hardware execution is deferred to Phase 11.

### Phase 9 — ioHub integration fixes & hardening
**Objective.** Resolve the issues found in the pre-handoff code review so a real PsychoPy experiment
(via `launchHubServer`) reports gaze in the correct **display units**, tighten validity and reconnect
behaviour, and guard the working integration with a permanent automated test. **Mechanical/coding work
first; human-in-the-loop verification second.**
**Prerequisite.** Phases 1–8 merged. **Environment:** Part A needs only Python 3.10; Part B needs
PsychoPy 2026.1.3 (+ a display).
**Context (already working — do not "re-fix").** A prior one-off `launchHubServer` test recorded 32
events after the entry-point group was set to `psychopy.iohub.devices.eyetracker.hw` and the event
classes were exported from `eyetribe/__init__.py` (both already in the code). The event pipeline works;
the gaps below are narrower.

**Part A — code & tests (no hardware).**
- **Coordinate units (primary fix).** `EyeTracker._eyeTrackerToDisplayCoords` /
  `_displayToEyeTrackerCoords` call `self._display_device.getBounds()`, which is **not** an ioHub Display
  method → it raises → the silent fallback emits gaze in **raw top-left pixels**, not the experiment's
  display units. Replace with the base pattern
  `self._display_device._pixel2DisplayCoord(gaze_x, gaze_y, self._display_device.getIndex())` (Eye Tribe
  gaze is already top-left pixels — exactly that method's expected input), keeping a pixel pass-through
  only as the no-display test fallback. `transforms.py` then becomes unused by the device path:
  **delete `transforms.py` and `tests/unit/test_transforms.py`**, remove them from the `[tool.mypy]`
  files list and the coverage scope, and update the references in §5 (repo tree), Principle 4 (§1), the
  §4 architecture footnote, and `docs/coordinate_systems.md` §1.6 to match.
- **Validity guard.** In `_process_frame`, emit `status=0` only when the sample is state-valid **and**
  in-bounds (`0 ≤ x ≤ screen_w`, `0 ≤ y ≤ screen_h`); otherwise `status=2`. Matches `REFERENCES.md`
  ("calibrated + in-bounds, not the `STATE_TRACKING_GAZE` bit alone").
- **Reconnect hygiene.** `EyeTribeClient._reconnect_bg` / `_connect_once` can leave a second heartbeat
  thread running and re-clear the shared `_stop_evt`. A reconnect must stop/join the previous reader +
  heartbeat before starting new ones; assert no duplicate threads after a reconnect.
- **Permanent `launchHubServer` regression test — host-run, NOT in the CI gate.** Promote the throwaway
  `_test_launchhub.py` to `tests/integration/test_launchhub_against_mock.py` under a dedicated marker
  `@pytest.mark.iohub`: start the mock, run `launchHubServer` with `eyetracker.hw.eyetribe.EyeTracker`,
  record ≥ 1 s, and assert `io.devices.tracker.getEvents()` is non-empty **and** `getPosition()` is
  inside the active Display's bounds (this is what catches the coordinate bug). It spawns a real ioHub
  subprocess + display, so **exclude it from GitHub CI** (register the `iohub` marker in `pyproject.toml`;
  CI runs `-m "not hardware and not iohub"`); run it **locally on the Windows host** (with the `.pth`
  step) as the first step of Part B. Do **not** mark it `integration` — those tests drive the device
  directly and must keep running headless in CI.
- **Doc/code reconciliation.** Set the entry-point group to `psychopy.iohub.devices.eyetracker.hw` in
  §5.1 and `REFERENCES.md` (code + `test_discovery.py` already use it). Document the ioHub-subprocess
  `.pth` developer step (so the editable install is visible to the server subprocess) in `HUMAN_TASKS.md`.
- **Verify the Builder path.** Confirm `settings.py` `getParams` / `writeDeviceCode` match the in-tree
  `MouseGazeEyetrackerBackend` (no automated test covers Builder code-gen).

**Part B — human-in-the-loop verification (Windows + PsychoPy).**
- Run `pytest -m iohub -q` on the machine; confirm `test_launchhub_against_mock` is green.
- Run a minimal real experiment (or the README snippet) and confirm `tracker.getPosition()` returns
  coordinates in the **window's units** (e.g. centred for `pix`), not raw `0–1920` pixels.
- Record outcomes in `docs/REPORT.md` (Phase 9 section).

**Acceptance criteria.**
- Coordinate conversion goes through the Display device (no `getBounds`). A **CI-runnable** test injects
  a stub `_display_device` (`_pixel2DisplayCoord` / `getIndex`) and asserts the delegation + that a known
  device pixel maps inside the Display bounds — so the fix is regression-guarded in CI without the ioHub
  subprocess (the host-only `iohub` test is the end-to-end check).
- Out-of-bounds / uncalibrated gaze yields `status=2` (CI-runnable, via the mock with an out-of-bounds
  gaze model).
- No duplicate client threads after a reconnect (asserted).
- `tests/integration/test_launchhub_against_mock.py` (marker `iohub`) passes **on the Windows host**
  (`getEvents()` non-empty; `getPosition()` within Display bounds) — recorded in `REPORT.md`; not CI-gated.
- Docs reconciled (entry-point group; `.pth` step); `ruff`/`black`/`isort`/`mypy` clean; the **CI suite**
  (`-m "not hardware and not iohub"`) is green on `windows-latest`.
- Human-in-the-loop verification recorded in `REPORT.md`.
**Tests.** New `launchHubServer` integration test; reconnect-hygiene test; coordinate-mapping assertion;
existing suite stays green.

### Phase 10 — Post-review fixes & hardening
**Objective.** Resolve the items found in the pre-Phase-11 code review (recorded in `docs/REPORT.md`):
fix a misleading reconnect test, broaden the coverage gate to the full PsychoPy-free core, add the
"no-gaze" `(0,0)` validity exclusion (and document it), plus two minor cleanups. Pure software + CI;
no hardware.
**Prerequisite.** Phase 9 merged. **Environment:** Python 3.10 (+ PsychoPy for the PsychoPy-gated tests
in CI). Do the steps **in order**:

1. **Fix the false-confidence reconnect test.**
   `tests/integration/test_client_against_mock.py::test_stopping_heartbeats_causes_disconnect_and_reconnect`
   sets `client._stop_evt` manually, which suppresses `_on_server_eof` (the reader only calls it when
   `_stop_evt` is *not* set) — so the reconnect path never runs and the final assertion is trivially
   true. Rewrite it to drop the connection **from the server side** (e.g. close the mock's client
   handler) *without* touching `client._stop_evt`, so the reader hits EOF → `_on_server_eof` →
   `_reconnect_bg`. Assert the client reconnects (state `CONNECTED`) against the still-listening mock
   **and** that no duplicate reader/heartbeat threads remain (thread count stable). PsychoPy-free → CI.

2. **Broaden the coverage gate to the full PsychoPy-free core.**
   Extend the `ci.yml` coverage step to measure `eyetribe_client`, `frames`, `time_sync`, `calibration`,
   `validation`, and `mock_server` (one `--cov=` per module), keeping `--cov-fail-under=90`. Do **not**
   add `eyetracker.py` / `settings.py` (PsychoPy-coupled; their window/Builder code can't run headless
   and would tank the number). If a measured module is < 90%, add unit tests to bring it up (likely
   candidates: `calibration` sequencer branches, `eyetribe_client` error/reconnect paths — step 1 helps
   the latter). A temporary red CI here is acceptable; finish green. Update §6 to list the broadened gate.

3. **"No-gaze" `(0,0)` validity exclusion.**
   The Eye Tribe reports `raw/avg = (0,0)` as a "no gaze this frame" sentinel even on `state == 7`
   frames (confirmed in the smoke capture). In `EyeTracker._process_frame`, treat a combined gaze of
   exactly `(0,0)` as invalid: `status = 2`, and do not update `_latest_gaze_position`. (Current guard is
   `is_gaze_valid() and in_bounds`; `(0,0)` passes in-bounds, so add `and not (combined.x == 0 and
   combined.y == 0)`.) Assert it (mock with a fixed `(0,0)` gaze model → `status == 2`).

4. **Narrow the coordinate-method exception handling.**
   In `EyeTracker._eyeTrackerToDisplayCoords` / `_displayToEyeTrackerCoords`, replace the bare
   `except Exception` with `except (AttributeError, TypeError)` (+ a one-time debug log), so a *real*
   error isn't silently swallowed into a raw-pixel fallback. Keep the no-display passthrough behaviour
   and the existing `test_eyetracker_coords.py` passing.

5. **Remove the stale `pyproject.toml` comment** above `[tool.mypy]` ("ENABLED FROM PHASE 1 … not run in
   Phase 0 CI") — obsolete now that the core is implemented.

6. **Documentation.** Document the `(0,0)`/no-gaze behaviour **prominently in `README.md`** (Limitations)
   and in `docs/implementation_notes.md`, so users know origin-sentinel samples are dropped as invalid.
   Also commit the doc-consistency fixes already in the working tree (the `transforms.py` stale-reference
   corrections in `DEVELOPMENT_PLAN.md` / `ARCHITECTURE.md`).

**Acceptance criteria.**
- The reconnect test exercises the real EOF → reconnect path and asserts reconnection + stable thread
  count; passes in CI (PsychoPy-free).
- The coverage gate measures the full PsychoPy-free core (`eyetribe_client`, `frames`, `time_sync`,
  `calibration`, `validation`, `mock_server`) at ≥ 90%, green on `windows-latest`.
- A `(0,0)` combined gaze yields `status = 2` (asserted); README + implementation notes document it.
- Coordinate methods catch only `(AttributeError, TypeError)`; stale `pyproject` comment removed.
- `ruff`/`black`/`isort`/`mypy` clean; full CI suite (`-m "not hardware and not iohub"`) green.
**Tests.** Rewritten reconnect test; `(0,0)` validity test; broadened coverage gate satisfied; existing
suite stays green. (The host-only `iohub` launchHubServer test is unaffected.)

### Phase 11 — `[HARDWARE]` validation on the ET1000
**Objective.** Run the Phase 8 validation tooling on the real ET1000 (after the Phase 9 fixes), record
accuracy / precision / timing, capture a calibrated golden frame, and reconcile. (The release tag is
**not** here — it lands at the end of Phase 12.)
**Prerequisite.** Phase 10 merged (Phase 9 before it). **Environment:** Windows + Eye Tribe Server + ET1000.
**Steps (human-run; each produces a recorded artifact in `docs/hardware_validation.md`).**
- **11a** `stream_demo.py --real` — gaze dot tracks the eyes (screen recording / screenshots).
- **11b** `calibration_demo.py --real` — 9-point calibration completes; accuracy reported; redo works;
  `calibration_result.json` saved.
- **11c** `validation_experiment.py --real` — record gaze to known targets; compute accuracy
  (mean offset °), precision (RMS), and a stimulus-onset-to-gaze timing figure; write the metrics table.
- **11d** Capture a **calibrated** golden frame (`--capture-frame`); reconcile any real-frame differences
  into `frames.py` + the mock + `REFERENCES.md` (§2 procedure); confirm the mock-based CI still passes.
**Acceptance criteria.**
- 11a–11c run on the ET1000; metrics recorded (ET-class typical ≈ 0.5–1°); timing characterized.
- Calibrated golden frame captured and reconciled; CI suite still green.
**Tests.** Manual; evidence in `REPORT.md` + `docs/hardware_validation.md`.

### Phase 12 — Backlog cleanup & release
**Objective.** Clear the accumulated minor / cosmetic items in `docs/BACKLOG.md` in one pass, then cut
the `v1.0.0` release. Software + CI only — no hardware.
**Prerequisite.** Phase 11 hardware validation recorded (so the device is known-good before release).
**Steps.**
- **12a** Work through every **Open** item in `docs/BACKLOG.md`; for each, make the change, keep the
  suite green, and move it to the **Done** section with its resolving commit. If an item is judged not
  worth doing, record that decision in the backlog instead of deleting it silently.
- **12b** Final pre-release checks: `ruff`/`black`/`isort`/`mypy` clean; full mock-based CI
  (`-m "not hardware and not iohub"`) green; `CHANGELOG.md` finalized for `v1.0.0` (move `[Unreleased]`
  entries under the version heading with the date).
- **12c** Tag **`v1.0.0`** — `release.yml` builds the wheel and attaches it to the GitHub Release.
**Acceptance criteria.**
- `docs/BACKLOG.md` Open list is empty (every item resolved or explicitly deferred with a reason).
- Lint/type/test all green; `CHANGELOG.md` carries a dated `v1.0.0` section.
- `v1.0.0` tagged; GitHub Release created with the attached wheel.
**Tests.** Whatever each backlog item requires + the full mock-based suite green.

---

## 8. `[HARDWARE]` manual test checklists (self-contained)

Full versions in `docs/hardware_validation.md`; each is one script under `tests/manual/`. Ordered so
failures localize.

1. **Server reachable** — Eye Tribe Server running; `smoke_socket.py` connects to `:6555`; `get` returns
   `framerate`, `screenresw/h`, `trackerstate`. *Pass:* values returned, `trackerstate == 0`.
2. **Stream** — `set push`; receive ≥ 100 frames. *Pass:* rate ≈ 30 Hz, plausible gaze pixels, sane
   `state`; one frame committed as golden fixture.
3. **Heartbeat endurance** — stream 60 s with heartbeats. *Pass:* no disconnect.
4. **Plugin stream** — `stream_demo.py` gaze dot tracks the eyes. *Pass:* dot follows gaze.
5. **Calibration** — `calibration_demo.py` 9-point. *Pass:* completes, accuracy reported, redo works.
6. **Accuracy / precision / timing** — `11c`. *Pass:* metrics recorded.

Each item records device serial, Eye Tribe Server version, Windows build, date, agent/operator, result,
and evidence path.

---

## 9. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Eye Tribe Server won't install/run on the current Windows build | Med | High | Run the 8a smoke logic **first, before Phase 0** (it needs only a socket). If it fails, the project is blocked at the source — surface immediately; no further work until streaming is confirmed. |
| `EyeTrackerDevice` API differs from §3/MouseGaze assumptions in PsychoPy 2026.1.3 | Low | Med | Phase 0 reads the actual installed source into `REFERENCES.md`; integration tests run a real ioHub process. |
| Real frame schema differs from §3 | Low | Med | §3 is documentation-backed; the smoke-socket capture + Phase 11 reconcile a real frame via the §2 discrepancy procedure. |
| 30 Hz too low for the intended paradigm | Known | Med (scientific) | Documented limitation; not a code defect. raw/avg both exposed. |
| Pupil size misread as mm | Low | Low | Explicitly documented arbitrary units; no conversion. |
| Threading races (reader/heartbeat/poll) | Med | Med | Thread-safe bounded buffer, teardown leak assertions, a streaming stress test in CI. |
| ioHub YAML filename mismatch in 2026.1.3 | Low | Med | Filenames pinned from the in-tree GazePoint device; a Phase 0 loader test fails CI if either name is not found (§5.2). |

---

## 10. Sequencing

- **Pre-Phase 0 gate:** run the smoke-socket logic to confirm the Server + ET1000 actually stream
  (done 2026-06-15). Cheapest possible de-risk of the whole effort.
- Phases 0→…→9 are linear and complete. **Phase 10** (post-review fixes & hardening) precedes
  **Phase 11** (hardware validation), which precedes **Phase 12** (backlog cleanup & release): full
  chain 0→…→9 → 10 → 11 → 12. Phase 11 runs the Phase 8 tooling on the ET1000; Phase 12 clears
  `docs/BACKLOG.md` and tags `v1.0.0`.

---

## 11. Definition of Done (project)

A tagged GPL-3.0 **GitHub Release** (`v1.0.0`, end of Phase 12) with an attached wheel (no PyPI) such
that: a researcher with an ET1000 and the Eye Tribe Server on Windows installs the wheel into Standalone
PsychoPy 2026.1.3, selects **Eye Tribe** in the Builder Eyetracker component, runs PsychoPy-driven
9-point calibration, and records binocular **raw** gaze samples **in the experiment's display units**
(via the Phase 9 coordinate fix, with the Phase 10 validity/reliability hardening) on the PsychoPy
timebase with documented accuracy/precision — with the
full mock-based test suite (including the `launchHubServer` regression test) green in Windows CI and the
hardware validation recorded in `docs/hardware_validation.md`.
