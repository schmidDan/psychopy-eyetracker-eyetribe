# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Builder Eyetracker backend registration for The Eye Tribe.

STUB. Phase 6 implements the Builder parameter fields (host, port, gaze source,
calibration target count). Confirmed base class (PsychoPy 2026.1.3): ``EyetrackerBackend``
(module ``psychopy.experiment.components.settings.eyetracking``); Phase 6 mirrors the in-tree
``MouseGazeEyetrackerBackend``. The guarded import keeps the settings entry point resolvable
in any environment.
"""

from __future__ import annotations

try:  # pragma: no cover - base availability varies by PsychoPy build
    from psychopy.experiment.components.settings.eyetracking import EyetrackerBackend as _Base
except Exception:  # noqa: BLE001 - intentional: keep the entry point importable in any env
    _Base = object  # type: ignore[assignment, misc]


class EyeTribeEyetrackerBackend(_Base):  # type: ignore[misc, valid-type]
    """Exposes 'Eye Tribe' in the Builder Eyetracker component dropdown. Phase 6."""

    label = "Eye Tribe"
    deviceClasses = ["eyetracker.hw.eyetribe.EyeTracker"]
