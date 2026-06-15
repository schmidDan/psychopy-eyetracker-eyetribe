"""Phase 4 fills these in. Phase 0: the module imports without PsychoPy."""

from psychopy_eyetracker_eyetribe.eyetribe import transforms


def test_imports_without_psychopy():
    assert callable(transforms.eyetribe_pixels_to_display)
    assert callable(transforms.display_to_eyetribe_pixels)
