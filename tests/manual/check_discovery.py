# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""[Phase 0 diagnostic] Determine how PsychoPy exposes the Eye Tribe plugin device.

Run with the Standalone interpreter on Windows:

    & $py "$repo\tests\manual\check_discovery.py"

A bare ``import psychopy.iohub.devices.eyetracker.hw.eyetribe`` does NOT resolve until
PsychoPy's plugin system has been activated. This script reports the entry points, tries
the known plugin-activation hooks, and then probes the candidate import paths, so we can
pin the exact mechanism in docs/REFERENCES.md and the discovery test. Paste the output back.
"""

from __future__ import annotations

import importlib
from importlib.metadata import entry_points


def _try(label: str, fn) -> None:
    try:
        print(f"[ok] {label}: {fn()}")
    except Exception as exc:  # noqa: BLE001 - diagnostic: report, never crash
        print(f"[--] {label}: {type(exc).__name__}: {exc}")


def main() -> int:
    import psychopy

    print("PsychoPy", getattr(psychopy, "__version__", "?"))
    print(
        "entry points (psychopy.iohub.devices.eyetracker):",
        {ep.name: ep.value for ep in entry_points(group="psychopy.iohub.devices.eyetracker")},
    )

    try:
        from psychopy import plugins

        print("psychopy.plugins funcs:", [f for f in dir(plugins) if not f.startswith("_")])
        for fname in ("scanPlugins", "activatePlugins"):
            fn = getattr(plugins, fname, None)
            if callable(fn):
                _try(f"plugins.{fname}()", fn)
    except Exception as exc:  # noqa: BLE001
        print("no psychopy.plugins:", exc)

    for path in (
        "psychopy.iohub.devices.eyetracker.hw.eyetribe",
        "psychopy.iohub.devices.eyetracker.eyetribe",
    ):
        _try(
            f"import {path} -> EyeTracker",
            lambda p=path: getattr(importlib.import_module(p), "EyeTracker", "<no attr>"),
        )

    _try(
        "import psychopy_eyetracker_eyetribe.eyetribe -> EyeTracker (our own path)",
        lambda: importlib.import_module("psychopy_eyetracker_eyetribe.eyetribe").EyeTracker,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
