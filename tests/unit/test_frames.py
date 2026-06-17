"""Phase 2 — Frame parsing & data model tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from psychopy_eyetracker_eyetribe.eyetribe.frames import (
    STATE_TRACKING_EYES,
    STATE_TRACKING_FAIL,
    STATE_TRACKING_GAZE,
    STATE_TRACKING_LOST,
    STATE_TRACKING_PRESENCE,
    EyeData,
    FrameParseError,
    Point,
    TrackingState,
    parse_frame,
)

_CAPTURED_FRAME = Path(__file__).parent.parent / "manual" / "_captured_frame.json"

# ── helpers ───────────────────────────────────────────────────────────────────


def _eye_dict(x: float, y: float, psize: float = 15.0) -> dict[str, Any]:
    return {
        "raw": {"x": x, "y": y},
        "avg": {"x": x, "y": y},
        "psize": psize,
        "pcenter": {"x": x / 1920.0, "y": y / 1080.0},
    }


def _frame_dict(
    state: int,
    gx: float = 960.0,
    gy: float = 540.0,
    time_ms: int = 100_000,
    fix: bool = True,
) -> dict[str, Any]:
    return {
        "timestamp": "2026-06-15 14:30:14.000",
        "time": time_ms,
        "fix": fix,
        "state": state,
        "raw": {"x": gx, "y": gy},
        "avg": {"x": gx, "y": gy},
        "lefteye": _eye_dict(gx - 5.0, gy + 2.0, psize=15.0),
        "righteye": _eye_dict(gx + 5.0, gy - 2.0, psize=15.5),
    }


# ── round-trip: all mock frame variants ──────────────────────────────────────


class TestParseFrameVariants:
    def test_valid_binocular(self) -> None:
        state = STATE_TRACKING_GAZE | STATE_TRACKING_EYES | STATE_TRACKING_PRESENCE
        frame = parse_frame(_frame_dict(state, gx=1024.5, gy=720.3))
        assert frame.time_ms == 100_000
        assert frame.fix is True
        assert frame.state == state
        assert frame.raw == Point(x=1024.5, y=720.3)
        assert frame.avg == Point(x=1024.5, y=720.3)
        assert isinstance(frame.left, EyeData)
        assert isinstance(frame.right, EyeData)
        assert frame.is_gaze_valid()

    def test_eyes_only_no_gaze(self) -> None:
        state = STATE_TRACKING_EYES | STATE_TRACKING_PRESENCE
        frame = parse_frame(_frame_dict(state, gx=0.0, gy=0.0, fix=False))
        assert frame.state == state
        assert not frame.is_gaze_valid()

    def test_blink_fail_state(self) -> None:
        frame = parse_frame(_frame_dict(STATE_TRACKING_FAIL, gx=0.0, gy=0.0, fix=False))
        assert not frame.is_gaze_valid()

    def test_tracking_lost(self) -> None:
        frame = parse_frame(_frame_dict(STATE_TRACKING_LOST, gx=0.0, gy=0.0, fix=False))
        assert not frame.is_gaze_valid()

    def test_malformed_missing_key(self) -> None:
        d = _frame_dict(STATE_TRACKING_GAZE)
        del d["state"]
        with pytest.raises(FrameParseError):
            parse_frame(d)

    def test_malformed_bad_point_type(self) -> None:
        d = _frame_dict(STATE_TRACKING_GAZE)
        d["raw"] = "not a dict"
        with pytest.raises(FrameParseError):
            parse_frame(d)

    def test_malformed_nested_bad_value(self) -> None:
        d = _frame_dict(STATE_TRACKING_GAZE)
        d["lefteye"]["raw"] = {"x": "NaN_string", "y": 0.0}
        with pytest.raises(FrameParseError):
            parse_frame(d)

    def test_malformed_not_a_dict(self) -> None:
        with pytest.raises(FrameParseError):
            parse_frame("not a dict")  # type: ignore[arg-type]

    def test_malformed_missing_eye_key(self) -> None:
        d = _frame_dict(STATE_TRACKING_GAZE)
        del d["lefteye"]["psize"]
        with pytest.raises(FrameParseError):
            parse_frame(d)

    def test_malformed_eye_not_a_dict(self) -> None:
        d = _frame_dict(STATE_TRACKING_GAZE)
        d["lefteye"] = "not a dict"
        with pytest.raises(FrameParseError):
            parse_frame(d)


# ── captured hardware frame (golden schema fixture) ───────────────────────────


class TestCapturedFrame:
    def test_captured_frame_parses(self) -> None:
        payload = json.loads(_CAPTURED_FRAME.read_text())
        frame = parse_frame(payload)
        assert frame.time_ms == 346742012
        assert frame.fix is True
        assert frame.state == 7  # STATE_TRACKING_GAZE | EYES | PRESENCE
        assert frame.raw == Point(x=916.4501, y=525.711)
        assert isinstance(frame.left, EyeData)
        assert isinstance(frame.right, EyeData)
        assert frame.is_gaze_valid()


# ── gaze() helper ─────────────────────────────────────────────────────────────


class TestGazeHelper:
    def test_gaze_raw(self) -> None:
        state = STATE_TRACKING_GAZE | STATE_TRACKING_EYES | STATE_TRACKING_PRESENCE
        frame = parse_frame(_frame_dict(state, gx=500.0, gy=300.0))
        assert frame.gaze("raw") == Point(x=500.0, y=300.0)

    def test_gaze_avg(self) -> None:
        state = STATE_TRACKING_GAZE | STATE_TRACKING_EYES | STATE_TRACKING_PRESENCE
        frame = parse_frame(_frame_dict(state, gx=500.0, gy=300.0))
        assert frame.gaze("avg") == Point(x=500.0, y=300.0)

    def test_gaze_default_is_raw(self) -> None:
        state = STATE_TRACKING_GAZE | STATE_TRACKING_EYES | STATE_TRACKING_PRESENCE
        frame = parse_frame(_frame_dict(state, gx=100.0, gy=200.0))
        assert frame.gaze() == frame.raw


# ── TrackingState: all 32 low-5-bit combinations ─────────────────────────────


@pytest.mark.parametrize("state", range(32))
def test_tracking_state_all_32_combinations(state: int) -> None:
    ts = TrackingState.from_int(state)
    assert ts.gaze == bool(state & STATE_TRACKING_GAZE)
    assert ts.eyes == bool(state & STATE_TRACKING_EYES)
    assert ts.presence == bool(state & STATE_TRACKING_PRESENCE)
    assert ts.fail == bool(state & STATE_TRACKING_FAIL)
    assert ts.lost == bool(state & STATE_TRACKING_LOST)


# ── is_gaze_valid: boundary cases ────────────────────────────────────────────


@pytest.mark.parametrize(
    "state, expected",
    [
        (STATE_TRACKING_GAZE, True),
        (STATE_TRACKING_GAZE | STATE_TRACKING_EYES | STATE_TRACKING_PRESENCE, True),
        (0, False),
        (STATE_TRACKING_EYES | STATE_TRACKING_PRESENCE, False),
        (STATE_TRACKING_GAZE | STATE_TRACKING_FAIL, False),
        (STATE_TRACKING_GAZE | STATE_TRACKING_LOST, False),
        (STATE_TRACKING_GAZE | STATE_TRACKING_FAIL | STATE_TRACKING_LOST, False),
        (STATE_TRACKING_FAIL, False),
        (STATE_TRACKING_LOST, False),
    ],
)
def test_is_gaze_valid(state: int, expected: bool) -> None:
    frame = parse_frame(_frame_dict(state))
    assert frame.is_gaze_valid() == expected


# ── EyeData fields ────────────────────────────────────────────────────────────


class TestEyeDataFields:
    def test_eye_data_values(self) -> None:
        state = STATE_TRACKING_GAZE | STATE_TRACKING_EYES | STATE_TRACKING_PRESENCE
        frame = parse_frame(_frame_dict(state, gx=960.0, gy=540.0))
        assert frame.left.raw == Point(x=955.0, y=542.0)
        assert frame.left.psize == pytest.approx(15.0)
        assert isinstance(frame.left.pcenter, Point)
        assert frame.right.raw == Point(x=965.0, y=538.0)
        assert frame.right.psize == pytest.approx(15.5)

    def test_frozen_point_raises_on_set(self) -> None:
        p = Point(x=1.0, y=2.0)
        with pytest.raises(Exception):
            p.x = 3.0  # type: ignore[misc]

    def test_frozen_frame_raises_on_set(self) -> None:
        frame = parse_frame(_frame_dict(STATE_TRACKING_GAZE))
        with pytest.raises(Exception):
            frame.fix = True  # type: ignore[misc]


# ── backward-compat: test_imports_without_psychopy (Phase 0) ─────────────────


def test_imports_without_psychopy() -> None:
    from psychopy_eyetracker_eyetribe.eyetribe import frames

    assert callable(frames.parse_frame)
    assert issubclass(frames.FrameParseError, ValueError)
    assert frames.STATE_TRACKING_GAZE == 0x1
