# Part of the psychopy-eyetracker-eyetribe plugin.
# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""PsychoPy ioHub eye-tracker plugin for The Eye Tribe (ET1000).

Device discovery is via entry points declared in ``pyproject.toml``; this top-level
package intentionally contains no import-time logic (mirrors the reference plugin).
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["clear_stale_servers", "__version__"]


def clear_stale_servers() -> list[int]:
    """Kill any orphaned ioHub server process and return the PIDs that were killed.

    ioHub uses a single, fixed UDP control port (9036).  If a PsychoPy experiment is
    force-quit (or crashes) while the ioHub server is running, the server can be left
    *orphaned* squatting on that port — PsychoPy's parent-death cleanup is unreliable —
    and a single orphan then makes every later run fail with ``PC_DEVICE_RUNTIME_ERROR``
    (or hang on a black screen) because the next server cannot bind 9036.

    Call this **from the experiment process, before ``launchHubServer``** (e.g. in a
    Builder *Before Experiment* code component)::

        from psychopy_eyetracker_eyetribe import clear_stale_servers
        clear_stale_servers()

    Doing it here (client side, before the new server starts) avoids the race that an
    in-server cleanup would hit, where the client latches onto the orphan during the
    server-ready poll before the orphan is removed.

    Best-effort and fully guarded: never raises.  Returns the list of killed PIDs
    (empty when nothing needed clearing).  No-op when ``psutil`` is unavailable.
    """
    try:
        import os

        import psutil
    except Exception:  # pragma: no cover - psutil ships with PsychoPy
        return []

    my_pid = os.getpid()
    victims = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            if proc.info["pid"] == my_pid:
                continue
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if "start_iohub_process" in cmdline:
                victims.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    pids = [p.pid for p in victims]
    for p in victims:
        try:
            p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    if victims:
        psutil.wait_procs(victims, timeout=2.0)  # let the OS release the UDP port
    return pids
