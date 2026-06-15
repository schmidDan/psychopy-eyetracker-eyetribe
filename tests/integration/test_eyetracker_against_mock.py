"""Phase 3: the ioHub EyeTracker device driven against MockEyeTribeServer."""

import pytest

pytestmark = pytest.mark.integration


def test_eyetracker_against_mock():
    pytest.importorskip("psychopy")
    pytest.skip("Phase 3: implement EyeTracker recording/polling")
