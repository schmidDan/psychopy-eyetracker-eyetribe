# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Eye Tribe calibration sequencing + calibresult parsing (PsychoPy-free).

STUB. Phase 5. The PsychoPy drawing/loop lives in ``EyeTracker.runSetupProcedure``;
this module holds the device-protocol sequencing so it is unit-testable without a window.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_TARGET_COUNT = 9
SUPPORTED_TARGET_COUNTS = (5, 9, 12)
SETTLE_MS = 750
SAMPLE_MS = 1000


@dataclass(frozen=True)
class CalibrationResult:
    success: bool
    avg_error_deg: float
    per_point: tuple[dict[str, Any], ...]


def parse_calibresult(payload: dict[str, Any]) -> CalibrationResult:
    """Parse the Eye Tribe ``calibresult`` object into a :class:`CalibrationResult`. Phase 5."""
    raise NotImplementedError("Phase 5")
