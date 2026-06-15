"""Phase 2 fills these in. Phase 0: the module imports without PsychoPy."""

from psychopy_eyetracker_eyetribe.eyetribe import frames


def test_imports_without_psychopy():
    assert callable(frames.parse_frame)
    assert issubclass(frames.FrameParseError, ValueError)
    assert frames.STATE_TRACKING_GAZE == 0x1
