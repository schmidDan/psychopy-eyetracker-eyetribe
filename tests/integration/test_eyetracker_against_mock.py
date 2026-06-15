"""Phase 3 integration: EyeTracker device driven against MockEyeTribeServer.

Tests _poll(), BinocularEyeSampleEvent construction, fixation-event transitions,
validity propagation, gaze-source config, and recording-state toggling — all
without a running ioHub subprocess (the _iohub_server is not needed for these
device-level tests; the full launchHubServer path is exercised manually or in CI
with a PsychoPy window available).
"""

from __future__ import annotations

import time
from typing import Any

import pytest

pytestmark = pytest.mark.integration

psychopy = pytest.importorskip("psychopy", reason="PsychoPy not installed")


# ── imports that require PsychoPy ─────────────────────────────────────────────

from psychopy.iohub.constants import EventConstants, EyeTrackerConstants  # noqa: E402
from psychopy.iohub.devices.eyetracker import EyeTrackerDevice  # noqa: E402

from psychopy_eyetracker_eyetribe.eyetribe.eyetracker import EyeTracker  # noqa: E402
from psychopy_eyetracker_eyetribe.mock.mock_server import (  # noqa: E402
    MockEyeTribeServer,
    make_lost_segment,
)

ET_UNDEFINED = EyeTrackerConstants.UNDEFINED

# ── minimal dconfig factory ───────────────────────────────────────────────────


def _make_dconfig(port: int, gaze_source: str = "raw") -> dict[str, Any]:
    return {
        "name": "tracker",
        "event_buffer_length": 1024,
        "device_number": 0,
        "manufacturer_name": "The Eye Tribe",
        "model_name": "ET1000",
        "auto_report_events": False,
        "host": "127.0.0.1",
        "port": port,
        "api_version": 1,
        "gaze_source": gaze_source,
        "runtime_settings": {"sampling_rate": "auto", "track_eyes": "BINOCULAR"},
        "calibration": {"target_count": 9},
        "device_timer": {"interval": 0.005},
        "monitor_event_types": [
            "BinocularEyeSampleEvent",
            "FixationStartEvent",
            "FixationEndEvent",
        ],
    }


# ── tracker fixture ───────────────────────────────────────────────────────────


@pytest.fixture
def mock_srv():
    srv = MockEyeTribeServer(port=0, frame_rate=30, heartbeat_interval_ms=3000)
    srv.start()
    yield srv
    srv.stop()


@pytest.fixture
def tracker(mock_srv):
    """Construct EyeTracker, connect to mock, yield, then clean up singleton."""
    EyeTrackerDevice._INSTANCE = None
    t = EyeTracker(dconfig=_make_dconfig(mock_srv.port))
    t.setConnectionState(True)
    yield t
    t._close()
    EyeTrackerDevice._INSTANCE = None


# ── helpers ───────────────────────────────────────────────────────────────────


def _drain_events(tracker: EyeTracker) -> list:
    return list(tracker._native_event_buffer)


def _sample_events(events: list) -> list:
    return [e for e in events if e[4] == EventConstants.BINOCULAR_EYE_SAMPLE]


def _fixstart_events(events: list) -> list:
    return [e for e in events if e[4] == EventConstants.FIXATION_START]


def _fixend_events(events: list) -> list:
    return [e for e in events if e[4] == EventConstants.FIXATION_END]


# ── connection & recording ────────────────────────────────────────────────────


def test_is_connected_after_setConnectionState(tracker):
    assert tracker.isConnected()


def test_recording_state_toggle(tracker):
    assert not tracker.isRecordingEnabled()

    tracker.setRecordingState(True)
    assert tracker.isRecordingEnabled()
    assert tracker.isReportingEvents()

    tracker.setRecordingState(False)
    assert not tracker.isRecordingEnabled()
    assert not tracker.isReportingEvents()


# ── sample event generation ───────────────────────────────────────────────────


def test_sample_events_generated_on_poll(tracker):
    tracker.setRecordingState(True)
    time.sleep(0.4)  # ~12 frames at 30 Hz
    tracker._poll()

    samples = _sample_events(_drain_events(tracker))
    assert len(samples) >= 5, f"Expected ≥5 sample events, got {len(samples)}"


