# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""In-process mock Eye Tribe Server (PsychoPy-free; standard library only).

STUB. Phase 1 implements the TCP/JSON protocol, push streaming of synthesized frames,
heartbeat enforcement, and a scriptable calibration responder.
"""

from __future__ import annotations

from typing import Any


class MockEyeTribeServer:
    """Speaks the Eye Tribe Tracker API for tests. Phase 1."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0, frame_rate: int = 30) -> None:
        self.host = host
        self.port = port
        self.frame_rate = frame_rate

    def __enter__(self) -> "MockEyeTribeServer":
        raise NotImplementedError("Phase 1")

    def __exit__(self, *exc: Any) -> None:
        raise NotImplementedError("Phase 1")

    def start(self) -> int:
        """Bind and start serving; return the bound port. Phase 1."""
        raise NotImplementedError("Phase 1")

    def stop(self) -> None:
        raise NotImplementedError("Phase 1")
