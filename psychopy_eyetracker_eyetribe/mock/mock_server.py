# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""In-process mock Eye Tribe Server (PsychoPy-free; standard library only).

Speaks the Eye Tribe Tracker API (protocol v1) over TCP/JSON for unit and
integration tests. Supports push streaming, heartbeat enforcement, and a
scriptable calibration responder.
"""

from __future__ import annotations

import json
import logging
import math
import socket
import threading
import time
from typing import Any, Callable, Iterator, Optional

log = logging.getLogger(__name__)

# ── defaults ──────────────────────────────────────────────────────────────────
DEFAULT_FRAME_RATE = 30
DEFAULT_HEARTBEAT_INTERVAL_MS = 3000
DEFAULT_SCREEN_W = 1920
DEFAULT_SCREEN_H = 1080
STATE_TRACKING_GAZE = 0x01
STATE_TRACKING_EYES = 0x02
STATE_TRACKING_PRESENCE = 0x04
STATE_TRACKING_FAIL = 0x08
STATE_TRACKING_LOST = 0x10


# ── gaze models ───────────────────────────────────────────────────────────────

GazeModel = Callable[[float], tuple[float, float]]  # elapsed_s -> (x_px, y_px)


def _fixed_point(x: float = 960.0, y: float = 540.0) -> GazeModel:
    def _model(t: float) -> tuple[float, float]:  # noqa: ARG001
        return x, y

    return _model


def _linear_sweep(
    x0: float = 100.0,
    y0: float = 540.0,
    x1: float = 1820.0,
    y1: float = 540.0,
    period_s: float = 4.0,
) -> GazeModel:
    def _model(t: float) -> tuple[float, float]:
        frac = (t % period_s) / period_s
        return x0 + frac * (x1 - x0), y0 + frac * (y1 - y0)

    return _model


# ── blink / lost segment injection ────────────────────────────────────────────


class _Segment:
    """A time window during which a special state is injected."""

    def __init__(self, start_s: float, duration_s: float, state: int) -> None:
        self.start_s = start_s
        self.end_s = start_s + duration_s
        self.state = state

    def active(self, t: float) -> bool:
        return self.start_s <= t < self.end_s


# ── frame synthesis ───────────────────────────────────────────────────────────


def _make_frame(
    elapsed_ms: int,
    gaze_model: GazeModel,
    elapsed_s: float,
    segments: list[_Segment],
    screen_w: int,
    screen_h: int,
) -> dict[str, Any]:
    state = STATE_TRACKING_GAZE | STATE_TRACKING_EYES | STATE_TRACKING_PRESENCE
    for seg in segments:
        if seg.active(elapsed_s):
            state = seg.state
            break

    if state & STATE_TRACKING_GAZE:
        gx, gy = gaze_model(elapsed_s)
    else:
        gx, gy = 0.0, 0.0

    # Slight per-eye offset for realism
    lx, ly = gx - 5.0, gy + 2.0
    rx, ry = gx + 5.0, gy - 2.0
    psize = 15.0 + 3.0 * math.sin(elapsed_s * 0.5)
    pcx_l = lx / screen_w
    pcy_l = ly / screen_h
    pcx_r = rx / screen_w
    pcy_r = ry / screen_h
    fix = bool(state & STATE_TRACKING_GAZE)

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S") + ".000"

    return {
        "timestamp": timestamp,
        "time": elapsed_ms,
        "fix": fix,
        "state": state,
        "raw": {"x": gx, "y": gy},
        "avg": {"x": gx, "y": gy},
        "lefteye": {
            "raw": {"x": lx, "y": ly},
            "avg": {"x": lx, "y": ly},
            "psize": psize,
            "pcenter": {"x": pcx_l, "y": pcy_l},
        },
        "righteye": {
            "raw": {"x": rx, "y": ry},
            "avg": {"x": rx, "y": ry},
            "psize": psize + 0.5,
            "pcenter": {"x": pcx_r, "y": pcy_r},
        },
    }


# ── client handler ────────────────────────────────────────────────────────────


class _ClientHandler(threading.Thread):
    """Handles one connected client in its own thread."""

    def __init__(
        self,
        conn: socket.socket,
        addr: Any,
        frame_rate: int,
        heartbeat_interval_ms: int,
        screen_w: int,
        screen_h: int,
        gaze_model: GazeModel,
        segments: list[_Segment],
        calib_result: Optional[dict[str, Any]],
        on_disconnect: Callable[[], None],
        calib_log: Optional[list[dict[str, Any]]] = None,
        calib_log_lock: Optional[threading.Lock] = None,
    ) -> None:
        super().__init__(daemon=True, name=f"MockClientHandler-{addr}")
        self._conn = conn
        self._frame_rate = frame_rate
        self._heartbeat_interval_ms = heartbeat_interval_ms
        self._screen_w = screen_w
        self._screen_h = screen_h
        self._gaze_model = gaze_model
        self._segments = segments
        self._calib_result = calib_result
        self._on_disconnect = on_disconnect
        self._calib_log = calib_log
        self._calib_log_lock = calib_log_lock

        self._push_mode = False
        self._stop_evt = threading.Event()
        self._last_heartbeat = time.monotonic()
        self._push_thread: Optional[threading.Thread] = None
        self._start_mono = time.monotonic()

        # Protects writes to the socket from both the reader and push threads
        self._send_lock = threading.Lock()

    # ── public ────────────────────────────────────────────────────────────────

    def stop(self) -> None:
        self._stop_evt.set()
        try:
            self._conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._conn.close()

    # ── internal ──────────────────────────────────────────────────────────────

    def _send(self, obj: dict[str, Any]) -> None:
        data = (json.dumps(obj) + "\n").encode("utf-8")
        with self._send_lock:
            try:
                self._conn.sendall(data)
            except OSError:
                self._stop_evt.set()

    def _reply_ok(
        self, category: str, request: str, values: Optional[dict[str, Any]] = None
    ) -> None:
        msg: dict[str, Any] = {"category": category, "request": request, "statuscode": 200}
        if values is not None:
            msg["values"] = values
        self._send(msg)

    def _reply_err(self, category: str, request: str, code: int = 400) -> None:
        self._send({"category": category, "request": request, "statuscode": code})

    def _handle_message(self, msg: dict[str, Any]) -> None:
        cat = msg.get("category", "")
        req = msg.get("request", "")
        vals = msg.get("values", {})

        if cat == "heartbeat":
            self._last_heartbeat = time.monotonic()
            return

        if cat == "tracker":
            if req == "set":
                if isinstance(vals, dict):
                    if "version" in vals:
                        self._reply_ok("tracker", "set")
                    elif "push" in vals:
                        if vals["push"]:
                            self._push_mode = True
                            self._start_push_thread()
                        self._reply_ok("tracker", "set")
                    else:
                        self._reply_ok("tracker", "set")
                else:
                    self._reply_err("tracker", "set")

            elif req == "get":
                if isinstance(vals, list):
                    result: dict[str, Any] = {}
                    for key in vals:
                        if key == "heartbeatinterval":
                            result[key] = self._heartbeat_interval_ms
                        elif key == "framerate":
                            result[key] = self._frame_rate
                        elif key == "screenresw":
                            result[key] = self._screen_w
                        elif key == "screenresh":
                            result[key] = self._screen_h
                        elif key == "trackerstate":
                            result[key] = 0
                        elif key == "iscalibrated":
                            result[key] = False
                    self._reply_ok("tracker", "get", result)
                else:
                    self._reply_err("tracker", "get")
            else:
                self._reply_err("tracker", req)

        elif cat == "calibration":
            if self._calib_log is not None and self._calib_log_lock is not None:
                with self._calib_log_lock:
                    self._calib_log.append({"request": req, "values": vals})
            if req == "start":
                self._reply_ok("calibration", "start")
            elif req == "pointstart":
                self._reply_ok("calibration", "pointstart")
            elif req == "pointend":
                # Return calibresult on pointend — the client will detect it
                cr = self._calib_result or {
                    "result": True,
                    "deg": 0.71,
                    "degl": 0.66,
                    "degr": 0.77,
                    "calibpoints": [],
                }
                self._reply_ok("calibration", "pointend", {"calibresult": cr})
            elif req == "abort":
                self._reply_ok("calibration", "abort")
            elif req == "clear":
                self._reply_ok("calibration", "clear")
            else:
                self._reply_err("calibration", req)
        else:
            self._reply_err(cat, req)

    def _start_push_thread(self) -> None:
        self._push_thread = threading.Thread(
            target=self._push_loop, daemon=True, name=f"{self.name}-push"
        )
        self._push_thread.start()

    def _push_loop(self) -> None:
        interval_s = 1.0 / self._frame_rate
        next_tick = time.monotonic()
        while not self._stop_evt.is_set():
            now = time.monotonic()
            elapsed_s = now - self._start_mono
            elapsed_ms = int(elapsed_s * 1000)
            frame = _make_frame(
                elapsed_ms,
                self._gaze_model,
                elapsed_s,
                self._segments,
                self._screen_w,
                self._screen_h,
            )
            self._send({"category": "tracker", "request": "get", "values": {"frame": frame}})
            next_tick += interval_s
            sleep_s = next_tick - time.monotonic()
            if sleep_s > 0:
                self._stop_evt.wait(sleep_s)

    def _heartbeat_enforcer(self) -> None:
        """Drop the client if no heartbeat arrives within the interval."""
        interval_s = self._heartbeat_interval_ms / 1000.0
        while not self._stop_evt.is_set():
            time.sleep(0.1)
            elapsed = time.monotonic() - self._last_heartbeat
            if elapsed > interval_s:
                log.debug("Heartbeat timeout — dropping client %s", self._conn.getpeername())
                self._stop_evt.set()
                try:
                    self._conn.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self._conn.close()
                return

    def run(self) -> None:
        log.debug("Client connected")
        self._last_heartbeat = time.monotonic()

        # Start heartbeat enforcer
        hb_thread = threading.Thread(
            target=self._heartbeat_enforcer, daemon=True, name=f"{self.name}-hb"
        )
        hb_thread.start()

        buf = b""
        try:
            self._conn.settimeout(0.2)
            while not self._stop_evt.is_set():
                try:
                    chunk = self._conn.recv(4096)
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
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        log.warning("Malformed JSON from client: %r", line)
                        continue
                    self._handle_message(msg)
        finally:
            self._stop_evt.set()
            log.debug("Client disconnected")
            self._on_disconnect()


# ── MockEyeTribeServer ────────────────────────────────────────────────────────


class MockEyeTribeServer:
    """Speaks the Eye Tribe Tracker API for tests.

    Usage::

        with MockEyeTribeServer() as srv:
            port = srv.port
            # connect EyeTribeClient to ('127.0.0.1', port)

    Or::

        srv = MockEyeTribeServer()
        port = srv.start()
        ...
        srv.stop()
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        frame_rate: int = DEFAULT_FRAME_RATE,
        heartbeat_interval_ms: int = DEFAULT_HEARTBEAT_INTERVAL_MS,
        screen_w: int = DEFAULT_SCREEN_W,
        screen_h: int = DEFAULT_SCREEN_H,
        gaze_model: Optional[GazeModel] = None,
        segments: Optional[list[_Segment]] = None,
        calib_result: Optional[dict[str, Any]] = None,
    ) -> None:
        self.host = host
        self._requested_port = port
        self.port: int = 0
        self.frame_rate = frame_rate
        self.heartbeat_interval_ms = heartbeat_interval_ms
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._gaze_model: GazeModel = gaze_model if gaze_model is not None else _fixed_point()
        self._segments: list[_Segment] = segments if segments is not None else []
        self._calib_result = calib_result

        self._server_sock: Optional[socket.socket] = None
        self._accept_thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._clients: list[_ClientHandler] = []
        self._clients_lock = threading.Lock()
        self._calib_log: list[dict[str, Any]] = []
        self._calib_log_lock = threading.Lock()

    # ── context-manager ───────────────────────────────────────────────────────

    def __enter__(self) -> "MockEyeTribeServer":
        self.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> int:
        """Bind, start accepting, and return the bound port."""
        self._stop_evt.clear()
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self._requested_port))
        self._server_sock.listen(5)
        self.port = self._server_sock.getsockname()[1]
        log.debug("MockEyeTribeServer listening on %s:%d", self.host, self.port)
        self._accept_thread = threading.Thread(
            target=self._accept_loop, daemon=True, name="MockEyeTribeServer-accept"
        )
        self._accept_thread.start()
        return self.port

    def stop(self) -> None:
        self._stop_evt.set()
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except OSError:
                pass
        with self._clients_lock:
            for c in list(self._clients):
                c.stop()
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=2.0)

    # ── helpers ───────────────────────────────────────────────────────────────

    @property
    def connected_client_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    def inject_segments(self, segments: list[_Segment]) -> None:
        """Replace the segment list (affects new frames immediately)."""
        self._segments = segments

    def get_calib_log(self) -> list[dict[str, Any]]:
        """Return a snapshot of recorded calibration messages (thread-safe)."""
        with self._calib_log_lock:
            return list(self._calib_log)

    def clear_calib_log(self) -> None:
        """Clear the calibration message log."""
        with self._calib_log_lock:
            self._calib_log.clear()

    def drop_clients(self) -> None:
        """Close all connected client sockets to simulate a server-side EOF.

        The listening socket stays up so clients can reconnect.  Each connected
        client's reader thread hits EOF and calls its ``_on_server_eof`` callback
        (because the client's own ``_stop_evt`` is not touched).  The push thread
        on the handler side detects the ``OSError`` on the next send and sets the
        handler's internal stop event, cleaning up the handler gracefully.
        """
        with self._clients_lock:
            handlers = list(self._clients)
        for handler in handlers:
            try:
                handler._conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                handler._conn.close()
            except OSError:
                pass

    # ── internal ──────────────────────────────────────────────────────────────

    def _accept_loop(self) -> None:
        assert self._server_sock is not None
        self._server_sock.settimeout(0.2)
        while not self._stop_evt.is_set():
            try:
                conn, addr = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            handler = _ClientHandler(
                conn=conn,
                addr=addr,
                frame_rate=self.frame_rate,
                heartbeat_interval_ms=self.heartbeat_interval_ms,
                screen_w=self.screen_w,
                screen_h=self.screen_h,
                gaze_model=self._gaze_model,
                segments=self._segments,
                calib_result=self._calib_result,
                on_disconnect=lambda: self._remove_client(handler),
                calib_log=self._calib_log,
                calib_log_lock=self._calib_log_lock,
            )
            with self._clients_lock:
                self._clients.append(handler)
            handler.start()

    def _remove_client(self, handler: _ClientHandler) -> None:
        with self._clients_lock:
            try:
                self._clients.remove(handler)
            except ValueError:
                pass