def test_no_events_when_not_recording(tracker):
    # recording is off by default in fixture
    time.sleep(0.2)
    tracker._poll()

    events = _drain_events(tracker)
    assert len(events) == 0, "Events generated while not recording"


def test_no_events_after_recording_stopped(tracker):
    tracker.setRecordingState(True)
    time.sleep(0.1)
    tracker._poll()
    tracker._native_event_buffer.clear()

    tracker.setRecordingState(False)
    time.sleep(0.2)
    tracker._poll()

    events = _drain_events(tracker)
    assert len(events) == 0, "Events generated after recording stopped"


# ── event shape ───────────────────────────────────────────────────────────────


def test_binocular_sample_has_50_fields(tracker):
    tracker.setRecordingState(True)
    time.sleep(0.15)
    tracker._poll()

    samples = _sample_events(_drain_events(tracker))
    assert samples, "No samples"
    for s in samples:
        assert len(s) == 50, f"BinocularEyeSampleEvent has {len(s)} fields, expected 50"


def test_binocular_sample_field_ranges(tracker):
    """Gaze coordinates, pcenter (0-1), and pupil size should be in plausible ranges."""
    tracker.setRecordingState(True)
    time.sleep(0.2)
    tracker._poll()

    samples = _sample_events(_drain_events(tracker))
    assert samples

    # Mock emits gaze around centre (960, 540) on a 1920×1080 screen.
    # Coordinates pass through as pixels in Phase 3 (no display device).
    for s in samples:
        if s[49] == 0:  # valid sample
            lgx, lgy = s[11], s[12]
            assert -2000 < lgx < 2000, f"left_gaze_x={lgx} out of range"
            assert -2000 < lgy < 2000, f"left_gaze_y={lgy} out of range"

            # eye_cam_x/y = pcenter (normalized 0-1)
            lpcx, lpcy = s[14], s[15]
            assert 0.0 <= lpcx <= 1.0, f"left_eye_cam_x={lpcx} outside [0, 1]"
            assert 0.0 <= lpcy <= 1.0, f"left_eye_cam_y={lpcy} outside [0, 1]"

            # pupil_measure1 = psize (arbitrary units, ~12-18 from mock)
            lpup = s[21]
            assert lpup > 0, f"left_pupil_measure1={lpup} not positive"

    # pupil_measure1_type should be EyeTrackerConstants.PUPIL_AREA
    for s in samples:
        assert s[22] == EyeTrackerConstants.PUPIL_AREA


def test_sample_timestamps_advance(tracker):
    """device_time (index 5) and iohub_time (index 7) should increase across samples."""
    tracker.setRecordingState(True)
    time.sleep(0.3)
    tracker._poll()

    samples = _sample_events(_drain_events(tracker))
    assert len(samples) >= 2

    device_times = [s[5] for s in samples]
    iohub_times = [s[7] for s in samples]
    assert device_times == sorted(device_times), "device_time not monotonically increasing"
    assert iohub_times[0] > 0, "iohub_time should be positive (PsychoPy clock)"
    assert iohub_times[-1] > iohub_times[0], "iohub_time not advancing"


# ── validity propagation ──────────────────────────────────────────────────────


def test_validity_propagation_tracking_lost():
    """Frames with STATE_TRACKING_LOST produce status=2 events."""
    EyeTrackerDevice._INSTANCE = None
    srv = MockEyeTribeServer(
        port=0,
        frame_rate=30,
        heartbeat_interval_ms=3000,
        segments=[make_lost_segment(start_s=0.0, duration_s=0.5)],
    )
    srv.start()
    try:
        t = EyeTracker(dconfig=_make_dconfig(srv.port))
        t.setConnectionState(True)
        t.setRecordingState(True)
        time.sleep(0.4)
        t._poll()
        samples = _sample_events(_drain_events(t))
    finally:
        t._close()
        EyeTrackerDevice._INSTANCE = None
        srv.stop()

    assert samples, "No samples"
    statuses = [s[49] for s in samples]
    assert 2 in statuses, "No invalid (status=2) samples found for tracking-lost frames"


