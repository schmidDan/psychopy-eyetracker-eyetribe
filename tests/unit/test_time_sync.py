"""Unit tests for psychopy_eyetracker_eyetribe.eyetribe.time_sync.

Acceptance criteria (Phase 4):
- Synthetic frames with known ``time`` map to expected PsychoPy times within 1 ms
  (deterministic math — no hardware jitter).
- Offset estimation, drift re-estimation, and RTT correction are verified
  numerically.
"""

from __future__ import annotations

import pytest

from psychopy_eyetracker_eyetribe.eyetribe.time_sync import REESTIMATE_INTERVAL_S, ClockSync

# ── import smoke ──────────────────────────────────────────────────────────────


def test_imports_without_psychopy() -> None:
    assert ClockSync is not None
    assert REESTIMATE_INTERVAL_S == 5.0


# ── initial state ─────────────────────────────────────────────────────────────


def test_not_initialized_before_update() -> None:
    cs = ClockSync()
    assert not cs.is_initialized


def test_initialized_after_first_update() -> None:
    cs = ClockSync()
    cs.update(tracker_time_ms=100_000, local_time_s=50.0)
    assert cs.is_initialized


def test_to_psychopy_time_raises_if_not_initialized() -> None:
    cs = ClockSync()
    with pytest.raises(RuntimeError, match="update"):
        cs.to_psychopy_time(100_000)


def test_offset_property_is_float() -> None:
    cs = ClockSync()
    cs.update(100_000, 50.0)
    assert isinstance(cs.offset, float)


# ── offset estimation ─────────────────────────────────────────────────────────


def test_basic_offset_no_rtt() -> None:
    """offset = local_s − tracker_s when rtt_s=0."""
    cs = ClockSync()
    tracker_ms = 100_000  # 100 s
    local_s = 50.0
    cs.update(tracker_ms, local_s, rtt_s=0.0)
    expected_offset = local_s - tracker_ms / 1000.0  # 50 - 100 = -50
    assert abs(cs.offset - expected_offset) < 1e-9


def test_to_psychopy_time_equals_local_at_first_update() -> None:
    """to_psychopy_time(tracker_ms) equals local_time at the first sync point."""
    cs = ClockSync()
    tracker_ms = 100_000
    local_s = 50.0
    cs.update(tracker_ms, local_s)
    result = cs.to_psychopy_time(tracker_ms)
    assert abs(result - local_s) < 1e-9


# ── RTT correction ────────────────────────────────────────────────────────────


def test_rtt_correction_shifts_offset() -> None:
    """offset corrects for half the RTT (one-way transmit delay)."""
    cs = ClockSync()
    tracker_ms = 100_000  # 100 s
    local_s = 50.1  # received 100 ms after sample was captured
    rtt_s = 0.08  # 80 ms RTT → correction = 40 ms
    cs.update(tracker_ms, local_s, rtt_s=rtt_s)
    # corrected_local = 50.1 − 0.04 = 50.06
    # offset = 50.06 − 100 = −49.94
    corrected_local = local_s - rtt_s / 2.0
    expected_offset = corrected_local - tracker_ms / 1000.0
    assert abs(cs.offset - expected_offset) < 1e-9


def test_zero_rtt_leaves_offset_unchanged() -> None:
    """Passing rtt_s=0 (default) is equivalent to no RTT correction."""
    cs_with = ClockSync()
    cs_without = ClockSync()
    cs_with.update(100_000, 50.0, rtt_s=0.0)
    cs_without.update(100_000, 50.0)
    assert abs(cs_with.offset - cs_without.offset) < 1e-15


# ── to_psychopy_time accuracy ─────────────────────────────────────────────────


def test_synthetic_frames_within_1ms() -> None:
    """10 consecutive 30 Hz frames map to PsychoPy times within 1 ms of expected."""
    cs = ClockSync()
    cs.update(tracker_time_ms=100_000, local_time_s=50.0)

    for i in range(1, 11):
        tracker_ms = 100_000 + i * 33  # ~33 ms per frame at 30 Hz
        expected = tracker_ms / 1000.0 + cs.offset
        result = cs.to_psychopy_time(tracker_ms)
        assert (
            abs(result - expected) < 0.001
        ), f"frame {i}: got {result:.6f}, expected {expected:.6f}"


def test_large_tracker_ms_converts_correctly() -> None:
    """Realistic tracker_ms (~1.889e8) converts without overflow."""
    cs = ClockSync()
    tracker_ms = 188_928_052  # value observed on hardware
    local_s = 3600.0
    cs.update(tracker_ms, local_s)
    result = cs.to_psychopy_time(tracker_ms)
    assert abs(result - local_s) < 1e-6


# ── drift re-estimation ───────────────────────────────────────────────────────


def test_no_reestimate_within_interval() -> None:
    """Offset is NOT updated while within the re-estimate interval."""
    cs = ClockSync(reestimate_interval_s=5.0)
    cs.update(100_000, local_time_s=50.0)
    offset_first = cs.offset  # 50 − 100 = −50

    # 3 s later with artificial drift (+0.5 s): new offset would be 53.5 − 103 = −49.5
    cs.update(103_000, local_time_s=53.5)
    assert abs(cs.offset - offset_first) < 1e-9, "offset changed within interval"


def test_reestimate_after_interval() -> None:
    """Offset IS updated after the re-estimate interval elapses."""
    cs = ClockSync(reestimate_interval_s=5.0)
    cs.update(100_000, local_time_s=50.0)
    offset_first = cs.offset  # −50

    # 6 s later with +0.5 s drift: new offset = 56.5 − 106 = −49.5
    cs.update(106_000, local_time_s=56.5)
    assert abs(cs.offset - (-49.5)) < 1e-9
    assert cs.offset != offset_first  # actually changed


def test_reestimate_boundary_exactly_at_interval() -> None:
    """Update exactly at the interval boundary triggers re-estimation."""
    cs = ClockSync(reestimate_interval_s=5.0)
    cs.update(100_000, local_time_s=50.0)
    # Exactly 5 s later
    cs.update(105_000, local_time_s=55.5)  # drift +0.5 s → offset = 55.5 − 105 = −49.5
    assert abs(cs.offset - (-49.5)) < 1e-9


def test_multiple_reestimate_cycles() -> None:
    """Offset tracks drift across multiple re-estimation cycles."""
    cs = ClockSync(reestimate_interval_s=5.0)
    cs.update(100_000, local_time_s=50.0)  # offset = −50

    cs.update(106_000, local_time_s=56.1)  # offset = 56.1 − 106 = −49.9
    assert abs(cs.offset - (-49.9)) < 1e-9

    cs.update(112_000, local_time_s=62.3)  # offset = 62.3 − 112 = −49.7
    assert abs(cs.offset - (-49.7)) < 1e-9


def test_custom_reestimate_interval() -> None:
    """ClockSync respects a custom reestimate_interval_s."""
    cs = ClockSync(reestimate_interval_s=10.0)
    cs.update(100_000, local_time_s=50.0)
    offset_first = cs.offset

    # 8 s later: within the 10 s custom interval — should NOT update
    cs.update(108_000, local_time_s=58.9)
    assert abs(cs.offset - offset_first) < 1e-9

    # 11 s after first update: past the interval — should update
    cs.update(111_000, local_time_s=61.8)  # offset = 61.8 − 111 = −49.2
    assert abs(cs.offset - (-49.2)) < 1e-9
