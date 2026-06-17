# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""ioHub device package for The Eye Tribe (namespace: ...eyetracker.hw.eyetribe).

``EyeTracker`` is exported lazily (PEP 562) so the PsychoPy-free core modules in this
package (``eyetribe_client``, ``frames``, ``time_sync``, ``calibration``)
can be imported and unit-tested without PsychoPy installed. PsychoPy is pulled in only
when ioHub accesses ``EyeTracker`` at device-load time.
"""

from __future__ import annotations

from typing import Any

__all__ = ["EyeTracker", "BinocularEyeSampleEvent", "FixationStartEvent", "FixationEndEvent"]

# Event class names that ioHub's import_device requests from this module at load time.
_IOHUB_EVENT_CLASSES = {"BinocularEyeSampleEvent", "FixationStartEvent", "FixationEndEvent"}


def __getattr__(name: str) -> Any:
    if name == "EyeTracker":
        from .eyetracker import EyeTracker

        return EyeTracker
    if name in _IOHUB_EVENT_CLASSES:
        from psychopy.iohub.devices.eyetracker import (
            BinocularEyeSampleEvent,
            FixationEndEvent,
            FixationStartEvent,
        )

        _cls_map = {
            "BinocularEyeSampleEvent": BinocularEyeSampleEvent,
            "FixationStartEvent": FixationStartEvent,
            "FixationEndEvent": FixationEndEvent,
        }
        return _cls_map[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
