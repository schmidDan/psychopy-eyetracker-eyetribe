# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Eye Tribe ioHub ``EyeTracker`` device (Common Eye Tracker Interface).

STUB. Phase 3 implements recording/polling; Phase 4 coordinate transforms + time-sync;
Phase 5 calibration. Method signatures are provisional pending ``docs/REFERENCES.md``
(read from the installed PsychoPy 2026.1.3 ``EyeTrackerDevice`` source in Phase 0).

Importing this module requires PsychoPy and succeeds so ioHub can discover the device.
"""

from __future__ import annotations

from typing import Any

from psychopy.iohub.devices.eyetracker import EyeTrackerDevice


class EyeTracker(EyeTrackerDevice):
    """ioHub Common Eye Tracker Interface implementation for The Eye Tribe (ET1000)."""

    # The Eye Tribe ``time`` field is epoch milliseconds.
    DEVICE_TIMEBASE_TO_SEC = 0.001

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    # --- timing (Phase 4) ---
    def trackerTime(self) -> float:
        raise NotImplementedError("Phase 4")

    def trackerSec(self) -> float:
        raise NotImplementedError("Phase 4")

    # --- connection / recording lifecycle (Phase 3) ---
    def setConnectionState(self, enable: bool) -> bool:
        raise NotImplementedError("Phase 3")

    def isConnected(self) -> bool:
        raise NotImplementedError("Phase 3")

    def setRecordingState(self, recording: bool) -> bool:
        raise NotImplementedError("Phase 3")

    def isRecordingEnabled(self) -> bool:
        raise NotImplementedError("Phase 3")

    def enableEventReporting(self, enabled: bool = True) -> bool:
        raise NotImplementedError("Phase 3")

    # --- calibration (Phase 5) ---
    def runSetupProcedure(self, calibration_args: dict[str, Any] | None = None) -> int:
        raise NotImplementedError("Phase 5")

    # --- internals ---
    def _poll(self) -> None:
        raise NotImplementedError("Phase 3")

    def _eyeTrackerToDisplayCoords(self, eye_data: Any) -> Any:
        raise NotImplementedError("Phase 4")

    def _displayToEyeTrackerCoords(self, x: float, y: float) -> Any:
        raise NotImplementedError("Phase 4")
