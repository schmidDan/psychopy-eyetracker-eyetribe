"""Phase 1 fills these in. Phase 0: the transport module imports without PsychoPy."""

from psychopy_eyetracker_eyetribe.eyetribe import eyetribe_client


def test_imports_without_psychopy():
    assert eyetribe_client.PORT_DEFAULT == 6555
    assert eyetribe_client.API_VERSION == 1
    assert eyetribe_client.FRAME_BUFFER_CAPACITY == 1024
