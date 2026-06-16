# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Unit tests for psychopy_eyetracker_eyetribe.eyetribe.validation."""

from __future__ import annotations

import math

import pytest

from psychopy_eyetracker_eyetribe.eyetribe.validation import (
    compute_accuracy,
    compute_precision,
    compute_timing_stats,
    euclidean_degrees,
)

# Shared monitor parameters (typical 24-inch monitor at arm's length)
SW, SH = 1920, 1080
MW, MH = 53.1, 29.9  # cm
DIST = 60.0  # cm

# ── euclidean_degrees ─────────────────────────────────────────────────────────


def test_euclidean_degrees_zero():
    assert euclidean_degrees(0, 0, SW, SH, MW, MH, DIST) == pytest.approx(0.0, abs=1e-9)


def test_euclidean_degrees_horizontal():
    # 100 px horizontal → arctan(100 * MW/SW / DIST)
    expected = math.degrees(math.atan2(100 * MW / SW, DIST))
    got = euclidean_degrees(100, 0, SW, SH, MW, MH, DIST)
    assert abs(got - expected) < 1e-9


def test_euclidean_degrees_vertical():
    expected = math.degrees(math.atan2(100 * MH / SH, DIST))
    got = euclidean_degrees(0, 100, SW, SH, MW, MH, DIST)
    assert abs(got - expected) < 1e-9


def test_euclidean_degrees_diagonal():
    dx_cm = 100 * MW / SW
    dy_cm = 100 * MH / SH
    expected = math.degrees(math.atan2(math.hypot(dx_cm, dy_cm), DIST))
    got = euclidean_degrees(100, 100, SW, SH, MW, MH, DIST)
    assert abs(got - expected) < 1e-9


def test_euclidean_degrees_symmetry():
    """Negative offset should give the same angle as positive (offset magnitude)."""
    pos = euclidean_degrees(200, 100, SW, SH, MW, MH, DIST)
    neg = euclidean_degrees(-200, -100, SW, SH, MW, MH, DIST)
    assert pos == pytest.approx(neg)


def test_euclidean_degrees_larger_offset_gives_larger_angle():
    small = euclidean_degrees(50, 0, SW, SH, MW, MH, DIST)
    large = euclidean_degrees(100, 0, SW, SH, MW, MH, DIST)
    assert large > small


def test_euclidean_degrees_typical_range():
    # ~1 degree at 60 cm viewing; for 53.1 cm wide screen / 1920 px → ~28 px / deg
    one_deg_px = math.tan(math.radians(1.0)) * DIST / (MW / SW)
    got = euclidean_degrees(one_deg_px, 0, SW, SH, MW, MH, DIST)
    assert abs(got - 1.0) < 0.01


# ── compute_accuracy ──────────────────────────────────────────────────────────


def test_compute_accuracy_perfect():
    """Gaze equals target at every point → accuracy 0."""
    targets = [(100.0, 200.0), (800.0, 600.0), (960.0, 540.0)]
    gazes = list(targets)
    acc = compute_accuracy(targets, gazes, SW, SH, MW, MH, DIST)
    assert acc == pytest.approx(0.0, abs=1e-9)


def test_compute_accuracy_mean():
    """Mean of two offsets computed correctly."""
    targets = [(960.0, 540.0), (960.0, 540.0)]
    gazes = [(860.0, 540.0), (760.0, 540.0)]  # 100 px and 200 px horizontal offset
    acc = compute_accuracy(targets, gazes, SW, SH, MW, MH, DIST)
    d1 = euclidean_degrees(100, 0, SW, SH, MW, MH, DIST)
    d2 = euclidean_degrees(200, 0, SW, SH, MW, MH, DIST)
    assert abs(acc - (d1 + d2) / 2) < 1e-9


def test_compute_accuracy_empty_returns_nan():
    result = compute_accuracy([], [], SW, SH, MW, MH, DIST)
    assert math.isnan(result)


def test_compute_accuracy_length_mismatch():
    with pytest.raises(ValueError, match="equal length"):
        compute_accuracy([(0.0, 0.0)], [], SW, SH, MW, MH, DIST)


def test_compute_accuracy_single_point():
    targets = [(500.0, 300.0)]
    gazes = [(600.0, 300.0)]
    acc = compute_accuracy(targets, gazes, SW, SH, MW, MH, DIST)
    assert acc == pytest.approx(euclidean_degrees(100, 0, SW, SH, MW, MH, DIST))


