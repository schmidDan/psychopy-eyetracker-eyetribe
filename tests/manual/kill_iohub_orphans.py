# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Kill orphaned ioHub server processes (recovery for PC_DEVICE_RUNTIME_ERROR).

ioHub uses a *fixed* UDP control port (9036).  If a PsychoPy experiment is
force-quit (or crashes) while the ioHub server is running, the server can be
orphaned and keep squatting on 9036 — PsychoPy's parent-death cleanup is not
reliable.  A single orphan then breaks every subsequent run: the new ioHub
server cannot bind 9036, and the keyboard device-state RPC comes back as
``PC_DEVICE_RUNTIME_ERROR`` (or the experiment hangs on a black screen).

Run this between runs if you hit that crash:

    "C:/Program Files/PsychoPy/python.exe" tests/manual/kill_iohub_orphans.py

To prevent it automatically, call the same routine from your experiment's
*Before Experiment* code component (it runs before ``launchHubServer``)::

    from psychopy_eyetracker_eyetribe import clear_stale_servers
    clear_stale_servers()
"""

from __future__ import annotations

import os
import sys

# Make the plugin importable when run straight from a checkout.
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)


def main() -> int:
    from psychopy_eyetracker_eyetribe import clear_stale_servers

    killed = clear_stale_servers()
    if killed:
        print(f"done — killed {len(killed)} orphaned ioHub server(s): {killed}")
    else:
        print("done — no orphaned ioHub servers found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
