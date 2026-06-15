# Phase 1 handoff prompt

Copy everything in the fenced block below to brief the Phase 1 coding agent.

---

````
You are implementing **Phase 1** of the `psychopy-eyetracker-eyetribe` project (a native PsychoPy
ioHub eye-tracker plugin for The Eye Tribe ET1000). The repo already has a complete, hardware-verified
Phase 0 scaffold. Your job is the **transport layer + mock server only** — pure software, no hardware,
no PsychoPy.

## Read these first (in order), and treat them as authoritative
1. `docs/DEVELOPMENT_PLAN.md` — the contract. Read §0 (pinned decisions), §3 (Eye Tribe wire format),
   §4 (architecture), §5 (repo structure), §6 (conventions/CI/reporting), and the **Phase 1** section.
   It contains NO open design decisions — implement what it says; do not redesign.
2. `docs/REFERENCES.md` — facts verified against the real device/PsychoPy. Pay special attention to the
   "Eye Tribe Tracker API" CORRECTION items (they override older assumptions):
   - **Frame `time` is a MONOTONIC millisecond counter (relative, ~uptime) — NOT Unix epoch.** A
     separate `timestamp` field is the wall-clock string. (Time-sync itself is Phase 4 — for Phase 1
     just carry the values through.)
   - **In push mode the Server sends frames as `{"category":"tracker","request":"get","values":{"frame":{…}}}`.**
     The `request` is `"get"`, NOT `"push"`. The reader MUST detect frame messages by the **presence of
     `values.frame`**, never by the request string.
3. `tests/manual/smoke_socket.py` and `tests/manual/_captured_frame.json` — a real connect/stream
   transcript and a real (uncalibrated) frame. Use them as ground truth for message shapes and to drive
   the mock's synthesized frames.
4. The stubs you will implement: `psychopy_eyetracker_eyetribe/eyetribe/eyetribe_client.py` and
   `psychopy_eyetracker_eyetribe/mock/mock_server.py` (they already declare the intended constants and
   method signatures). The placeholder tests: `tests/integration/test_client_against_mock.py`,
   `tests/unit/test_client.py`, and the `mock_server` fixture in `tests/conftest.py`.

## Scope — implement ONLY these
- `psychopy_eyetracker_eyetribe/mock/mock_server.py` — `MockEyeTribeServer`:
  - Binds a configurable port (default an ephemeral free port); speaks the §3 protocol: replies to
    `tracker set version`, `tracker get <keys>` (return `heartbeatinterval`, `framerate` (default 30),
    `screenresw`/`screenresh` (default 1920/1080), `trackerstate` (0), `iscalibrated`), and
    `tracker set push=true`.
  - In push mode, streams synthesized frames at a configurable rate (default 30 Hz) framed as
    `{"category":"tracker","request":"get","values":{"frame":{…}}}` with a monotonic-ms `time` counter
    and the field shape from `_captured_frame.json`/§3. Configurable gaze model: fixed point, linear
    sweep, and injectable blink / `STATE_TRACKING_LOST` segments.
  - Enforces heartbeats: if no `{"category":"heartbeat"}` arrives within `heartbeatinterval`
    (default 3000 ms), drop the client connection.
  - Provides a scriptable calibration responder that returns a configurable `calibresult` (so Phase 5
    can drive it later). Context-manager (`__enter__/__exit__`) + `start()`/`stop()`.
- `psychopy_eyetracker_eyetribe/eyetribe/eyetribe_client.py` — `EyeTribeClient`:
  - `connect()` performs §3 steps 1–5 (open socket → `set version`=1 → `get` session params →
    `set push`=true → start heartbeat thread). `close()` tears everything down cleanly.
  - Reconnect policy: 3 attempts × 0.5 s backoff, then state `DISCONNECTED` (use the module constants).
  - Request/reply with a 2 s timeout (match replies to requests by `category`/`request`).
  - `ReaderThread`: reads newline-delimited JSON; **detects frames by `values.frame` presence** and
    pushes the **raw frame dict** into a thread-safe bounded `FrameBuffer` (capacity 1024, drop oldest
    on overflow). Non-frame messages are routed to the request/reply waiter.
  - `HeartbeatThread`: sends `{"category":"heartbeat"}` every `heartbeatinterval / 2` ms (interval read
    at connect).
  - Structured `logging` (module logger).
