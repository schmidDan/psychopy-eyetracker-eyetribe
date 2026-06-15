"""Phase 4 fills these in. Phase 0: the module imports without PsychoPy."""

from psychopy_eyetracker_eyetribe.eyetribe import time_sync


def test_imports_without_psychopy():
    assert time_sync.ClockSync is not None
