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
- At least one event flows through to getEvents() (event-pipeline check).
- getPosition() returns coordinates inside the active Display bounds (coordinate-fix check).
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
    """launchHubServer records events and getPosition() is inside Display bounds."""
    from psychopy.iohub import launchHubServer

    from psychopy_eyetracker_eyetribe.mock.mock_server import MockEyeTribeServer

    mock = MockEyeTribeServer(port=0, frame_rate=30, heartbeat_interval_ms=3000)
    mock.start()
    try:
        io = launchHubServer(**_make_iohub_config(mock.port))
        tracker = io.devices.tracker

        tracker.setRecordingState(True)
        time.sleep(1.2)  # record ≥ 1 s
        tracker.setRecordingState(False)

        events = tracker.getEvents()
        assert events, (
            "No events from getEvents() — event pipeline not working or "
            "coordinate conversion broke before events were emitted."
        )

        # getPosition() should return coordinates in the Display's unit space,
        # NOT raw pixel coords 0–1920.  For the default 'pix' unit at 1920×1080,
        # the bounds are (-960, -540) to (960, 540); the mock emits gaze near
        # centre (960, 540 px) which maps to roughly (0, 0) pix.
        pos = tracker.getPosition()
        assert pos is not None, "getPosition() returned None — no valid gaze recorded"

        display = io.devices.display
        left, top, right, bottom = (
            display.getConfiguration()["bounds"]["left"],
            display.getConfiguration()["bounds"]["top"],
            display.getConfiguration()["bounds"]["right"],
            display.getConfiguration()["bounds"]["bottom"],
        )
        gx, gy = pos
        assert left <= gx <= right, (
            f"getPosition() x={gx!r} outside Display bounds [{left}, {right}]; "
            "coordinate fix may not be working"
        )
        # Y bounds: bottom < top in Y-up space
        y_lo, y_hi = min(bottom, top), max(bottom, top)
        assert y_lo <= gy <= y_hi, (
            f"getPosition() y={gy!r} outside Display bounds [{y_lo}, {y_hi}]; "
            "coordinate fix may not be working"
        )

        io.quit()
    finally:
        mock.stop()