# ── convenience factories ─────────────────────────────────────────────────────


def make_blink_segment(start_s: float, duration_s: float = 0.15) -> _Segment:
    return _Segment(start_s, duration_s, STATE_TRACKING_FAIL)


def make_lost_segment(start_s: float, duration_s: float = 0.5) -> _Segment:
    return _Segment(start_s, duration_s, STATE_TRACKING_LOST)


def fixed_point_model(x: float = 960.0, y: float = 540.0) -> GazeModel:
    return _fixed_point(x, y)


def linear_sweep_model(
    x0: float = 100.0,
    y0: float = 540.0,
    x1: float = 1820.0,
    y1: float = 540.0,
    period_s: float = 4.0,
) -> GazeModel:
    return _linear_sweep(x0, y0, x1, y1, period_s)


# Expose Iterator for typing (used in tests)
__all__ = [
    "MockEyeTribeServer",
    "GazeModel",
    "_Segment",
    "make_blink_segment",
    "make_lost_segment",
    "fixed_point_model",
    "linear_sweep_model",
    "STATE_TRACKING_GAZE",
    "STATE_TRACKING_EYES",
    "STATE_TRACKING_PRESENCE",
    "STATE_TRACKING_FAIL",
    "STATE_TRACKING_LOST",
    "DEFAULT_FRAME_RATE",
    "DEFAULT_HEARTBEAT_INTERVAL_MS",
    "DEFAULT_SCREEN_W",
    "DEFAULT_SCREEN_H",
]

# keep Iterator import quiet if unused externally
_ = Iterator