def test_validity_propagation_valid_frames():
    """Normal frames (GAZE|EYES|PRESENCE) produce status=0 events."""
    EyeTrackerDevice._INSTANCE = None
    srv = MockEyeTribeServer(port=0, frame_rate=30, heartbeat_interval_ms=3000)
    srv.start()
    try:
        t = EyeTracker(dconfig=_make_dconfig(srv.port))
        t.setConnectionState(True)
        t.setRecordingState(True)
        time.sleep(0.3)
        t._poll()
        samples = _sample_events(_drain_events(t))
    finally:
        t._close()
        EyeTrackerDevice._INSTANCE = None
        srv.stop()

    assert samples
    statuses = [s[49] for s in samples]
    assert 0 in statuses, "No valid (status=0) samples found for normal frames"


# ── fixation events ───────────────────────────────────────────────────────────


def test_fixation_start_emitted_on_fix_transition(tracker):
    """FixationStartEvent is emitted when fix transitions False→True."""
    # The mock emits fix=True whenever state has GAZE bit set (normal frames).
    # First poll after reset: _last_fix=False, first frame fix=True → start event.
    tracker.setRecordingState(True)
    time.sleep(0.15)
    tracker._poll()

    events = _drain_events(tracker)
    fix_starts = _fixstart_events(events)
    assert len(fix_starts) >= 1, "No FixationStartEvent emitted"
    assert len(fix_starts[0]) == 29, f"FixationStartEvent has {len(fix_starts[0])} fields"


def test_fixation_end_emitted_on_fix_exit():
    """FixationEndEvent is emitted when fix transitions True→False (via lost segment)."""
    EyeTrackerDevice._INSTANCE = None
    # Normal frames for 0.1 s, then lost for 0.3 s (fix goes False)
    srv = MockEyeTribeServer(
        port=0,
        frame_rate=30,
        heartbeat_interval_ms=3000,
        segments=[make_lost_segment(start_s=0.15, duration_s=0.4)],
    )
    srv.start()
    try:
        t = EyeTracker(dconfig=_make_dconfig(srv.port))
        t.setConnectionState(True)
        t.setRecordingState(True)
        time.sleep(0.6)
        t._poll()
        events = _drain_events(t)
    finally:
        t._close()
        EyeTrackerDevice._INSTANCE = None
        srv.stop()

    fix_ends = _fixend_events(events)
    assert len(fix_ends) >= 1, "No FixationEndEvent emitted"
    assert len(fix_ends[0]) == 65, f"FixationEndEvent has {len(fix_ends[0])} fields"

    # duration should be positive
    assert fix_ends[0][12] > 0, "FixationEndEvent duration ≤ 0"


# ── gaze-source config ────────────────────────────────────────────────────────


def test_gaze_source_raw_is_default(tracker):
    assert tracker._gaze_source == "raw"


def test_gaze_source_avg_config():
    """EyeTracker constructed with gaze_source='avg' sets _gaze_source correctly."""
    EyeTrackerDevice._INSTANCE = None
    srv = MockEyeTribeServer(port=0, frame_rate=30, heartbeat_interval_ms=3000)
    srv.start()
    try:
        t = EyeTracker(dconfig=_make_dconfig(srv.port, gaze_source="avg"))
        assert t._gaze_source == "avg"
        t.setConnectionState(True)
        t.setRecordingState(True)
        time.sleep(0.15)
        t._poll()
        samples = _sample_events(_drain_events(t))
        assert samples, "No samples with gaze_source='avg'"
    finally:
        t._close()
        EyeTrackerDevice._INSTANCE = None
        srv.stop()


# ── timing ────────────────────────────────────────────────────────────────────


def test_tracker_time_returns_float(tracker):
    tracker.setRecordingState(True)
    time.sleep(0.1)
    tracker._poll()

    tt = tracker.trackerTime()
    ts = tracker.trackerSec()
    assert isinstance(tt, float), "trackerTime() did not return float"
    assert isinstance(ts, float), "trackerSec() did not return float"
    assert tt > 0, "trackerTime() not positive"
    assert ts > 0, "trackerSec() not positive"
    # trackerSec ≈ trackerTime * 0.001
    assert abs(ts - tt * 0.001) < 1e-6
