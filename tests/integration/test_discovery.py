"""Phase 0 acceptance: packaging/discovery wiring.

The entry-point and YAML checks are PsychoPy-free and run everywhere once the package
is installed (``pip install -e .``). The EyeTracker-class load requires PsychoPy and is
skipped where PsychoPy is absent (it runs on the Windows CI runner).
"""

from __future__ import annotations

import importlib.resources as resources
from importlib.metadata import entry_points

import pytest


def test_iohub_entry_point_registered():
    eps = entry_points(group="psychopy.iohub.devices.eyetracker")
    mapping = {ep.name: ep.value for ep in eps}
    assert mapping.get("eyetribe") == "psychopy_eyetracker_eyetribe.eyetribe"


def test_settings_entry_point_registered():
    eps = entry_points(group="psychopy.experiment.components.settings.eyetracking")
    mapping = {ep.name: ep.value for ep in eps}
    assert (
        mapping.get("EyeTribeEyetrackerBackend")
        == "psychopy_eyetracker_eyetribe.eyetribe.settings:EyeTribeEyetrackerBackend"
    )


@pytest.mark.parametrize("fname", ["default_eyetracker.yaml", "supported_config_settings.yaml"])
def test_device_yaml_present_and_parses(fname):
    yaml = pytest.importorskip("yaml")
    pkg = "psychopy_eyetracker_eyetribe.eyetribe"
    text = resources.files(pkg).joinpath(fname).read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    assert "eyetracker.hw.eyetribe.EyeTracker" in data


def test_settings_backend_label_and_key():
    from psychopy_eyetracker_eyetribe.eyetribe.settings import EyeTribeEyetrackerBackend

    assert EyeTribeEyetrackerBackend.label == "Eye Tribe"
    assert EyeTribeEyetrackerBackend.key == "eyetracker.hw.eyetribe.EyeTracker"


@pytest.mark.integration
def test_settings_backend_params_under_psychopy():
    pytest.importorskip("psychopy")
    from psychopy_eyetracker_eyetribe.eyetribe.settings import EyeTribeEyetrackerBackend

    params, order = EyeTribeEyetrackerBackend.getParams()
    assert set(order) == {"etHost", "etPort", "etGazeSource", "etCalibTargetCount"}
    assert params["etHost"].val == "127.0.0.1"
    assert params["etPort"].val == 6555
    assert params["etGazeSource"].val == "raw"
    assert params["etCalibTargetCount"].val == 9


@pytest.mark.integration
def test_eyetracker_class_loads_under_psychopy():
    pytest.importorskip("psychopy")
    from psychopy_eyetracker_eyetribe.eyetribe import EyeTracker

    assert isinstance(EyeTracker, type)
