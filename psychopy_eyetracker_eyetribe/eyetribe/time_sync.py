# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Tracker <-> PsychoPy clock-offset model (PsychoPy-free).

The Eye Tribe ``time`` field is a **monotonic millisecond counter** (relative,
~uptime — NOT Unix epoch; confirmed against hardware on 2026-06-15, observed
≈ 1.889 × 10⁸ ms at ~30 Hz).  The separate ``timestamp`` field is the wall-clock
string and is not used for synchronisation.

This module maps ``time`` (ms) onto the PsychoPy timebase via a measured offset::

    psychopy_time = tracker_time_s + offset

where::

    offset = (local_time_s − rtt_s / 2) − tracker_time_s

The RTT correction halves the request/reply round-trip time to estimate the one-way
transmit delay.  For streaming frames (no per-frame RTT) pass ``rtt_s=0.0``.

:class:`ClockSync` re-estimates the offset at most once every
``reestimate_interval_s`` seconds (default 5 s) to track slow clock drift without
over-reacting to individual noisy samples.  See ``docs/coordinate_systems.md``
(timing section) for the residual latency budget.
"""

from __future__ import annotations

REESTIMATE_INTERVAL_S: float = 5.0


class ClockSync:
    """Estimate and maintain the Eye-Tribe-to-PsychoPy clock offset.

    Call :meth:`update` each time a frame arrives (or once at recording start with
    a measured RTT).  Retrieve PsychoPy-domain timestamps with
    :meth:`to_psychopy_time`.
    """

    def __init__(self, reestimate_interval_s: float = REESTIMATE_INTERVAL_S) -> None:
        """Create an uninitialised sync; call :meth:`update` before converting times."""
        self.reestimate_interval_s = reestimate_interval_s
        self._offset: float = 0.0
        self._last_update_local_s: float = 0.0
        self._initialized: bool = False

    # -- public properties -----------------------------------------------

    @property
    def is_initialized(self) -> bool:
        """True once the first :meth:`update` call has been processed."""
        return self._initialized

    @property
    def offset(self) -> float:
        """Current offset in seconds: ``psychopy_time = tracker_s + offset``."""
        return self._offset

    # -- public methods --------------------------------------------------

    def update(
        self,
        tracker_time_ms: int,
        local_time_s: float,
        rtt_s: float = 0.0,
    ) -> None:
        """Refresh the offset from a (tracker_ms, local_s, round-trip) sample.

        On the first call the offset is always recorded.  Subsequent calls only
        update the offset if at least ``reestimate_interval_s`` seconds of
        *local* clock time have elapsed since the last update.

        Parameters
        ----------
        tracker_time_ms:
            Eye Tribe monotonic timestamp in milliseconds (the ``time`` field).
        local_time_s:
            PsychoPy (local) clock time at which the sample was received, in seconds.
        rtt_s:
            Measured request/reply round-trip time in seconds.  Pass ``0.0``
            (default) for streaming frames where no per-frame RTT is available.
        """
        tracker_s = tracker_time_ms / 1000.0
        corrected_local = local_time_s - rtt_s / 2.0
        new_offset = corrected_local - tracker_s

        if not self._initialized:
            self._offset = new_offset
            self._last_update_local_s = local_time_s
            self._initialized = True
        elif local_time_s - self._last_update_local_s >= self.reestimate_interval_s:
            self._offset = new_offset
            self._last_update_local_s = local_time_s

    def to_psychopy_time(self, tracker_time_ms: int) -> float:
        """Convert an Eye Tribe monotonic-ms timestamp to PsychoPy seconds.

        Parameters
        ----------
        tracker_time_ms:
            Eye Tribe ``time`` field value in milliseconds.

        Returns
        -------
        Estimated PsychoPy clock time in seconds.

        Raises
        ------
        RuntimeError
            If called before :meth:`update` has been invoked at least once.
        """
        if not self._initialized:
            raise RuntimeError(
                "ClockSync.to_psychopy_time() called before update(); "
                "call update() with the first frame to initialise the offset."
            )
        return tracker_time_ms / 1000.0 + self._offset
