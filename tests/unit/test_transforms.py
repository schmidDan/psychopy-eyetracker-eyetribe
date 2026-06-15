"""Unit tests for psychopy_eyetracker_eyetribe.eyetribe.transforms.

Acceptance criteria (Phase 4):
- Known device pixel coords map to expected display-unit coords for pix, norm,
  height, and deg, asserted numerically.
- forward∘inverse round-trips within 1e-6 in normalised space.
"""

from __future__ import annotations

import pytest

from psychopy_eyetracker_eyetribe.eyetribe.transforms import (
    DisplayBounds,
    display_to_eyetribe_pixels,
    eyetribe_pixels_to_display,
)

# ── screen reference ──────────────────────────────────────────────────────────

SCREEN_W = 1920
SCREEN_H = 1080

# ── standard display bounds for a 1920×1080 monitor ──────────────────────────
# Each unit system uses a (left, top, right, bottom) tuple expressed in that unit.
# In all Y-up systems top > 0 and bottom < 0; left < 0 and right > 0.

BOUNDS_PIX: DisplayBounds = (-960.0, 540.0, 960.0, -540.0)
BOUNDS_NORM: DisplayBounds = (-1.0, 1.0, 1.0, -1.0)
BOUNDS_HEIGHT: DisplayBounds = (-960 / 1080, 0.5, 960 / 1080, -0.5)
BOUNDS_DEG: DisplayBounds = (-12.85, 7.2, 12.85, -7.2)  # example monitor calibration

# Pixel-passthrough bounds (Y-down, matches ioHub no-display-device fallback):
# disp coords == screen pixels (no spatial transform, used in integration tests).
BOUNDS_PASSTHROUGH: DisplayBounds = (0.0, 0.0, float(SCREEN_W), float(SCREEN_H))


# ── import smoke ──────────────────────────────────────────────────────────────


def test_imports_without_psychopy() -> None:
    assert callable(eyetribe_pixels_to_display)
    assert callable(display_to_eyetribe_pixels)


# ── forward transform: known coords ──────────────────────────────────────────


@pytest.mark.parametrize(
    "bounds,expected",
    [
        (BOUNDS_PIX, (0.0, 0.0)),
        (BOUNDS_NORM, (0.0, 0.0)),
        (BOUNDS_HEIGHT, (0.0, 0.0)),
        (BOUNDS_DEG, (0.0, 0.0)),
    ],
    ids=["pix", "norm", "height", "deg"],
)
def test_center_pixel_maps_to_display_origin(
    bounds: DisplayBounds, expected: tuple[float, float]
) -> None:
    """Screen centre (960, 540) → display origin (0, 0) for all Y-up unit systems."""
    x, y = eyetribe_pixels_to_display(960, 540, SCREEN_W, SCREEN_H, bounds)
    assert abs(x - expected[0]) < 1e-9
    assert abs(y - expected[1]) < 1e-9


@pytest.mark.parametrize(
    "px,py,bounds,ex,ey",
    [
        # pix — corners
        (0, 0, BOUNDS_PIX, -960.0, 540.0),
        (1920, 1080, BOUNDS_PIX, 960.0, -540.0),
        # norm — corners
        (0, 0, BOUNDS_NORM, -1.0, 1.0),
        (1920, 1080, BOUNDS_NORM, 1.0, -1.0),
        # height — corners
        (0, 0, BOUNDS_HEIGHT, -960 / 1080, 0.5),
        (1920, 1080, BOUNDS_HEIGHT, 960 / 1080, -0.5),
        # deg — corners
        (0, 0, BOUNDS_DEG, -12.85, 7.2),
        (1920, 1080, BOUNDS_DEG, 12.85, -7.2),
        # passthrough: disp == pixel
        (500, 300, BOUNDS_PASSTHROUGH, 500.0, 300.0),
        (0, 0, BOUNDS_PASSTHROUGH, 0.0, 0.0),
        (1920, 1080, BOUNDS_PASSTHROUGH, 1920.0, 1080.0),
    ],
    ids=[
        "pix-TL",
        "pix-BR",
        "norm-TL",
        "norm-BR",
        "height-TL",
        "height-BR",
        "deg-TL",
        "deg-BR",
        "passthrough-mid",
        "passthrough-TL",
        "passthrough-BR",
    ],
)
def test_known_pixel_to_display(
    px: float, py: float, bounds: DisplayBounds, ex: float, ey: float
) -> None:
    x, y = eyetribe_pixels_to_display(px, py, SCREEN_W, SCREEN_H, bounds)
    assert abs(x - ex) < 1e-6, f"x={x!r} expected {ex!r}"
    assert abs(y - ey) < 1e-6, f"y={y!r} expected {ey!r}"


