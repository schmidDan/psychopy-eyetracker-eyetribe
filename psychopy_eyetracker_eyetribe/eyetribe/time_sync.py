# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Tracker <-> PsychoPy clock-offset model (PsychoPy-free).

STUB. Phase 4. The Eye Tribe ``time`` field is epoch milliseconds; this maps it onto
the PsychoPy timebase via an offset re-estimated periodically.
"""

from __future__ import annotations

REESTIMATE_INTERVAL_S = 5.0


class ClockSync:
    """Estimate and maintain the Eye-Tribe-to-PsychoPy clock offset. Phase 4."""

    def __init__(self, reestimate_interval_s: float = REESTIMATE_INTERVAL_S) -> None:
        self.reestimate_interval_s = reestimate_interval_s

    def update(self, tracker_time_ms: int, local_time_s: float, rtt_s: float = 0.0) -> None:
        """Refresh the offset from a (tracker_ms, local_s, round-trip) sample. Phase 4."""
        raise NotImplementedError("Phase 4")

    def to_psychopy_time(self, tracker_time_ms: int) -> float:
        """Convert an Eye Tribe epoch-ms timestamp to PsychoPy seconds. Phase 4."""
        raise NotImplementedError("Phase 4")
