# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Permanent launchHubServer regression test — host-only, NOT in the CI gate.

Run this on the Windows machine with PsychoPy 2026.1.3 + a display:

    pytest -m iohub -q

Prerequisite: the editable install must be visible to the ioHub subprocess.
Create the .pth file once:

    $pth = "$env:APPDATA\\psychopy3\\packages\\Python310\\site-packages\\"
    Set-Content ($pth + "psychopy_eyetracker_eyetribe_dev.pth") $repo

See docs/HUMAN_TASKS.md Phase 9 for the full command.

What this test verifies (Phase 9 acceptance criteria):
- The ioHub subprocess discovers and loads EyeTribeEyeTracker via the entry-point group.
- setConnectionState(True) connects to the mock Eye Tribe server.
- At least one event flows through to getEvents() (event-pipeline check).
- getPosition() returns a non-raw-pixel value — i.e. the Phase 9 coordinate fix
  is active.  The mock emits gaze at screen centre (960 px on a 1920-wide screen).
  The old broken code returned (960, ...) directly; the fix routes through
  _pixel2DisplayCoord which maps screen centre to approximately (0, ...) in any
  Y-up unit system.  We assert abs(gx) < 500 to distinguish fixed from broken.
"""

from __future__ import annotations

import time

import pytest

# Skip the entire module when PsychoPy is not installed
psychopy = pytest.importorskip("psychopy", reason="PsychoPy not installed")

pytestmark = pytest.mark.iohub


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_iohub_config(port: int) -> dict:
    return {
        "eyetracker.hw.eyetribe.EyeTracker": {
            "name": "tracker",
            "host": "127.0.0.1",
            "port": port,
            "gaze_source": "raw",
            "calibration": {"target_count": 9},
        }
    }


# ── test ──────────────────────────────────────────────────────────────────────


def test_launchhub_against_mock_events_and_position() -> None:
    """launchHubServer records events and getPosition() is not raw pixels."""
    from psychopy.iohub import launchHubServer

    from psychopy_eyetracker_eyetribe.mock.mock_server import MockEyeTribeServer

    mock = MockEyeTribeServer(port=0, frame_rate=30, heartbeat_interval_ms=3000)
    mock.start()
    io = None
    try:
        io = launchHubServer(**_make_iohub_config(mock.port))
        tracker = io.devices.tracker

        # Must connect explicitly — there is no auto_connect in the YAML.
        connected = tracker.setConnectionState(True)
        assert connected, "Could not connect to the mock Eye Tribe server"

        tracker.setRecordingState(True)
        time.sleep(1.2)  # record ≥ 1 s — should yield ~36 frames at 30 Hz
        tracker.setRecordingState(False)

        events = tracker.getEvents()
        assert events, (
            "No events from getEvents() — event pipeline not working. "
            "Check that the .pth dev step is done and the entry-point group resolves."
        )

        pos = tracker.getPosition()
        assert pos is not None, (
            "getPosition() returned None — no valid gaze sample was recorded. "
            "Check that the mock is running and setConnectionState succeeded."
        )

        # Coordinate-fix check.
        # Mock emits gaze at screen centre (960, 540 px on a 1920×1080 screen).
        # Phase 9 fix: _pixel2DisplayCoord maps (960, 540) → (0, 0) in any Y-up
        # unit system (pix / norm / height), or returns (0, 0) when no unit type
        # is configured — either way, gx ≈ 0.
        # Broken pre-Phase-9 behaviour: getBounds() raised → fallback passthrough
        # returned (960, 540) → gx ≈ 960.
        gx, _gy = pos
        assert abs(gx) < 500, (
            f"getPosition() x={gx!r} looks like raw screen pixels (expected ~0 for "
            "screen centre); the Phase 9 coordinate fix may not be active."
        )

    finally:
        if io is not None:
            try:
                io.quit()
            except Exception:
                pass
        mock.stop()
