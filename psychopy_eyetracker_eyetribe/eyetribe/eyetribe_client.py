# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Eye Tribe Tracker API transport (PsychoPy-free; standard library only).

Implements the socket client, reader thread (pushing raw frame dicts into a
bounded FrameBuffer), heartbeat thread, and reconnect handling.
"""

from __future__ import annotations

import json
import logging
import queue
import socket
import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Optional

log = logging.getLogger(__name__)

HOST_DEFAULT = "127.0.0.1"
PORT_DEFAULT = 6555
API_VERSION = 1
FRAME_BUFFER_CAPACITY = 1024
REQUEST_TIMEOUT_S = 2.0
RECONNECT_ATTEMPTS = 3
RECONNECT_BACKOFF_S = 0.5

# Connection state constants
STATE_CONNECTED = "CONNECTED"
STATE_DISCONNECTED = "DISCONNECTED"
STATE_CONNECTING = "CONNECTING"


# ── FrameBuffer ───────────────────────────────────────────────────────────────


class FrameBuffer:
    """Thread-safe bounded FIFO for raw frame dicts; drops oldest on overflow."""

    def __init__(self, capacity: int = FRAME_BUFFER_CAPACITY) -> None:
        self._capacity = capacity
        self._buf: Deque[dict[str, Any]] = deque()
        self._lock = threading.Lock()

    def put(self, frame: dict[str, Any]) -> None:
        with self._lock:
            if len(self._buf) >= self._capacity:
                self._buf.popleft()
            self._buf.append(frame)

    def get_all(self) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._buf)
            self._buf.clear()
            return items

    def get_one(self, timeout_s: float = 0.0) -> Optional[dict[str, Any]]:
        deadline = time.monotonic() + timeout_s
        while True:
            with self._lock:
                if self._buf:
                    return self._buf.popleft()
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.001)

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)

    @property
    def capacity(self) -> int:
        return self._capacity


# ── Internal threads ──────────────────────────────────────────────────────────


class _ReaderThread(threading.Thread):
    """Reads newline-delimited JSON from the socket.

    - Frames are detected by ``values.frame`` presence and pushed to FrameBuffer.
    - Non-frame replies are routed to the request/reply queue.
    """

    def __init__(
        self,
        sock: socket.socket,
        frame_buffer: FrameBuffer,
        reply_queue: "queue.Queue[dict[str, Any]]",
        stop_evt: threading.Event,
        on_eof: "Optional[Callable[[], None]]" = None,
    ) -> None:
        super().__init__(daemon=True, name="EyeTribeReaderThread")
        self._sock = sock
        self._frame_buffer = frame_buffer
        self._reply_queue = reply_queue
        self._stop_evt = stop_evt
        self._on_eof = on_eof

    def run(self) -> None:
        buf = b""
        self._sock.settimeout(0.2)
        while not self._stop_evt.is_set():
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg: dict[str, Any] = json.loads(line)
                except json.JSONDecodeError:
                    log.warning("EyeTribeClient: malformed JSON: %r", line)
                    continue
                self._dispatch(msg)
        log.debug("EyeTribeReaderThread: EOF")
        if not self._stop_evt.is_set() and self._on_eof is not None:
            self._on_eof()

    def _dispatch(self, msg: dict[str, Any]) -> None:
        values = msg.get("values")
        if isinstance(values, dict) and "frame" in values:
            self._frame_buffer.put(values["frame"])
        else:
            try:
                self._reply_queue.put_nowait(msg)
            except queue.Full:
                log.warning("EyeTribeClient: reply queue full, dropping message")


class _HeartbeatThread(threading.Thread):
    """Sends ``{"category":"heartbeat"}`` every ``interval_ms / 2`` ms."""

    def __init__(
        self,
        send_fn: Callable[[dict[str, Any]], None],
        interval_ms: int,
        stop_evt: threading.Event,
    ) -> None:
        super().__init__(daemon=True, name="EyeTribeHeartbeatThread")
        self._send = send_fn
        self._interval_s = (interval_ms / 2) / 1000.0
        self._stop_evt = stop_evt

    def run(self) -> None:
        while not self._stop_evt.wait(self._interval_s):
            try:
                self._send({"category": "heartbeat"})
            except OSError:
                break
        log.debug("EyeTribeHeartbeatThread: stopped")


# ── EyeTribeClient ────────────────────────────────────────────────────────────


class EyeTribeClient:
    """TCP/JSON client for the Eye Tribe Server.

    Thread-safe after ``connect()`` returns. Push frames arrive in
    ``frame_buffer``. Use ``get()``/``set()`` for request/reply operations.
    """

    def __init__(self, host: str = HOST_DEFAULT, port: int = PORT_DEFAULT) -> None:
        self.host = host
        self.port = port
        self.state: str = STATE_DISCONNECTED

        self.frame_buffer: FrameBuffer = FrameBuffer(FRAME_BUFFER_CAPACITY)
        self.heartbeat_interval_ms: int = 3000  # updated at connect
        self.frame_rate: int = 30  # updated at connect

        self._sock: Optional[socket.socket] = None
        self._stop_evt = threading.Event()
        self._reply_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=64)
        self._send_lock = threading.Lock()
        self._reader: Optional[_ReaderThread] = None
        self._heartbeat: Optional[_HeartbeatThread] = None

    # ── public API ────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Open socket, negotiate protocol, start push, start heartbeat.

        Retries RECONNECT_ATTEMPTS times with RECONNECT_BACKOFF_S delay.
        Raises RuntimeError if all attempts fail.
        """
        self._stop_evt.clear()
        last_exc: Optional[Exception] = None
        for attempt in range(1, RECONNECT_ATTEMPTS + 1):
            try:
                self._connect_once()
                return
            except Exception as exc:
                last_exc = exc
                log.warning(
                    "EyeTribeClient: connect attempt %d/%d failed: %s",
                    attempt,
                    RECONNECT_ATTEMPTS,
                    exc,
                )
                if attempt < RECONNECT_ATTEMPTS:
                    time.sleep(RECONNECT_BACKOFF_S)
        self.state = STATE_DISCONNECTED
        raise RuntimeError(
            f"EyeTribeClient: could not connect after {RECONNECT_ATTEMPTS} attempts"
        ) from last_exc

    def close(self) -> None:
        """Tear down cleanly: stop threads, close socket."""
        self._stop_evt.set()
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._reader is not None:
            self._reader.join(timeout=2.0)
            self._reader = None
        if self._heartbeat is not None:
            self._heartbeat.join(timeout=2.0)
            self._heartbeat = None
        self.state = STATE_DISCONNECTED
        log.debug("EyeTribeClient: closed")

    def get(self, keys: list[str]) -> dict[str, Any]:
        """Send ``tracker get`` and return the ``values`` dict."""
        reply = self._request({"category": "tracker", "request": "get", "values": keys})
        return reply.get("values", {})  # type: ignore[no-any-return]

    def set(self, values: dict[str, Any]) -> dict[str, Any]:
        """Send ``tracker set`` and return the reply."""
        return self._request({"category": "tracker", "request": "set", "values": values})

    # ── internal ──────────────────────────────────────────────────────────────

    def _connect_once(self) -> None:
        self.state = STATE_CONNECTING
        sock = socket.create_connection((self.host, self.port), timeout=REQUEST_TIMEOUT_S)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock = sock

        # Start the reader before sending any requests so replies are caught
        self._stop_evt.clear()
        self._reply_queue = queue.Queue(maxsize=64)
        self._reader = _ReaderThread(
            sock=self._sock,
            frame_buffer=self.frame_buffer,
            reply_queue=self._reply_queue,
            stop_evt=self._stop_evt,
            on_eof=self._on_server_eof,
        )
        self._reader.start()

        # Step 2: set version
        self.set({"version": API_VERSION})

        # Step 3: get session params
        params = self.get(
            [
                "heartbeatinterval",
                "framerate",
                "screenresw",
                "screenresh",
                "iscalibrated",
                "trackerstate",
            ]
        )
        self.heartbeat_interval_ms = int(params.get("heartbeatinterval", 3000))
        self.frame_rate = int(params.get("framerate", 30))
        log.info(
            "EyeTribeClient: connected — rate=%d Hz, heartbeat=%d ms",
            self.frame_rate,
            self.heartbeat_interval_ms,
        )

        # Step 4: enable push
        self.set({"push": True})

        # Step 5: start heartbeat thread
        self._heartbeat = _HeartbeatThread(
            send_fn=self._send_raw,
            interval_ms=self.heartbeat_interval_ms,
            stop_evt=self._stop_evt,
        )
        self._heartbeat.start()

        self.state = STATE_CONNECTED

    def _send_raw(self, obj: dict[str, Any]) -> None:
        data = (json.dumps(obj) + "\n").encode("utf-8")
        with self._send_lock:
            if self._sock is None:
                raise OSError("socket closed")
            self._sock.sendall(data)

    def _request(self, msg: dict[str, Any]) -> dict[str, Any]:
        """Send a message and wait for the matching reply (by category+request)."""
        # Drain stale replies from a previous request
        while not self._reply_queue.empty():
            try:
                self._reply_queue.get_nowait()
            except queue.Empty:
                break

        self._send_raw(msg)
        deadline = time.monotonic() + REQUEST_TIMEOUT_S
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"EyeTribeClient: no reply for {msg.get('request')} within {REQUEST_TIMEOUT_S}s"
                )
            try:
                reply = self._reply_queue.get(timeout=min(remaining, 0.1))
            except queue.Empty:
                continue
            # Match by category and request
            if reply.get("category") == msg.get("category") and reply.get("request") == msg.get(
                "request"
            ):
                if reply.get("statuscode", 200) != 200:
                    log.warning("EyeTribeClient: error reply: %s", reply)
                return reply
            # Unexpected reply — put back and wait (simplistic: just discard and keep polling)
            log.debug("EyeTribeClient: unexpected reply %s, discarding", reply)

    def _on_server_eof(self) -> None:
        """Called by ReaderThread when the server closes the connection."""
        if self._stop_evt.is_set():
            return
        log.warning("EyeTribeClient: server closed connection — attempting reconnect")
        self.state = STATE_DISCONNECTED
        # Attempt reconnect in background
        t = threading.Thread(target=self._reconnect_bg, daemon=True, name="EyeTribeReconnect")
        t.start()

    def _reconnect_bg(self) -> None:
        """Background reconnect: 3 attempts then give up."""
        for attempt in range(1, RECONNECT_ATTEMPTS + 1):
            time.sleep(RECONNECT_BACKOFF_S)
            if self._stop_evt.is_set():
                return
            try:
                log.info("EyeTribeClient: reconnect attempt %d/%d", attempt, RECONNECT_ATTEMPTS)
                self._connect_once()
                log.info("EyeTribeClient: reconnected")
                return
            except Exception as exc:
                log.warning("EyeTribeClient: reconnect attempt %d failed: %s", attempt, exc)
        self.state = STATE_DISCONNECTED
        log.error("EyeTribeClient: reconnect failed — state DISCONNECTED")
