"""Phase 5 integration tests: calibration against MockEyeTribeServer.

Part A — CalibrationSequencer + real mock server (no window).
  Verifies the exact message sequence and result parsing for 5/9/12-point runs,
  the abort path, and the redo (clear) path.

Part B — EyeTracker.runSetupProcedure with mocked PsychoPy visual layer.
  Patches psychopy.visual and psychopy.event so no display is required.
  Verifies that runSetupProcedure sends the correct calibration messages and
  returns the expected status code.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

pytestmark = pytest.mark.integration

from psychopy_eyetracker_eyetribe.eyetribe.calibration import (  # noqa: E402
    CalibrationSequencer,
    parse_calibresult,
    point_layout,
)
from psychopy_eyetracker_eyetribe.eyetribe.eyetribe_client import EyeTribeClient  # noqa: E402
from psychopy_eyetracker_eyetribe.mock.mock_server import MockEyeTribeServer  # noqa: E402

# ── Part A: CalibrationSequencer against real mock ────────────────────────────


@pytest.fixture
def calib_server():
    """Mock server with a fixed calibresult for testing."""
    calib_result = {
        "result": True,
        "deg": 0.71,
        "degl": 0.66,
        "degr": 0.77,
        "calibpoints": [
            {
                "state": 1,
                "cp": {"x": 960.0, "y": 540.0},
                "mecp": {"x": 961.0, "y": 541.0},
                "ad": 0.65,
                "adl": 0.60,
                "adr": 0.70,
                "mep": 10.0,
                "mepl": 9.0,
                "mepr": 11.0,
            }
        ]
        * 12,  # enough points for 12-point calibration
    }
    srv = MockEyeTribeServer(port=0, calib_result=calib_result)
    srv.start()
    yield srv
    srv.stop()


@pytest.fixture
def client(calib_server):
    """Connected EyeTribeClient."""
    c = EyeTribeClient(host="127.0.0.1", port=calib_server.port)
    c.connect()
    yield c
    c.close()


@pytest.fixture
def sequencer(client):
    return CalibrationSequencer(client._request)


@pytest.mark.parametrize("target_count", [5, 9, 12])
def test_full_calibration_run_message_sequence(sequencer, calib_server, target_count):
    """Full N-point run sends start + N×(pointstart, pointend) in order."""
    calib_server.clear_calib_log()
    layout = point_layout(target_count)

    sequencer.start(target_count)
    last_raw: dict[str, Any] | None = None
    for x_norm, y_norm in layout:
        sequencer.point_start(x_norm * 1920, y_norm * 1080)
        raw = sequencer.point_end()
        if raw is not None:
            last_raw = raw

    log = calib_server.get_calib_log()
    requests = [m["request"] for m in log]
    expected = ["start"] + ["pointstart", "pointend"] * target_count
    assert requests == expected, f"Unexpected message sequence: {requests}"


@pytest.mark.parametrize("target_count", [5, 9, 12])
def test_full_calibration_run_parses_result(sequencer, calib_server, target_count):
    """CalibrationResult parsed from final pointend has correct fields."""
    layout = point_layout(target_count)
    sequencer.start(target_count)
    last_raw: dict[str, Any] | None = None
    for x_norm, y_norm in layout:
        sequencer.point_start(x_norm * 1920, y_norm * 1080)
        raw = sequencer.point_end()
        if raw is not None:
            last_raw = raw

    assert last_raw is not None, "No calibresult received"
    result = parse_calibresult(last_raw)
    assert result.success is True
    assert result.avg_error_deg == pytest.approx(0.71)
    assert len(result.per_point) > 0


def test_abort_path_leaves_device_clean(sequencer, calib_server):
    """After abort the device accepts a fresh start without error."""
    calib_server.clear_calib_log()
    layout = point_layout(5)

    sequencer.start(5)
    sequencer.point_start(layout[0][0] * 1920, layout[0][1] * 1080)
    sequencer.point_end()
    sequencer.abort()

    requests_after_abort = [m["request"] for m in calib_server.get_calib_log()]
    assert requests_after_abort[-1] == "abort"

    # Device should accept a new start after abort
    calib_server.clear_calib_log()
    sequencer.start(5)
    assert calib_server.get_calib_log()[0]["request"] == "start"


def test_redo_path_clear_then_restart(sequencer, calib_server):
    """Redo: first run → clear → second full run."""
    calib_server.clear_calib_log()
    layout = point_layout(5)

    # First run
    sequencer.start(5)
    for x, y in layout:
        sequencer.point_start(x * 1920, y * 1080)
        sequencer.point_end()

    # Redo
    sequencer.clear()
    sequencer.start(5)
    for x, y in layout:
        sequencer.point_start(x * 1920, y * 1080)
        sequencer.point_end()

    all_reqs = [m["request"] for m in calib_server.get_calib_log()]
    assert all_reqs.count("start") == 2
    assert "clear" in all_reqs
    # clear comes between the two starts
    idx_clear = all_reqs.index("clear")
    idx_second_start = all_reqs.index("start", idx_clear)
    assert idx_second_start > idx_clear


def test_pointstart_coords_forwarded_correctly(sequencer, calib_server):
    """Pixel coordinates reach the mock exactly as sent."""
    calib_server.clear_calib_log()
    sequencer.start(5)
    sequencer.point_start(192.0, 108.0)

    log = calib_server.get_calib_log()
    ps_entry = next(m for m in log if m["request"] == "pointstart")
    assert ps_entry["values"]["x"] == pytest.approx(192.0)
    assert ps_entry["values"]["y"] == pytest.approx(108.0)


# ── Part B: runSetupProcedure with mocked PsychoPy ───────────────────────────

psychopy = pytest.importorskip("psychopy", reason="PsychoPy not installed")

from psychopy.iohub.constants import EyeTrackerConstants  # noqa: E402
from psychopy.iohub.devices.eyetracker import EyeTrackerDevice  # noqa: E402

from psychopy_eyetracker_eyetribe.eyetribe.eyetracker import EyeTracker  # noqa: E402


def _make_dconfig(port: int) -> dict[str, Any]:
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
        "gaze_source": "raw",
        "runtime_settings": {"sampling_rate": "auto", "track_eyes": "BINOCULAR"},
        "calibration": {"target_count": 9},
        "device_timer": {"interval": 0.005},
        "monitor_event_types": [
            "BinocularEyeSampleEvent",
            "FixationStartEvent",
            "FixationEndEvent",
        ],
    }


def _reset_singleton() -> None:
    """Clear both the base-class and subclass _INSTANCE so a fresh EyeTracker can be created."""
    EyeTrackerDevice._INSTANCE = None
    # After construction, Python sets _INSTANCE on the concrete subclass directly.
    # Clearing only the base class leaves the subclass attribute intact, causing a
    # "already created" error on the next construction.
    if "_INSTANCE" in EyeTracker.__dict__:
        EyeTracker._INSTANCE = None  # type: ignore[attr-defined]


def _make_tracker(port: int) -> EyeTracker:
    _reset_singleton()
    t = EyeTracker(dconfig=_make_dconfig(port))
    t.setConnectionState(True)
    return t


def _mock_window() -> MagicMock:
    """A minimal Window mock: flip returns None, setMouseVisible/close are no-ops."""
    win = MagicMock()
    win.flip.return_value = None
    return win


def _mock_visual(win: MagicMock) -> MagicMock:
    pp_visual = MagicMock()
    pp_visual.Window.return_value = win
    pp_visual.Circle.return_value = MagicMock()
    pp_visual.TextStim.return_value = MagicMock()
    return pp_visual


def _key_sequence(*keys: str) -> list[list[str]]:
    """Build a side_effect list: each call returns the next list of keys."""
    return [[k] for k in keys]


@pytest.fixture
def srv_9pt():
    srv = MockEyeTribeServer(port=0, calib_result={
        "result": True,
        "deg": 0.71,
        "degl": 0.66,
        "degr": 0.77,
        "calibpoints": [{"state": 1, "cp": {"x": 960, "y": 540},
                         "mecp": {"x": 961, "y": 541},
                         "ad": 0.65, "adl": 0.60, "adr": 0.70,
                         "mep": 10.0, "mepl": 9.0, "mepr": 11.0}] * 9,
    })
    srv.start()
    yield srv
    srv.stop()


def test_run_setup_procedure_success(srv_9pt):
    """runSetupProcedure accepts calibration and returns EYETRACKER_OK."""
    t = _make_tracker(srv_9pt.port)
    # Speed up timing so the test doesn't sleep 1.75 s × 9 points
    t._CALIB_SETTLE_S = 0.0
    t._CALIB_SAMPLE_S = 0.0

    win = _mock_window()
    pp_visual = _mock_visual(win)

    # Keyboard sequence: space (start intro) → ... → space (accept summary)
    # With 0-second timing loops, getKeys is only called in intro and summary screens.
    pp_event = MagicMock()
    pp_event.getKeys.side_effect = _key_sequence("space", "space")

    srv_9pt.clear_calib_log()

    with patch.dict("sys.modules", {"psychopy.visual": pp_visual, "psychopy.event": pp_event}):
        with patch("psychopy_eyetracker_eyetribe.eyetribe.eyetracker.pp_visual", pp_visual, create=True):
            result = t._run_calib_loop(win, 9, 1920, 1080, pp_event, pp_visual)
    t._close()
    _reset_singleton()

    assert result == EyeTrackerConstants.EYETRACKER_OK

    # Verify the correct message sequence was sent to the mock
    requests = [m["request"] for m in srv_9pt.get_calib_log()]
    expected = ["start"] + ["pointstart", "pointend"] * 9
    assert requests == expected


def test_run_setup_procedure_abort_on_escape_intro(srv_9pt):
    """Pressing Escape on the intro screen aborts without sending calibration messages."""
    t = _make_tracker(srv_9pt.port)
    t._CALIB_SETTLE_S = 0.0
    t._CALIB_SAMPLE_S = 0.0

    win = _mock_window()
    pp_visual = _mock_visual(win)
    pp_event = MagicMock()
    pp_event.getKeys.return_value = ["escape"]  # always escape

    srv_9pt.clear_calib_log()
    result = t._run_calib_loop(win, 9, 1920, 1080, pp_event, pp_visual)
    t._close()
    _reset_singleton()

    assert result == EyeTrackerConstants.EYETRACKER_CALIBRATION_ERROR
    # No calibration messages should have been sent
    assert srv_9pt.get_calib_log() == []


def test_run_setup_procedure_abort_on_escape_summary(srv_9pt):
    """Pressing Escape on the summary screen returns CALIBRATION_ERROR after full run."""
    t = _make_tracker(srv_9pt.port)
    t._CALIB_SETTLE_S = 0.0
    t._CALIB_SAMPLE_S = 0.0

    win = _mock_window()
    pp_visual = _mock_visual(win)
    pp_event = MagicMock()
    # space to start, then escape at summary
    pp_event.getKeys.side_effect = _key_sequence("space", "escape")

    result = t._run_calib_loop(win, 9, 1920, 1080, pp_event, pp_visual)
    t._close()
    _reset_singleton()

    assert result == EyeTrackerConstants.EYETRACKER_CALIBRATION_ERROR


def test_run_setup_procedure_redo_then_accept(srv_9pt):
    """R on the summary screen triggers a redo (clear + restart); space then accepts."""
    t = _make_tracker(srv_9pt.port)
    t._CALIB_SETTLE_S = 0.0
    t._CALIB_SAMPLE_S = 0.0

    win = _mock_window()
    pp_visual = _mock_visual(win)
    pp_event = MagicMock()
    # intro-start, redo-at-summary, second-intro-start, accept-at-summary
    pp_event.getKeys.side_effect = _key_sequence("space", "r", "space", "space")

    srv_9pt.clear_calib_log()
    result = t._run_calib_loop(win, 9, 1920, 1080, pp_event, pp_visual)
    t._close()
    _reset_singleton()

    assert result == EyeTrackerConstants.EYETRACKER_OK

    all_reqs = [m["request"] for m in srv_9pt.get_calib_log()]
    # Two full runs plus a clear between them
    assert all_reqs.count("start") == 2
    assert "clear" in all_reqs


def test_run_setup_procedure_window_closed_on_exit(srv_9pt):
    """The calibration window is closed via runSetupProcedure's finally block."""
    t = _make_tracker(srv_9pt.port)
    t._CALIB_SETTLE_S = 0.0
    t._CALIB_SAMPLE_S = 0.0

    win = _mock_window()
    pp_visual = _mock_visual(win)
    pp_event = MagicMock()
    pp_event.getKeys.side_effect = _key_sequence("space", "space")

    # Drive _run_calib_loop directly; verify the window is NOT closed by it
    # (window close happens in runSetupProcedure's finally block, not the inner loop).
    t._run_calib_loop(win, 9, 1920, 1080, pp_event, pp_visual)
    win.close.assert_not_called()

    # Now verify runSetupProcedure closes it.  Patch at sys.modules level so the
    # lazy imports inside the method see our mocks.
    import sys

    pp_event2 = MagicMock()
    pp_event2.getKeys.side_effect = _key_sequence("space", "space")
    pp_visual2 = _mock_visual(_mock_window())
    captured_win: list[MagicMock] = []

    def _capturing_window(*args: Any, **kwargs: Any) -> MagicMock:
        w = _mock_window()
        captured_win.append(w)
        return w

    pp_visual2.Window.side_effect = _capturing_window

    orig_visual = sys.modules.get("psychopy.visual")
    orig_event = sys.modules.get("psychopy.event")
    sys.modules["psychopy.visual"] = pp_visual2  # type: ignore[assignment]
    sys.modules["psychopy.event"] = pp_event2  # type: ignore[assignment]
    try:
        t.runSetupProcedure()
    finally:
        if orig_visual is not None:
            sys.modules["psychopy.visual"] = orig_visual
        else:
            sys.modules.pop("psychopy.visual", None)
        if orig_event is not None:
            sys.modules["psychopy.event"] = orig_event
        else:
            sys.modules.pop("psychopy.event", None)
        t._close()
        _reset_singleton()

    assert captured_win, "Window was never created"
    captured_win[0].close.assert_called()
