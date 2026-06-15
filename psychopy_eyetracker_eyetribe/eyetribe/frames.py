# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Eye Tribe frame data model + parser + state-bitmask decoder (PsychoPy-free)."""

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
    """2-D gaze or pupil-centre coordinate (screen pixels or normalised)."""

    x: float
    y: float


@dataclass(frozen=True)
class EyeData:
    """Per-eye data block extracted from an Eye Tribe frame."""

    raw: Point
    avg: Point
    psize: float
    pcenter: Point


@dataclass(frozen=True)
class TrackingState:
    """Named-boolean view of the Eye Tribe state bitmask."""

    gaze: bool
    eyes: bool
    presence: bool
    fail: bool
    lost: bool

    @classmethod
    def from_int(cls, state: int) -> "TrackingState":
        """Decode a raw Eye Tribe ``state`` bitmask into named boolean flags."""
        return cls(
            gaze=bool(state & STATE_TRACKING_GAZE),
            eyes=bool(state & STATE_TRACKING_EYES),
            presence=bool(state & STATE_TRACKING_PRESENCE),
            fail=bool(state & STATE_TRACKING_FAIL),
            lost=bool(state & STATE_TRACKING_LOST),
        )


@dataclass(frozen=True)
class Frame:
    """Parsed Eye Tribe gaze frame (one per pushed JSON message)."""

    time_ms: int
    fix: bool
    state: int
    raw: Point
    avg: Point
    left: EyeData
    right: EyeData

    def gaze(self, source: GazeSource = "raw") -> Point:
        """Return the combined gaze point for the requested source."""
        if source == "avg":
            return self.avg
        return self.raw

    def is_gaze_valid(self) -> bool:
        """True when STATE_TRACKING_GAZE is set and neither FAIL nor LOST.

        State-level check only: an uncalibrated tracker sets GAZE but reports 0,0.
        The calibrated + in-bounds guard lives in the EyeTracker (Phase 3).
        """
        return (
            bool(self.state & STATE_TRACKING_GAZE)
            and not bool(self.state & STATE_TRACKING_FAIL)
            and not bool(self.state & STATE_TRACKING_LOST)
        )


def _parse_point(d: Any, ctx: str) -> Point:
    if not isinstance(d, dict):
        raise FrameParseError(f"{ctx}: expected dict, got {type(d).__name__}")
    try:
        return Point(x=float(d["x"]), y=float(d["y"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise FrameParseError(f"{ctx}: {exc}") from exc


def _parse_eye(d: Any, ctx: str) -> EyeData:
    if not isinstance(d, dict):
        raise FrameParseError(f"{ctx}: expected dict, got {type(d).__name__}")
    try:
        return EyeData(
            raw=_parse_point(d["raw"], f"{ctx}.raw"),
            avg=_parse_point(d["avg"], f"{ctx}.avg"),
            psize=float(d["psize"]),
            pcenter=_parse_point(d["pcenter"], f"{ctx}.pcenter"),
        )
    except FrameParseError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise FrameParseError(f"{ctx}: {exc}") from exc


def parse_frame(payload: dict[str, Any]) -> Frame:
    """Parse a raw Eye Tribe frame dict into a :class:`Frame`.

    Raises :class:`FrameParseError` on any malformed input so callers can log and skip
    without crashing the reader.
    """
    if not isinstance(payload, dict):
        raise FrameParseError(f"payload must be a dict, got {type(payload).__name__}")
    try:
        return Frame(
            time_ms=int(payload["time"]),
            fix=bool(payload["fix"]),
            state=int(payload["state"]),
            raw=_parse_point(payload["raw"], "raw"),
            avg=_parse_point(payload["avg"], "avg"),
            left=_parse_eye(payload["lefteye"], "lefteye"),
            right=_parse_eye(payload["righteye"], "righteye"),
        )
    except FrameParseError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise FrameParseError(str(exc)) from exc
