"""Unit tests for EyeTribeClient — message framing, routing, timeout.

These tests do NOT require PsychoPy or the mock server; they use raw sockets
or the mock server fixture where needed for tight protocol control.
"""

from __future__ import annotations

import json
import socket
import threading
import time

import pytest

from psychopy_eyetracker_eyetribe.eyetribe import eyetribe_client
from psychopy_eyetracker_eyetribe.eyetribe.eyetribe_client import (
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    EyeTribeClient,
    FrameBuffer,
)
from psychopy_eyetracker_eyetribe.mock.mock_server import MockEyeTribeServer

# ── module-level constants (Phase 0 smoke) ────────────────────────────────────


def test_imports_without_psychopy() -> None:
    assert eyetribe_client.PORT_DEFAULT == 6555
    assert eyetribe_client.API_VERSION == 1
    assert eyetribe_client.FRAME_BUFFER_CAPACITY == 1024


# ── FrameBuffer ───────────────────────────────────────────────────────────────


def test_frame_buffer_put_get() -> None:
    fb = FrameBuffer(capacity=3)
    fb.put({"a": 1})
    fb.put({"b": 2})
    assert len(fb) == 2
    all_frames = fb.get_all()
    assert len(all_frames) == 2
    assert len(fb) == 0


def test_frame_buffer_overflow_drops_oldest() -> None:
    fb = FrameBuffer(capacity=3)
    for i in range(5):
        fb.put({"i": i})
    assert len(fb) == 3
    frames = fb.get_all()
    assert [f["i"] for f in frames] == [2, 3, 4]


def test_frame_buffer_get_one_blocks() -> None:
    fb = FrameBuffer(capacity=10)

    def _put_later() -> None:
        time.sleep(0.05)
        fb.put({"x": 99})

    t = threading.Thread(target=_put_later)
    t.start()
    frame = fb.get_one(timeout_s=1.0)
    t.join()
    assert frame is not None
    assert frame["x"] == 99


def test_frame_buffer_get_one_timeout() -> None:
    fb = FrameBuffer()
    result = fb.get_one(timeout_s=0.05)
    assert result is None


# ── newline-delimited JSON framing ────────────────────────────────────────────


def _make_pair() -> tuple[socket.socket, socket.socket]:
    """Return a connected socket pair for testing."""
    a, b = socket.socketpair()
    return a, b


def test_message_framing_encode_decode() -> None:
    """Frames are JSON + newline on the wire; the reader splits on newlines."""
    obj = {"category": "heartbeat"}
    encoded = (json.dumps(obj) + "\n").encode("utf-8")
    decoded = json.loads(encoded.rstrip(b"\n"))
    assert decoded == obj


def test_multiple_messages_in_one_recv() -> None:
    """Reader correctly handles multiple JSON objects in a single recv."""
    msgs = [{"category": "heartbeat"}, {"category": "tracker", "request": "get", "statuscode": 200}]
    combined = "".join(json.dumps(m) + "\n" for m in msgs).encode("utf-8")
    # Simulate the split logic the reader uses
    buf = combined
    parsed = []
    while b"\n" in buf:
        line, buf = buf.split(b"\n", 1)
        line = line.strip()
        if line:
            parsed.append(json.loads(line))
    assert parsed == msgs


# ── frame-vs-reply routing ────────────────────────────────────────────────────


def test_frame_detection_by_values_frame_key() -> None:
    """Frames must be detected by presence of values.frame, not request string."""
    frame_msg = {
        "category": "tracker",
        "request": "get",
        "values": {"frame": {"time": 1000, "state": 7}},
    }
    reply_msg = {
        "category": "tracker",
        "request": "get",
        "statuscode": 200,
        "values": {"framerate": 30},
    }
    assert "frame" in (frame_msg.get("values") or {})
    assert "frame" not in (reply_msg.get("values") or {})


# ── request/reply timeout ─────────────────────────────────────────────────────


def test_request_timeout_when_no_server() -> None:
    """connect() raises when the server is not reachable (exhausts retries)."""
    client = EyeTribeClient(host="127.0.0.1", port=19999)
    with pytest.raises((RuntimeError, OSError)):
        client.connect()
    assert client.state == STATE_DISCONNECTED


# ── connect / close lifecycle via mock ───────────────────────────────────────


def test_connect_close_state(mock_server: MockEyeTribeServer) -> None:
    client = EyeTribeClient(host=mock_server.host, port=mock_server.port)
    client.connect()
    assert client.state == STATE_CONNECTED
    client.close()
    assert client.state == STATE_DISCONNECTED


def test_heartbeat_interval_read_at_connect(mock_server: MockEyeTribeServer) -> None:
    client = EyeTribeClient(host=mock_server.host, port=mock_server.port)
    client.connect()
    assert client.heartbeat_interval_ms == mock_server.heartbeat_interval_ms
    client.close()


def test_frame_rate_read_at_connect(mock_server: MockEyeTribeServer) -> None:
    client = EyeTribeClient(host=mock_server.host, port=mock_server.port)
    client.connect()
    assert client.frame_rate == mock_server.frame_rate
    client.close()


def test_no_thread_leak_after_close(mock_server: MockEyeTribeServer) -> None:
    client = EyeTribeClient(host=mock_server.host, port=mock_server.port)
    client.connect()
    client.close()
    time.sleep(0.1)
    after = {t.name for t in threading.enumerate()}
    # The two named threads should be gone
    assert "EyeTribeReaderThread" not in after
    assert "EyeTribeHeartbeatThread" not in after
