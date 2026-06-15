# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Pixel <-> display coordinate transforms (PsychoPy-free).

STUB. Phase 4. The ioHub Display bounds and unit are passed in as plain numbers so
this module never imports PsychoPy.
"""

from __future__ import annotations

DisplayBounds = tuple[float, float, float, float]  # left, top, right, bottom (display units)


def eyetribe_pixels_to_display(
    x_px: float,
    y_px: float,
    screen_w: int,
    screen_h: int,
    display_bounds: DisplayBounds,
) -> tuple[float, float]:
    """Map Eye Tribe screen pixels (origin top-left) to ioHub display coords. Phase 4."""
    raise NotImplementedError("Phase 4")


def display_to_eyetribe_pixels(
    x: float,
    y: float,
    screen_w: int,
    screen_h: int,
    display_bounds: DisplayBounds,
) -> tuple[float, float]:
    """Inverse of :func:`eyetribe_pixels_to_display`. Phase 4."""
    raise NotImplementedError("Phase 4")
