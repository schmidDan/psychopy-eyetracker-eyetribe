# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""[HARDWARE] Pre-Phase-0 smoke test: confirm the Eye Tribe Server + ET1000 stream.

Standard-library only; does NOT require this package or PsychoPy. Run on the Windows
machine with the Eye Tribe Server running:

    "C:\\Program Files\\PsychoPy\\python.exe" tests/manual/smoke_socket.py

It opens a TCP socket to the Server, sets protocol version 1, enables push, prints the
first frames, and saves one raw frame to ``tests/manual/_captured_frame.json`` (the
Phase 2 golden-fixture seed). Phase 11 turns this into the recorded validation artifact.
"""

from __future__ import annotations

import json
import socket
import sys

HOST, PORT, N = "127.0.0.1", 6555, 20


def _send(sock: socket.socket, obj: dict) -> None:
    sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))


def main() -> int:
    with socket.create_connection((HOST, PORT), timeout=5) as sock:
        _send(sock, {"category": "tracker", "request": "set", "values": {"version": 1}})
        _send(
            sock,
            {
                "category": "tracker",
                "request": "get",
                "values": ["framerate", "screenresw", "screenresh", "trackerstate"],
            },
        )
        _send(sock, {"category": "tracker", "request": "set", "values": {"push": True}})

        buf, count, first = b"", 0, None
        sock.settimeout(5)
        while count < N:
            buf += sock.recv(4096)
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                msg = json.loads(line)
                print(msg)
                if msg.get("values", {}).get("frame") is not None:
                    first = first or msg["values"]["frame"]
                    count += 1
        if first is not None:
            with open("tests/manual/_captured_frame.json", "w", encoding="utf-8") as fh:
                json.dump(first, fh, indent=2)
            print("saved tests/manual/_captured_frame.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
