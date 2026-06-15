# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Eye Tribe Tracker API transport (PsychoPy-free; standard library only).

STUB. Phase 1 implements the socket client, the reader thread (parsing pushed frames
into a thread-safe bounded buffer), the heartbeat thread, and reconnect handling.
"""

from __future__ import annotations

from typing import Any

HOST_DEFAULT = "127.0.0.1"
PORT_DEFAULT = 6555
API_VERSION = 1
FRAME_BUFFER_CAPACITY = 1024
REQUEST_TIMEOUT_S = 2.0
RECONNECT_ATTEMPTS = 3
RECONNECT_BACKOFF_S = 0.5


class EyeTribeClient:
    """TCP/JSON client for the Eye Tribe Server. Phase 1."""

    def __init__(self, host: str = HOST_DEFAULT, port: int = PORT_DEFAULT) -> None:
        self.host = host
        self.port = port

    def connect(self) -> None:
        raise NotImplementedError("Phase 1")

    def close(self) -> None:
        raise NotImplementedError("Phase 1")

    def get(self, keys: list[str]) -> dict[str, Any]:
        raise NotImplementedError("Phase 1")

    def set(self, values: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Phase 1")
