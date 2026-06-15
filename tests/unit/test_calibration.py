"""Unit tests for calibration.py — no window, no PsychoPy, no network required.

Tests:
- point_layout(): correct counts and range for 5/9/12 points; error on invalid count.
- parse_calibresult(): success and failure payloads, per-point extraction, missing keys.
- CalibrationSequencer: correct message sequences, abort path, redo (clear) path, and
  result extraction — all via a local mock request function (no real server).
"""

from __future__ import annotations

from typing import Any

import pytest

from psychopy_eyetracker_eyetribe.eyetribe.calibration import (
    DEFAULT_TARGET_COUNT,
    SAMPLE_MS,
    SETTLE_MS,
    SUPPORTED_TARGET_COUNTS,
    CalibrationResult,
    CalibrationSequencer,
    parse_calibresult,
    point_layout,
)

# ── constants ─────────────────────────────────────────────────────────────────


def test_default_target_count():
    assert DEFAULT_TARGET_COUNT == 9


def test_supported_target_counts():
    assert SUPPORTED_TARGET_COUNTS == (5, 9, 12)


def test_timing_constants():
    assert SETTLE_MS == 750
    assert SAMPLE_MS == 1000


# ── point_layout ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("n", [5, 9, 12])
def test_point_layout_correct_count(n):
    layout = point_layout(n)
    assert len(layout) == n


@pytest.mark.parametrize("n", [5, 9, 12])
def test_point_layout_values_in_unit_range(n):
    for x, y in point_layout(n):
        assert 0.0 <= x <= 1.0, f"x={x} out of [0,1] for {n}-point layout"
        assert 0.0 <= y <= 1.0, f"y={y} out of [0,1] for {n}-point layout"


@pytest.mark.parametrize("n", [5, 9, 12])
def test_point_layout_no_duplicates(n):
    layout = point_layout(n)
    assert len(set(layout)) == n, "Duplicate positions in layout"


@pytest.mark.parametrize("bad", [0, 3, 7, 13, -1])
def test_point_layout_invalid_count_raises(bad):
    with pytest.raises(ValueError, match="target_count"):
        point_layout(bad)


# ── parse_calibresult ─────────────────────────────────────────────────────────


def _make_calibresult(
    result: bool = True,
    deg: float = 0.71,
    n_points: int = 9,
) -> dict[str, Any]:
    return {
        "result": result,
        "deg": deg,
        "degl": deg - 0.05,
        "degr": deg + 0.05,
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
            for _ in range(n_points)
        ],
    }


def test_parse_calibresult_success():
    raw = _make_calibresult(result=True, deg=0.71, n_points=9)
    cr = parse_calibresult(raw)
    assert isinstance(cr, CalibrationResult)
    assert cr.success is True
    assert cr.avg_error_deg == pytest.approx(0.71)
    assert len(cr.per_point) == 9


def test_parse_calibresult_failure():
    raw = _make_calibresult(result=False, deg=2.5, n_points=5)
    cr = parse_calibresult(raw)
    assert cr.success is False
    assert cr.avg_error_deg == pytest.approx(2.5)
    assert len(cr.per_point) == 5


def test_parse_calibresult_per_point_fields():
    raw = _make_calibresult(n_points=1)
    cr = parse_calibresult(raw)
    pt = cr.per_point[0]
    assert "ad" in pt
    assert pt["ad"] == pytest.approx(0.65)


def test_parse_calibresult_empty_calibpoints():
    raw = {"result": True, "deg": 0.5, "calibpoints": []}
    cr = parse_calibresult(raw)
    assert cr.per_point == ()


def test_parse_calibresult_missing_keys_use_defaults():
    cr = parse_calibresult({})
    assert cr.success is False
    assert cr.avg_error_deg == pytest.approx(0.0)
    assert cr.per_point == ()


def test_parse_calibresult_immutable():
    cr = parse_calibresult(_make_calibresult())
    with pytest.raises((AttributeError, TypeError)):
        cr.success = False  # type: ignore[misc]


# ── CalibrationSequencer — helpers ────────────────────────────────────────────


class _MockTransport:
    """Records sent messages and returns configurable replies."""

    def __init__(self, calibresult: dict[str, Any] | None = None) -> None:
        self.sent: list[dict[str, Any]] = []
        self._calibresult = calibresult or {
            "result": True,
            "deg": 0.71,
            "degl": 0.66,
            "degr": 0.77,
            "calibpoints": [],
        }

    def __call__(self, msg: dict[str, Any]) -> dict[str, Any]:
        self.sent.append(msg)
        req = msg.get("request", "")
        cat = msg.get("category", "")
        if cat == "calibration" and req == "pointend":
            return {
                "category": "calibration",
                "request": "pointend",
                "statuscode": 200,
                "values": {"calibresult": self._calibresult},
            }
        return {"category": cat, "request": req, "statuscode": 200}

    @property
    def requests(self) -> list[str]:
        return [m.get("request", "") for m in self.sent]


