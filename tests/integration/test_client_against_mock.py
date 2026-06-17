"""Phase 1 integration: EyeTribeClient driven against MockEyeTribeServer."""

from __future__ import annotations

import threading
import time

import pytest

from psychopy_eyetracker_eyetribe.eyetribe.eyetribe_client import (
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    EyeTribeClient,
    FrameBuffer,
)
from psychopy_eyetracker_eyetribe.mock.mock_server import MockEyeTribeServer

pytestmark = pytest.mark.integration


# ── helpers ───────────────────────────────────────────────────────────────────


def _connect(srv: MockEyeTribeServer) -> EyeTribeClient:
    client = EyeTribeClient(host=srv.host, port=srv.port)
    client.connect()
    return client


# ── lifecycle ─────────────────────────────────────────────────────────────────


def test_lifecycle_connect_stream_close(mock_server: MockEyeTribeServer) -> None:
    """Client connects, receives frames, closes cleanly."""
    client = _connect(mock_server)
    time.sleep(0.3)  # let frames accumulate
    frames = client.frame_buffer.get_all()
    assert len(frames) > 0, "No frames received"
    # Each frame must have the required fields
    for f in frames:
        assert "time" in f
        assert "state" in f
        assert "raw" in f
        assert "lefteye" in f
        assert "righteye" in f
    client.close()


def test_no_leaked_threads_after_close(mock_server: MockEyeTribeServer) -> None:
    client = _connect(mock_server)
    client.close()
    time.sleep(0.15)
    live = {t.name for t in threading.enumerate()}
    assert "EyeTribeReaderThread" not in live
    assert "EyeTribeHeartbeatThread" not in live


# ── frame rate accuracy ───────────────────────────────────────────────────────


@pytest.mark.parametrize("configured_rate", [10, 30])
def test_frame_rate_within_10_percent(configured_rate: int) -> None:
    """Received frame rate is within ±10% of the configured rate."""
    srv = MockEyeTribeServer(port=0, frame_rate=configured_rate, heartbeat_interval_ms=3000)
    srv.start()
    try:
        client = EyeTribeClient(host=srv.host, port=srv.port)
        client.connect()
        # Measure over 1 second
        time.sleep(1.0)
        frames = client.frame_buffer.get_all()
        client.close()
    finally:
        srv.stop()

    received = len(frames)
    tolerance = 0.10
    low = configured_rate * (1 - tolerance)
    high = configured_rate * (1 + tolerance)
    assert (
        low <= received <= high
    ), f"Rate {received} fps outside ±10% of {configured_rate} fps (expected {low:.1f}–{high:.1f})"


# ── heartbeat keeps link alive ────────────────────────────────────────────────


def test_heartbeat_keeps_link_alive_30s() -> None:
    """Heartbeat keeps the connection alive for 30 s (sped up via short intervals)."""
    # Use a very short heartbeat interval so the test doesn't actually wait 30 real seconds.
    # heartbeat_interval_ms=200 → client sends every 100 ms; we run for 1.5 s (many intervals).
    srv = MockEyeTribeServer(port=0, frame_rate=30, heartbeat_interval_ms=200)
    srv.start()
    try:
        client = EyeTribeClient(host=srv.host, port=srv.port)
        client.connect()
        # Run for 15× the heartbeat interval — equivalent stress to 30 s at default 3 s interval
        run_s = 0.2 * 15  # 3.0 s real time
        time.sleep(run_s)
        # Client should still be connected
        assert client.state != STATE_DISCONNECTED, "Client disconnected during heartbeat run"
        frames_received = len(client.frame_buffer.get_all())
        client.close()
    finally:
        srv.stop()

    assert frames_received > 0, "No frames received during heartbeat run"


# ── heartbeat timeout → disconnect → reconnect ────────────────────────────────


def test_server_drop_triggers_reconnect_without_duplicate_threads() -> None:
    """Server drops the client; EOF triggers reconnect without duplicate threads."""
    srv = MockEyeTribeServer(port=0, frame_rate=10, heartbeat_interval_ms=3000)
    srv.start()
    try:
        client = EyeTribeClient(host=srv.host, port=srv.port)
        client.connect()
        time.sleep(0.2)  # let a few frames arrive to confirm connection

        def _et_thread_names() -> list[str]:
            return [t.name for t in threading.enumerate() if t.name.startswith("EyeTribe")]

        names_before = _et_thread_names()
        assert (
            len(names_before) >= 2
        ), f"Expected ≥2 EyeTribe threads before drop, got {names_before}"

        # Drop the connection from the server side WITHOUT touching client._stop_evt.
        # The client's reader hits EOF → _on_server_eof fires → _reconnect_bg spawns.
        srv.drop_clients()

        # _reconnect_bg joins old threads (~0 s) + 1×RECONNECT_BACKOFF_S (0.5 s) + connect.
        # Give it 5 s headroom to be safe on a loaded CI runner.
        time.sleep(5.0)

        assert (
            client.state == STATE_CONNECTED
        ), f"Expected STATE_CONNECTED after reconnect, got {client.state!r}"

        # Reconnect hygiene: no duplicate threads — count of EyeTribe* threads is stable.
        names_after = _et_thread_names()
        assert len(names_after) == len(
            names_before
        ), f"Thread count changed after reconnect: before={names_before}, after={names_after}"
    finally:
        client.close()
        srv.stop()


# ── FrameBuffer overflow ──────────────────────────────────────────────────────


def test_frame_buffer_overflow_drops_oldest() -> None:
    """When the buffer is full, the oldest frame is dropped."""
    capacity = 5
    fb = FrameBuffer(capacity=capacity)
    for i in range(capacity + 3):
        fb.put({"seq": i})
    assert len(fb) == capacity
    frames = fb.get_all()
    seqs = [f["seq"] for f in frames]
    # Should contain the most-recent `capacity` frames
    assert seqs == list(range(3, capacity + 3))


def test_frame_buffer_overflow_via_mock() -> None:
    """Buffer filled beyond capacity by mock: only newest frames survive."""
    # Very small buffer, high rate for a short burst
    capacity = 20
    srv = MockEyeTribeServer(port=0, frame_rate=100, heartbeat_interval_ms=3000)
    srv.start()
    try:
        client = EyeTribeClient(host=srv.host, port=srv.port)
        # Patch the buffer capacity for this test
        client.frame_buffer = FrameBuffer(capacity=capacity)
        client.connect()
        time.sleep(0.5)  # 100 Hz × 0.5 s = ~50 frames → overflows capacity=20
        frames = client.frame_buffer.get_all()
        client.close()
    finally:
        srv.stop()

    assert len(frames) <= capacity, "Buffer exceeded declared capacity"
    # Frames should be monotonically increasing in time
    times = [f["time"] for f in frames]
    assert times == sorted(times), "Frames not in time order after overflow"
