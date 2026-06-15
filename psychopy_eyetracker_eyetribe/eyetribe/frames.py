# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Eye Tribe frame data model + parser + state-bitmask decoder (PsychoPy-free).

STUB. Phase 2 implements ``parse_frame`` and the ``TrackingState`` decoder.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

GazeSource = Literal["raw", "avg"]

# state bitmask (Eye Tribe Tracker API)
STATE_TRACKING_GAZE = 0x1
STATE_TRACKING_EYES = 0x2
STATE_TRACKING_PRESENCE = 0x4
STATE_TRACKING_FAIL = 0x8
STATE_TRACKING_LOST = 0x10


class FrameParseError(ValueError):
    """Raised when a server frame cannot be parsed into a :class:`Frame`."""


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class EyeData:
    raw: Point
    avg: Point
    psize: float
    pcenter: Point


@dataclass(frozen=True)
class Frame:
    time_ms: int
    fix: bool
    state: int
    raw: Point
    avg: Point
    left: EyeData
    right: EyeData

    def gaze(self, source: GazeSource = "raw") -> Point:
        """Return the combined gaze point for the requested source. Phase 2."""
        raise NotImplementedError("Phase 2")

    def is_gaze_valid(self) -> bool:
        """True when STATE_TRACKING_GAZE is set and neither FAIL nor LOST. Phase 2."""
        raise NotImplementedError("Phase 2")


def parse_frame(payload: dict[str, Any]) -> Frame:
    """Parse a raw Eye Tribe frame dict into a :class:`Frame`. Phase 2."""
    raise NotImplementedError("Phase 2")
