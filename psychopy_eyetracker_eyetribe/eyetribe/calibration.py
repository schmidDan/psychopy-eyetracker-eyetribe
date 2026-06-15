# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Eye Tribe calibration sequencing + calibresult parsing (PsychoPy-free).

``CalibrationSequencer`` drives the device-protocol message exchange.
``parse_calibresult`` converts the server payload to a typed result.
``point_layout`` returns the normalized target positions for 5, 9, or 12 points.

No PsychoPy imports here — this module is fully unit-testable without a window.
The PsychoPy drawing/loop lives in ``EyeTracker.runSetupProcedure``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

DEFAULT_TARGET_COUNT = 9
SUPPORTED_TARGET_COUNTS = (5, 9, 12)
SETTLE_MS = 750  # ms to let the participant fixate before sampling starts
SAMPLE_MS = 1000  # ms sampling window per calibration point

# Normalized (x, y) target positions in Eye Tribe screen space.
# Origin is top-left; values are fractions of screen width/height (0..1).
# Centre-first so an early abort leaves the device in a defined state.
_LAYOUTS: dict[int, tuple[tuple[float, float], ...]] = {
    5: (
        (0.5, 0.5),
        (0.1, 0.1),
        (0.9, 0.1),
        (0.9, 0.9),
        (0.1, 0.9),
    ),
    9: (
        (0.5, 0.5),
        (0.1, 0.5),
        (0.9, 0.5),
        (0.1, 0.1),
        (0.5, 0.1),
        (0.9, 0.1),
        (0.9, 0.9),
        (0.5, 0.9),
        (0.1, 0.9),
    ),
    12: (
        (0.5, 0.5),
        (0.1, 0.1),
        (0.9, 0.1),
        (0.9, 0.9),
        (0.1, 0.9),
        (0.1, 0.5),
        (0.9, 0.5),
        (0.5, 0.1),
        (0.5, 0.9),
        (0.3, 0.3),
        (0.7, 0.3),
        (0.3, 0.7),
    ),
}


@dataclass(frozen=True)
class CalibrationResult:
    success: bool
    avg_error_deg: float
    per_point: tuple[dict[str, Any], ...]


def point_layout(target_count: int) -> tuple[tuple[float, float], ...]:
    """Return normalized (x, y) target positions for *target_count* calibration points.

    Coordinates are in Eye Tribe screen space: origin top-left, values in [0, 1].
    Multiply by ``screen_w`` / ``screen_h`` to get pixel coordinates for the API.
    """
    if target_count not in SUPPORTED_TARGET_COUNTS:
        raise ValueError(
            f"target_count must be one of {SUPPORTED_TARGET_COUNTS}, got {target_count}"
        )
    return _LAYOUTS[target_count]


def parse_calibresult(payload: dict[str, Any]) -> CalibrationResult:
    """Parse the Eye Tribe ``calibresult`` object into a :class:`CalibrationResult`."""
    success = bool(payload.get("result", False))
    avg_error = float(payload.get("deg", 0.0))
    per_point = tuple(dict(pt) for pt in payload.get("calibpoints", []))
    return CalibrationResult(success=success, avg_error_deg=avg_error, per_point=per_point)


# Callable type for the transport: takes a full message dict, returns the reply dict.
_RequestFn = Callable[[dict[str, Any]], dict[str, Any]]


class CalibrationSequencer:
    """Drives the Eye Tribe calibration protocol via a transport-provided request callable.

    No PsychoPy dependency; fully unit-testable without a window.

    Parameters
    ----------
    request_fn:
        A callable with the signature ``(msg: dict) -> dict`` that sends *msg*
        to the server and returns the reply.  In production this is
        ``EyeTribeClient._request``; in unit tests it can be any mock.
    """

    def __init__(self, request_fn: _RequestFn) -> None:
        self._request = request_fn

    def start(self, point_count: int) -> dict[str, Any]:
        """Send ``calibration start`` with the total point count."""
        return self._request(
            {
                "category": "calibration",
                "request": "start",
                "values": {"pointcount": point_count},
            }
        )

    def point_start(self, x_px: float, y_px: float) -> dict[str, Any]:
        """Send ``calibration pointstart`` for the target at pixel position *(x_px, y_px)*."""
        return self._request(
            {
                "category": "calibration",
                "request": "pointstart",
                "values": {"x": x_px, "y": y_px},
            }
        )

    def point_end(self) -> dict[str, Any] | None:
        """Send ``calibration pointend`` and return the ``calibresult`` payload if present.

        The real Eye Tribe server includes ``calibresult`` only in the reply to
        the *final* ``pointend``.  The mock returns it for every ``pointend``.
        Callers should use the result from the last call in the sequence.
        """
        reply = self._request({"category": "calibration", "request": "pointend"})
        values = reply.get("values")
        if isinstance(values, dict):
            return values.get("calibresult")
        return None

    def abort(self) -> dict[str, Any]:
        """Send ``calibration abort``; leaves the device in a clean recordable state."""
        return self._request({"category": "calibration", "request": "abort"})

    def clear(self) -> dict[str, Any]:
        """Send ``calibration clear``; resets calibration state before a redo."""
        return self._request({"category": "calibration", "request": "clear"})