# ── CalibrationSequencer — individual method tests ────────────────────────────


def test_sequencer_start_sends_correct_message():
    t = _MockTransport()
    seq = CalibrationSequencer(t)
    seq.start(9)
    assert t.sent[-1] == {
        "category": "calibration",
        "request": "start",
        "values": {"pointcount": 9},
    }


def test_sequencer_point_start_sends_coords():
    t = _MockTransport()
    seq = CalibrationSequencer(t)
    seq.point_start(960.0, 540.0)
    assert t.sent[-1] == {
        "category": "calibration",
        "request": "pointstart",
        "values": {"x": 960.0, "y": 540.0},
    }


def test_sequencer_point_end_returns_calibresult():
    t = _MockTransport()
    seq = CalibrationSequencer(t)
    raw = seq.point_end()
    assert raw is not None
    assert raw["result"] is True


def test_sequencer_point_end_returns_none_when_no_calibresult():
    def _no_cr(msg: dict) -> dict:
        return {"category": "calibration", "request": "pointend", "statuscode": 200}

    seq = CalibrationSequencer(_no_cr)
    assert seq.point_end() is None


def test_sequencer_abort_sends_abort():
    t = _MockTransport()
    seq = CalibrationSequencer(t)
    seq.abort()
    assert t.sent[-1] == {"category": "calibration", "request": "abort"}


def test_sequencer_clear_sends_clear():
    t = _MockTransport()
    seq = CalibrationSequencer(t)
    seq.clear()
    assert t.sent[-1] == {"category": "calibration", "request": "clear"}


# ── CalibrationSequencer — full sequence tests ────────────────────────────────


@pytest.mark.parametrize("n", [5, 9, 12])
def test_full_calibration_sequence_message_order(n):
    """start → N×(pointstart, pointend) → correct message order."""
    t = _MockTransport()
    seq = CalibrationSequencer(t)
    layout = point_layout(n)

    seq.start(n)
    for x_norm, y_norm in layout:
        seq.point_start(x_norm * 1920, y_norm * 1080)
        seq.point_end()

    expected = ["start"] + ["pointstart", "pointend"] * n
    assert t.requests == expected


@pytest.mark.parametrize("n", [5, 9, 12])
def test_full_calibration_sequence_returns_valid_result(n):
    t = _MockTransport()
    seq = CalibrationSequencer(t)
    layout = point_layout(n)

    seq.start(n)
    last_raw = None
    for x_norm, y_norm in layout:
        seq.point_start(x_norm * 1920, y_norm * 1080)
        raw = seq.point_end()
        if raw is not None:
            last_raw = raw

    assert last_raw is not None
    result = parse_calibresult(last_raw)
    assert result.success is True
    assert result.avg_error_deg == pytest.approx(0.71)


def test_abort_path_message_order():
    """After abort: start → pointstart → pointend → abort."""
    t = _MockTransport()
    seq = CalibrationSequencer(t)
    seq.start(5)
    seq.point_start(960.0, 540.0)
    seq.point_end()
    seq.abort()
    assert t.requests == ["start", "pointstart", "pointend", "abort"]


def test_redo_path_message_order():
    """First attempt → clear → second attempt."""
    t = _MockTransport()
    seq = CalibrationSequencer(t)
    layout_5 = point_layout(5)

    # First run
    seq.start(5)
    for x, y in layout_5:
        seq.point_start(x * 1920, y * 1080)
        seq.point_end()

    # Clear and redo
    seq.clear()
    seq.start(5)
    for x, y in layout_5:
        seq.point_start(x * 1920, y * 1080)
        seq.point_end()

    assert t.requests.count("start") == 2
    assert "clear" in t.requests
    first_clear = t.requests.index("clear")
    # clear comes after the first run and before the second start
    second_start = t.requests.index("start", first_clear)
    assert second_start > first_clear


def test_pixel_coords_passed_correctly():
    """point_start forwards pixel coordinates unchanged."""
    t = _MockTransport()
    seq = CalibrationSequencer(t)
    seq.point_start(192.0, 108.0)
    sent_vals = t.sent[-1]["values"]
    assert sent_vals["x"] == pytest.approx(192.0)
    assert sent_vals["y"] == pytest.approx(108.0)


def test_start_uses_given_point_count():
    t = _MockTransport()
    seq = CalibrationSequencer(t)
    for n in [5, 9, 12]:
        seq.start(n)
    assert [m["values"]["pointcount"] for m in t.sent] == [5, 9, 12]


# ── existing import test (from Phase 0 stub) ─────────────────────────────────


def test_imports_without_psychopy():
    from psychopy_eyetracker_eyetribe.eyetribe import calibration

    assert calibration.DEFAULT_TARGET_COUNT == 9
    assert calibration.SUPPORTED_TARGET_COUNTS == (5, 9, 12)
    assert callable(calibration.parse_calibresult)
