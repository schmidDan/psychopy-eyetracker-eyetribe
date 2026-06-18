# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Builder Eyetracker backend registration for The Eye Tribe.

Exposes ``EyeTribeEyetrackerBackend`` which PsychoPy Builder discovers via the
``psychopy.experiment.components.settings.eyetracking`` entry-point group and
uses to populate the Eyetracker component dropdown (label "Eye Tribe") and
generate the ioHub device config block in Builder experiments.

The guarded import keeps the entry point importable in any environment (e.g.
unit tests without PsychoPy installed).
"""

from __future__ import annotations

try:  # pragma: no cover - base availability varies by PsychoPy build
    from psychopy.experiment import Param
    from psychopy.experiment.components.settings.eyetracking import EyetrackerBackend as _Base
    from psychopy.localization import _translate
except Exception:  # noqa: BLE001 - intentional: keep entry point importable without PsychoPy
    _Base = object  # type: ignore[assignment, misc]
    Param = None  # type: ignore[assignment]
    _translate = str  # type: ignore[assignment]


class EyeTribeEyetrackerBackend(_Base):  # type: ignore[misc, valid-type]
    """Exposes 'Eye Tribe' in the Builder Eyetracker component dropdown."""

    label = "Eye Tribe"
    key = "eyetracker.hw.eyetribe.EyeTracker"

    @classmethod
    def getParams(cls):  # type: ignore[override]
        """Return Builder parameter definitions for the Eye Tribe eyetracker."""
        if Param is None:
            return {}, []

        order = ["etHost", "etPort", "etGazeSource", "etCalibTargetCount"]
        params = {}

        params["etHost"] = Param(
            "127.0.0.1",
            valType="str",
            inputType="single",
            hint=_translate("Hostname or IP address of the Eye Tribe Server."),
            label=_translate("Host"),
            categ="Eyetracking",
        )
        params["etPort"] = Param(
            6555,
            valType="num",
            inputType="single",
            hint=_translate("TCP port of the Eye Tribe Server (default 6555)."),
            label=_translate("Port"),
            categ="Eyetracking",
        )
        params["etGazeSource"] = Param(
            "raw",
            valType="str",
            inputType="choice",
            allowedVals=["raw", "avg"],
            hint=_translate(
                "Gaze signal: raw per-sample coordinates (recommended for research) "
                "or server-smoothed average."
            ),
            label=_translate("Gaze source"),
            categ="Eyetracking",
        )
        params["etCalibTargetCount"] = Param(
            9,
            valType="num",
            inputType="choice",
            allowedVals=[5, 9, 12, 16],
            hint=_translate("Number of calibration target points (5, 9, 12, or 16)."),
            label=_translate("Calibration targets"),
            categ="Eyetracking",
        )

        return params, order

    @classmethod
    def writeDeviceCode(cls, inits, buff):  # type: ignore[override]
        """Write the ioHub device config block into a Builder-generated script."""
        code = (
            "ioConfig[%(eyetracker)s] = {\n"
            "    'name': 'tracker',\n"
            "    'host': %(etHost)s,\n"
            "    'port': int(%(etPort)s),\n"
            "    'gaze_source': %(etGazeSource)s,\n"
            "    'calibration': {'target_count': int(%(etCalibTargetCount)s)},\n"
            "}\n"
        )
        buff.writeIndentedLines(code % inits)
