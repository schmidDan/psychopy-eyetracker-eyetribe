"""Phase 5 fills these in. Phase 0: the module imports without PsychoPy."""

from psychopy_eyetracker_eyetribe.eyetribe import calibration


def test_imports_without_psychopy():
    assert calibration.DEFAULT_TARGET_COUNT == 9
    assert calibration.SUPPORTED_TARGET_COUNTS == (5, 9, 12)
    assert callable(calibration.parse_calibresult)