def test_compute_accuracy_realistic_1_deg():
    """Accuracy ≈ 1° for typical ET-class offset."""
    one_deg_px = math.tan(math.radians(1.0)) * DIST / (MW / SW)
    targets = [(960.0, 540.0)]
    gazes = [(960.0 + one_deg_px, 540.0)]
    acc = compute_accuracy(targets, gazes, SW, SH, MW, MH, DIST)
    assert abs(acc - 1.0) < 0.01


# ── compute_precision ─────────────────────────────────────────────────────────


def test_compute_precision_empty_returns_nan():
    result = compute_precision([], SW, SH, MW, MH, DIST)
    assert math.isnan(result)


def test_compute_precision_one_sample():
    result = compute_precision([(500.0, 300.0)], SW, SH, MW, MH, DIST)
    assert result == 0.0


def test_compute_precision_identical_samples():
    samples = [(500.0, 300.0)] * 20
    result = compute_precision(samples, SW, SH, MW, MH, DIST)
    assert result == pytest.approx(0.0, abs=1e-9)


def test_compute_precision_two_samples():
    samples = [(960.0, 540.0), (1060.0, 540.0)]  # 100 px apart
    prec = compute_precision(samples, SW, SH, MW, MH, DIST)
    expected = euclidean_degrees(100, 0, SW, SH, MW, MH, DIST)
    assert abs(prec - expected) < 1e-9


def test_compute_precision_uniform_jitter():
    """Alternating samples give RMS equal to the per-step distance."""
    step = 10.0  # px
    samples = [(960.0 + (step if i % 2 else 0.0), 540.0) for i in range(10)]
    prec = compute_precision(samples, SW, SH, MW, MH, DIST)
    expected = euclidean_degrees(step, 0, SW, SH, MW, MH, DIST)
    assert abs(prec - expected) < 1e-6


def test_compute_precision_realistic_sub_half_deg():
    """Good ET precision is < 0.5°; tiny jitter should pass this bound.

    Alternating ±px samples produce inter-sample distances of 2×amplitude,
    so use a 0.2° amplitude so the RMS stays below 0.5°.
    """
    px_amplitude = math.tan(math.radians(0.2)) * DIST / (MW / SW)
    samples = [(960.0 + (px_amplitude if i % 2 else -px_amplitude), 540.0) for i in range(30)]
    prec = compute_precision(samples, SW, SH, MW, MH, DIST)
    assert prec < 0.5


# ── compute_timing_stats ──────────────────────────────────────────────────────


def test_compute_timing_stats_empty():
    stats = compute_timing_stats([])
    assert all(math.isnan(v) for v in stats.values())
    assert set(stats.keys()) == {"median_ms", "mean_ms", "min_ms", "max_ms"}


def test_compute_timing_stats_single():
    stats = compute_timing_stats([0.200])
    assert stats["median_ms"] == pytest.approx(200.0)
    assert stats["mean_ms"] == pytest.approx(200.0)
    assert stats["min_ms"] == pytest.approx(200.0)
    assert stats["max_ms"] == pytest.approx(200.0)


def test_compute_timing_stats_odd_count():
    latencies = [0.150, 0.180, 0.210]
    stats = compute_timing_stats(latencies)
    assert abs(stats["median_ms"] - 180.0) < 1e-6
    assert abs(stats["mean_ms"] - 180.0) < 1e-6
    assert abs(stats["min_ms"] - 150.0) < 1e-6
    assert abs(stats["max_ms"] - 210.0) < 1e-6


def test_compute_timing_stats_even_count():
    latencies = [0.100, 0.200, 0.300, 0.400]
    stats = compute_timing_stats(latencies)
    assert abs(stats["median_ms"] - 250.0) < 1e-6
    assert abs(stats["mean_ms"] - 250.0) < 1e-6
    assert abs(stats["min_ms"] - 100.0) < 1e-6
    assert abs(stats["max_ms"] - 400.0) < 1e-6


def test_compute_timing_stats_unordered_input():
    """Input need not be sorted; median/min/max must still be correct."""
    latencies = [0.300, 0.100, 0.200]
    stats = compute_timing_stats(latencies)
    assert abs(stats["median_ms"] - 200.0) < 1e-6
    assert abs(stats["min_ms"] - 100.0) < 1e-6
    assert abs(stats["max_ms"] - 300.0) < 1e-6


def test_compute_timing_stats_typical_saccade_range():
    """Typical saccade latencies 150–300 ms; mean should be in that range."""
    latencies = [0.165, 0.180, 0.200, 0.220, 0.250]
    stats = compute_timing_stats(latencies)
    assert 150.0 < stats["mean_ms"] < 300.0
