# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Pixel <-> display coordinate transforms (PsychoPy-free).

Eye Tribe gaze coordinates are in screen pixels with origin at the top-left corner.
This module normalises them to [0, 1] (origin top-left) and then maps to the ioHub
Display coordinate bounds, which are expressed as (left, top, right, bottom) in the
display's native unit (pix, norm, height, deg).

Normalisation step::

    norm_x = x_px / screen_w   # 0 = left edge, 1 = right edge
    norm_y = y_px / screen_h   # 0 = top  edge, 1 = bottom edge

Display-unit mapping (note: ``bottom < top`` in Y-up display coordinates)::

    disp_x = left  + norm_x * (right  - left)
    disp_y = top   + norm_y * (bottom - top)

No PsychoPy imports; bounds are passed in as plain floats so the module is
testable without a PsychoPy installation.  See ``docs/coordinate_systems.md``
for a diagram and worked example.
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
    """Map Eye Tribe screen pixels (origin top-left) to ioHub display coords.

    Parameters
    ----------
    x_px, y_px:
        Gaze point in screen pixels, origin top-left.
    screen_w, screen_h:
        Server-reported screen resolution (``screenresw`` / ``screenresh``).
    display_bounds:
        ioHub Display bounds as ``(left, top, right, bottom)`` in the display unit
        in use (``pix`` / ``norm`` / ``height`` / ``deg``).

    Returns
    -------
    ``(disp_x, disp_y)`` in the display unit.
    """
    norm_x = x_px / screen_w
    norm_y = y_px / screen_h
    left, top, right, bottom = display_bounds
    return left + norm_x * (right - left), top + norm_y * (bottom - top)


def display_to_eyetribe_pixels(
    x: float,
    y: float,
    screen_w: int,
    screen_h: int,
    display_bounds: DisplayBounds,
) -> tuple[float, float]:
    """Inverse of :func:`eyetribe_pixels_to_display`.

    Parameters
    ----------
    x, y:
        Display-unit coordinates.
    screen_w, screen_h:
        Server-reported screen resolution.
    display_bounds:
        ioHub Display bounds as ``(left, top, right, bottom)`` in the display unit.

    Returns
    -------
    ``(x_px, y_px)`` in screen pixels, origin top-left.
    """
    left, top, right, bottom = display_bounds
    norm_x = (x - left) / (right - left)
    norm_y = (y - top) / (bottom - top)
    return norm_x * screen_w, norm_y * screen_h
