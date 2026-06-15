"""Shared pytest fixtures."""

from __future__ import annotations

import threading

import pytest

from psychopy_eyetracker_eyetribe.mock.mock_server import MockEyeTribeServer


@pytest.fixture
def mock_server():
    """Start a MockEyeTribeServer on a free port, yield it, then stop and assert no leaks."""
    srv = MockEyeTribeServer(port=0, frame_rate=30, heartbeat_interval_ms=3000)
    srv.start()
    yield srv
    srv.stop()

    # Assert no server-side threads leaked (daemon threads are excluded from this check
    # because Python names them; we just verify the accept thread is gone).
    live = {t.name for t in threading.enumerate()}
    assert "MockEyeTribeServer-accept" not in live, "MockEyeTribeServer accept thread leaked"
