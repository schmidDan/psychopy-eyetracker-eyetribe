# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Spatial accuracy, precision, and timing metrics for eye-tracker validation.

PsychoPy-free; importable without a window.  The functions here are the
numerical core used by ``tests/manual/validation_experiment.py`` to compute
the Phase 10c metrics and write them to ``docs/hardware_validation.md``.

Coordinate convention: all gaze and target positions are in **screen pixels**
with the origin at the top-left corner (the Eye Tribe native format).
"""

from __future__ import annotations

import math
from typing import Sequence


def euclidean_degrees(
    dx_px: float,
    dy_px: float,
    screen_w_px: int,
    screen_h_px: int,
    screen_w_cm: float,
    screen_h_cm: float,
    viewing_distance_cm: float,
) -> float:
    """Return the Euclidean offset between two points in visual degrees.

    Parameters
    ----------
    dx_px, dy_px:
        Pixel offset (target − gaze or sample_i+1 − sample_i), top-left origin.
    screen_w_px, screen_h_px:
        Screen resolution in pixels.
    screen_w_cm, screen_h_cm:
        Physical screen dimensions in centimetres.
    viewing_distance_cm:
        Eye-to-screen distance in centimetres.

    Returns
    -------
    Visual angle in degrees (always non-negative).
    """
    cm_per_px_w = screen_w_cm / screen_w_px
    cm_per_px_h = screen_h_cm / screen_h_px
    dx_cm = dx_px * cm_per_px_w
    dy_cm = dy_px * cm_per_px_h
    offset_cm = math.hypot(dx_cm, dy_cm)
    return math.degrees(math.atan2(offset_cm, viewing_distance_cm))


def compute_accuracy(
    targets: Sequence[tuple[float, float]],
    gazes: Sequence[tuple[float, float]],
    screen_w_px: int,
    screen_h_px: int,
    screen_w_cm: float,
    screen_h_cm: float,
    viewing_distance_cm: float,
) -> float:
    """Mean Euclidean accuracy in visual degrees across target–gaze pairs.

    Parameters
    ----------
    targets:
        Known target positions ``(x, y)`` in screen pixels, top-left origin.
    gazes:
        Corresponding mean gaze positions (one per target), same units.
    screen_w_px, screen_h_px:
        Screen resolution in pixels.
    screen_w_cm, screen_h_cm:
        Physical screen dimensions in centimetres.
    viewing_distance_cm:
        Eye-to-screen distance in centimetres.

    Returns
    -------
    Mean offset in degrees; ``float('nan')`` for empty *targets*.
    Raises :class:`ValueError` when *targets* and *gazes* lengths differ.
    """
    if not targets:
        return float("nan")
    if len(targets) != len(gazes):
        raise ValueError(
            f"targets ({len(targets)}) and gazes ({len(gazes)}) must have equal length"
        )
    offsets = [
        euclidean_degrees(
            tx - gx,
            ty - gy,
            screen_w_px,
            screen_h_px,
            screen_w_cm,
            screen_h_cm,
            viewing_distance_cm,
        )
        for (tx, ty), (gx, gy) in zip(targets, gazes)
    ]
    return sum(offsets) / len(offsets)


def compute_precision(
    gaze_samples: Sequence[tuple[float, float]],
    screen_w_px: int,
    screen_h_px: int,
    screen_w_cm: float,
    screen_h_cm: float,
    viewing_distance_cm: float,
) -> float:
    """RMS inter-sample distance in visual degrees (precision / jitter).

    Computed as the root-mean-square of consecutive sample-to-sample distances
    across the recorded fixation period, averaged over all target windows.

    Parameters
    ----------
    gaze_samples:
        Sequence of ``(x, y)`` gaze positions (screen pixels, top-left origin)
        recorded while the participant fixated a single target.
    screen_w_px, screen_h_px:
        Screen resolution in pixels.
    screen_w_cm, screen_h_cm:
        Physical screen dimensions in centimetres.
    viewing_distance_cm:
        Eye-to-screen distance in centimetres.

    Returns
    -------
    RMS distance in degrees; ``0.0`` for ≤ 1 sample; ``float('nan')`` for empty.
    """
    n = len(gaze_samples)
    if n == 0:
        return float("nan")
    if n == 1:
        return 0.0
    squared: list[float] = [
        euclidean_degrees(
            gaze_samples[i + 1][0] - gaze_samples[i][0],
            gaze_samples[i + 1][1] - gaze_samples[i][1],
            screen_w_px,
            screen_h_px,
            screen_w_cm,
            screen_h_cm,
            viewing_distance_cm,
        )
        ** 2
        for i in range(n - 1)
    ]
    return math.sqrt(sum(squared) / len(squared))


def compute_timing_stats(latencies_s: Sequence[float]) -> dict[str, float]:
    """Summarise stimulus-onset-to-gaze-shift latencies.

    Parameters
    ----------
    latencies_s:
        Measured latencies in seconds (one per target presentation).

    Returns
    -------
    Dict with ``"median_ms"``, ``"mean_ms"``, ``"min_ms"``, ``"max_ms"``
    (all in milliseconds); all values are ``float('nan')`` for empty input.
    """
    if not latencies_s:
        nan = float("nan")
        return {"median_ms": nan, "mean_ms": nan, "min_ms": nan, "max_ms": nan}
    ms = sorted(v * 1000.0 for v in latencies_s)
    n = len(ms)
    mid = n // 2
    median = ms[mid] if n % 2 else (ms[mid - 1] + ms[mid]) / 2.0
    return {
        "median_ms": median,
        "mean_ms": sum(ms) / n,
        "min_ms": ms[0],
        "max_ms": ms[-1],
    }
