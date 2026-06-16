# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""CI-runnable tests for EyeTracker._eyeTrackerToDisplayCoords / _displayToEyeTrackerCoords.

Phase 9 fix: the coordinate methods now delegate to the ioHub Display device's
``_pixel2DisplayCoord`` / ``display2PIxelCoord`` methods instead of the defunct
``getBounds()`` path.  These tests inject a stub ``_display_device`` to guard the
delegation in CI without a running ioHub subprocess.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

psychopy = pytest.importorskip("psychopy", reason="PsychoPy not installed")

from psychopy.iohub.devices.eyetracker import EyeTrackerDevice  # noqa: E402

from psychopy_eyetracker_eyetribe.eyetribe.eyetracker import EyeTracker  # noqa: E402

SCREEN_W = 1920
SCREEN_H = 1080


# ── helpers ───────────────────────────────────────────────────────────────────


def _reset_singleton() -> None:
    EyeTrackerDevice._INSTANCE = None
    if "_INSTANCE" in EyeTracker.__dict__:
        EyeTracker._INSTANCE = None  # type: ignore[attr-defined]


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


def _make_tracker_with_stub_display(
    pixel2display_fn: Any, display2pixel_fn: Any, display_index: int = 0
) -> EyeTracker:
    """Build an EyeTracker with a stub _display_device injected."""
    _reset_singleton()
    # Port 1 is not actually connected; we only test the coordinate methods.
    t = EyeTracker(dconfig=_make_dconfig(1))
    stub = MagicMock()
    stub.getIndex.return_value = display_index
    stub._pixel2DisplayCoord.side_effect = pixel2display_fn
    stub.display2PIxelCoord.side_effect = display2pixel_fn
    t._display_device = stub
    return t


# ── forward: _eyeTrackerToDisplayCoords delegates correctly ──────────────────


def test_forward_delegates_to_pixel2DisplayCoord() -> None:
    """_eyeTrackerToDisplayCoords must call _display_device._pixel2DisplayCoord."""
    called_with: list[Any] = []

    def fake_p2d(px: float, py: float, idx: int) -> tuple[float, float]:
        called_with.extend([px, py, idx])
        # pix units: centre origin, Y-up  →  (0, 0) for screen centre (960, 540)
        return px - SCREEN_W / 2, -(py - SCREEN_H / 2)

    t = _make_tracker_with_stub_display(fake_p2d, lambda x, y, i: (x, y))
    result = t._eyeTrackerToDisplayCoords((960.0, 540.0))

    assert called_with == [960.0, 540.0, 0], f"stub not called correctly: {called_with}"
    assert abs(result[0]) < 1e-9, f"expected x=0, got {result[0]}"
    assert abs(result[1]) < 1e-9, f"expected y=0, got {result[1]}"

    _reset_singleton()


def test_forward_known_pixel_in_display_bounds() -> None:
    """Screen centre pixel maps inside Display bounds (i.e. non-raw coords returned)."""

    def pix_units(px: float, py: float, idx: int) -> tuple[float, float]:  # noqa: ARG001
        return px - SCREEN_W / 2, -(py - SCREEN_H / 2)

    t = _make_tracker_with_stub_display(pix_units, lambda x, y, i: (x, y))
    # Screen centre (960, 540) → pix coords (0, 0)
    cx, cy = t._eyeTrackerToDisplayCoords((960.0, 540.0))
    assert abs(cx) < 1e-9 and abs(cy) < 1e-9

    # Top-left (0, 0) → pix coords (-960, 540)
    tlx, tly = t._eyeTrackerToDisplayCoords((0.0, 0.0))
    assert abs(tlx - (-SCREEN_W / 2)) < 1e-6
    assert abs(tly - (SCREEN_H / 2)) < 1e-6

    # Bottom-right (1920, 1080) → pix coords (960, -540)
    brx, bry = t._eyeTrackerToDisplayCoords((float(SCREEN_W), float(SCREEN_H)))
    assert abs(brx - (SCREEN_W / 2)) < 1e-6
    assert abs(bry - (-SCREEN_H / 2)) < 1e-6

    _reset_singleton()


# ── inverse: _displayToEyeTrackerCoords delegates correctly ──────────────────


def test_inverse_delegates_to_display2PIxelCoord() -> None:
    """_displayToEyeTrackerCoords must call _display_device.display2PIxelCoord."""
    called_with: list[Any] = []

    def fake_d2p(x: float, y: float, idx: int) -> tuple[float, float]:
        called_with.extend([x, y, idx])
        return x + SCREEN_W / 2, -(y - SCREEN_H / 2)

    t = _make_tracker_with_stub_display(lambda px, py, i: (px, py), fake_d2p)
    result = t._displayToEyeTrackerCoords(0.0, 0.0)

    assert called_with == [0.0, 0.0, 0], f"stub not called correctly: {called_with}"
    assert abs(result[0] - SCREEN_W / 2) < 1e-9
    assert abs(result[1] - SCREEN_H / 2) < 1e-9

    _reset_singleton()


# ── fallback: no display device → pixel pass-through ─────────────────────────


def test_forward_passthrough_when_no_display_device() -> None:
    """When _display_device raises AttributeError, raw pixel coords are returned."""
    _reset_singleton()
    t = EyeTracker(dconfig=_make_dconfig(1))
    # _display_device is not set / raises on access — simulate by not injecting stub
    # The base class leaves _display_device as a plain attribute that may be None or absent.
    t._display_device = None  # type: ignore[assignment]

    result = t._eyeTrackerToDisplayCoords((400.0, 300.0))
    assert result == (400.0, 300.0), f"expected pixel passthrough, got {result}"

    _reset_singleton()


def test_inverse_passthrough_when_no_display_device() -> None:
    """When _display_device raises AttributeError, display coords are returned unchanged."""
    _reset_singleton()
    t = EyeTracker(dconfig=_make_dconfig(1))
    t._display_device = None  # type: ignore[assignment]

    result = t._displayToEyeTrackerCoords(100.0, -200.0)
    assert result == (100.0, -200.0), f"expected passthrough, got {result}"

    _reset_singleton()