- Tests: replace the placeholders.
  - `tests/integration/test_client_against_mock.py`: lifecycle (connect→stream→close), frame rate within
    ±10% of configured, heartbeat keeps link alive ≥ 30 s, stopping heartbeats → mock disconnect that the
    client detects/reports/attempts reconnect, FrameBuffer overflow drops oldest.
    (Speed the long timing tests up by configuring the mock's rate/heartbeat interval.)
  - `tests/unit/test_client.py`: message framing (newline-delimited JSON encode/decode), request/reply
    timeout, frame-vs-reply routing.
  - `tests/conftest.py`: implement the `mock_server` fixture (start on a free port, yield, stop; assert
    no leaked threads/sockets on teardown).

## Do NOT touch (later phases)
- `frames.py` (Phase 2 — do **not** parse frames into dataclasses here; buffer raw dicts),
  `transforms.py`/`time_sync.py` (Phase 4), `calibration.py`/`runSetupProcedure` (Phase 5),
  `eyetracker.py` (Phase 3), `settings.py` (Phase 6). Leave them as stubs.
- Do not change pinned decisions in `DEVELOPMENT_PLAN.md`/`REFERENCES.md`. If you find a genuine
  discrepancy with the device protocol, follow the discrepancy procedure (plan §2): record it in
  `REFERENCES.md` and note it in `REPORT.md` rather than silently diverging.

## Engineering constraints (from §6)
- **PsychoPy-free**: `eyetribe_client.py` and everything under `mock/` must have ZERO PsychoPy imports
  (standard library only). Fully unit-testable without PsychoPy.
- Full type hints; must pass `mypy --strict` on the PsychoPy-free core. **Enable the mypy + coverage
  gates in `.github/workflows/ci.yml` now** (Phase 0 deferred them): add a `mypy` step over the core
  modules listed in `[tool.mypy]`, and a coverage step requiring **≥ 90%** on `eyetribe_client.py` and
  `mock/mock_server.py` (the other core modules are still stubs — ratchet them in as their phases land).
- `ruff`/`black`/`isort` clean (configs already in `pyproject.toml`, line length 100).
- Conventional Commits; work on a branch **`phase-1-transport`**; open a PR titled `Phase 1: Transport
  layer + Mock server` whose description restates the Phase 1 acceptance criteria as a ticked checklist
  with evidence (test output + coverage %).
- Append a **Phase 1** section to `docs/REPORT.md` per the template in §6.

## Acceptance criteria (Phase 1 is done when all hold)
- Client connects to the mock, enables push, and receives frames within ±10% of the configured rate.
- Heartbeat keeps the link alive ≥ 30 s; stopping heartbeats triggers a mock disconnect the client
  detects, reports, and (per policy) attempts to reconnect.
- No leaked threads/sockets after `close()` (asserted in teardown).
- `eyetribe_client.py` and `mock/` contain zero PsychoPy imports.
- `ruff`/`black`/`isort`/`mypy` clean; `pytest -m "not hardware" -q` green; coverage ≥ 90% on the two
  new modules. CI green on `windows-latest`.

## Dev/test commands (any Python 3.10 env; Phase 1 needs no PsychoPy)
```
pip install -e .[dev]
ruff check .
black --check .
isort --check-only .
mypy
pytest -m "not hardware" -q
```

Deliver a single PR for Phase 1. Keep the diff scoped to the files listed above plus `ci.yml` and the
`REPORT.md` entry.
````