# ── forward transform: multiple resolutions ───────────────────────────────────


@pytest.mark.parametrize(
    "screen_w,screen_h,bounds",
    [
        (1280, 720, (-1.0, 1.0, 1.0, -1.0)),
        (2560, 1440, (-1.0, 1.0, 1.0, -1.0)),
        (800, 600, (-400.0, 300.0, 400.0, -300.0)),
        (3840, 2160, (-1.0, 1.0, 1.0, -1.0)),
    ],
    ids=["1280x720", "2560x1440", "800x600", "4K"],
)
def test_center_pixel_various_resolutions(
    screen_w: int, screen_h: int, bounds: DisplayBounds
) -> None:
    """Screen centre maps to display origin regardless of resolution."""
    cx, cy = screen_w / 2, screen_h / 2
    x, y = eyetribe_pixels_to_display(cx, cy, screen_w, screen_h, bounds)
    assert abs(x) < 1e-9, f"centre_x={x!r}"
    assert abs(y) < 1e-9, f"centre_y={y!r}"


# ── inverse transform: known coords ──────────────────────────────────────────


@pytest.mark.parametrize(
    "bounds",
    [BOUNDS_PIX, BOUNDS_NORM, BOUNDS_HEIGHT, BOUNDS_DEG, BOUNDS_PASSTHROUGH],
    ids=["pix", "norm", "height", "deg", "passthrough"],
)
def test_display_origin_maps_back_to_center_pixel(bounds: DisplayBounds) -> None:
    """Display origin (0,0) → screen centre for Y-up unit systems.

    Note: passthrough has a different origin (top-left → (0,0) pixel), checked
    separately in test_passthrough_inverse.
    """
    if bounds == BOUNDS_PASSTHROUGH:
        pytest.skip("passthrough origin is top-left, not centre")
    px, py = display_to_eyetribe_pixels(0.0, 0.0, SCREEN_W, SCREEN_H, bounds)
    assert abs(px - 960) < 1e-6
    assert abs(py - 540) < 1e-6


def test_passthrough_origin_maps_to_top_left() -> None:
    px, py = display_to_eyetribe_pixels(0.0, 0.0, SCREEN_W, SCREEN_H, BOUNDS_PASSTHROUGH)
    assert abs(px) < 1e-9
    assert abs(py) < 1e-9


# ── round-trip tests ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bounds",
    [BOUNDS_PIX, BOUNDS_NORM, BOUNDS_HEIGHT, BOUNDS_DEG, BOUNDS_PASSTHROUGH],
    ids=["pix", "norm", "height", "deg", "passthrough"],
)
@pytest.mark.parametrize(
    "px,py",
    [
        (0.0, 0.0),
        (960.0, 540.0),
        (1920.0, 1080.0),
        (100.0, 200.0),
        (1820.0, 970.0),
        (1.0, 1.0),
        (1919.0, 1079.0),
    ],
    ids=["TL", "centre", "BR", "mid1", "mid2", "near-TL", "near-BR"],
)
def test_round_trip_forward_then_inverse(bounds: DisplayBounds, px: float, py: float) -> None:
    """forward(inverse(p)) == p within 1e-6 (acceptance criterion)."""
    disp_x, disp_y = eyetribe_pixels_to_display(px, py, SCREEN_W, SCREEN_H, bounds)
    rpx, rpy = display_to_eyetribe_pixels(disp_x, disp_y, SCREEN_W, SCREEN_H, bounds)
    assert abs(rpx - px) < 1e-6, f"round-trip x: {rpx!r} != {px!r}"
    assert abs(rpy - py) < 1e-6, f"round-trip y: {rpy!r} != {py!r}"


@pytest.mark.parametrize(
    "bounds",
    [BOUNDS_PIX, BOUNDS_NORM, BOUNDS_HEIGHT, BOUNDS_DEG],
    ids=["pix", "norm", "height", "deg"],
)
def test_round_trip_inverse_then_forward(bounds: DisplayBounds) -> None:
    """inverse(forward(d)) == d within 1e-6 (starting from display coords)."""
    left, top, right, bottom = bounds
    test_points = [
        (left, top),
        ((left + right) / 2, (top + bottom) / 2),
        (right, bottom),
        (left / 2, bottom / 2),
    ]
    for dx, dy in test_points:
        px, py = display_to_eyetribe_pixels(dx, dy, SCREEN_W, SCREEN_H, bounds)
        rdx, rdy = eyetribe_pixels_to_display(px, py, SCREEN_W, SCREEN_H, bounds)
        assert abs(rdx - dx) < 1e-6, f"round-trip dx: {rdx!r} != {dx!r}"
        assert abs(rdy - dy) < 1e-6, f"round-trip dy: {rdy!r} != {dy!r}"
