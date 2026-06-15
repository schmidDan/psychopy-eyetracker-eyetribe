"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def mock_server():
    """Start a MockEyeTribeServer on a free port. Implemented in Phase 1."""
    pytest.skip("MockEyeTribeServer is implemented in Phase 1")
