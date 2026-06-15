#!/usr/bin/env python3
# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Eye Tribe Coder demo — records gaze against the bundled mock or real hardware.

By default the script starts the bundled :class:`MockEyeTribeServer` so that a
researcher can try the full data pipeline without an ET1000 or Eye Tribe Server.

Usage
-----
Hardware-free (mock, default)::

    python examples/coder_demo.py

Real ET1000 (Eye Tribe Server must be running first)::

    python examples/coder_demo.py --no-mock

In a PsychoPy experiment you would normally use ``launchHubServer`` to integrate
with the ioHub event loop; see the Quick start section in README.md for that
snippet.  This script drives the ``EyeTracker`` class directly (the same way the
integration test suite does) so that it runs without a display and without a
running ioHub subprocess.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

# ── device-config factory ─────────────────────────────────────────────────────

_DCONFIG_BASE: dict[str, Any] = {
    "name": "tracker",
    "event_buffer_length": 1024,
    "device_number": 0,
    "manufacturer_name": "The Eye Tribe",
    "model_name": "ET1000",
    "auto_report_events": False,
    "api_version": 1,
    "gaze_source": "raw",
    "runtime_settings": {"sampling_rate": "auto", "track_eyes": "BINOCULAR"},
    "calibration": {"target_count": 9},
    "device_timer": {"interval": 0.005},
    "monitor_event_types": [
        "BinocularEyeSampleEvent",
        "FixationStartEvent",
        "FixationEndEvent",
    ],
}


def _make_dconfig(host: str, port: int) -> dict[str, Any]:
    return {**_DCONFIG_BASE, "host": host, "port": port}


def _reset_singleton() -> None:
    """Clear the EyeTrackerDevice singleton so a fresh EyeTracker can be built."""
    try:
        from psychopy.iohub.devices.eyetracker import EyeTrackerDevice

        from psychopy_eyetracker_eyetribe.eyetribe.eyetracker import EyeTracker

        EyeTrackerDevice._INSTANCE = None
        if "_INSTANCE" in EyeTracker.__dict__:
            EyeTracker._INSTANCE = None  # type: ignore[attr-defined]
    except Exception:
        pass


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(
        description="Eye Tribe Coder demo — records gaze against the mock or real hardware.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--no-mock",
        action="store_true",
        help="Connect to a real ET1000 (Eye Tribe Server must be running)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Server host (real mode only)")
    parser.add_argument("--port", type=int, default=6555, help="Server port (real mode only)")
    parser.add_argument(
        "--duration", type=float, default=1.0, help="Recording duration in seconds (default 1.0)"
    )
    args = parser.parse_args()

    # ── start mock server if needed ───────────────────────────────────────────
    mock_srv = None
    host = args.host
    port = args.port

    if not args.no_mock:
        from psychopy_eyetracker_eyetribe.mock.mock_server import MockEyeTribeServer

        mock_srv = MockEyeTribeServer(port=0, frame_rate=30, heartbeat_interval_ms=3000)
        mock_srv.start()
        host = "127.0.0.1"
        port = mock_srv.port
        print(f"[demo] Mock Eye Tribe Server started on {host}:{port}")
    else:
        print(f"[demo] Connecting to real Eye Tribe Server at {host}:{port}")

    # ── import PsychoPy EyeTracker ────────────────────────────────────────────
    try:
        from psychopy.iohub.constants import EventConstants

        from psychopy_eyetracker_eyetribe.eyetribe.eyetracker import EyeTracker
    except ImportError as exc:
        print(f"[demo] ERROR: PsychoPy is required. {exc}")
        if mock_srv is not None:
            mock_srv.stop()
        sys.exit(1)

    # ── build and connect the EyeTracker ─────────────────────────────────────
    _reset_singleton()
    tracker = EyeTracker(dconfig=_make_dconfig(host, port))

    try:
        print("[demo] Connecting …")
        tracker.setConnectionState(True)
        if not tracker.isConnected():
            print("[demo] ERROR: could not connect to the Eye Tribe Server.")
            sys.exit(1)
        print(f"[demo] Connected.  Sampling rate: {tracker._client.frame_rate} Hz")

        if args.no_mock:
            print(
                "[demo] Tip: call tracker.runSetupProcedure() before recording to run "
                "the PsychoPy-driven 9-point calibration."
            )
        else:
            print("[demo] Mock mode: skipping visual calibration.")

        # ── record ────────────────────────────────────────────────────────────
        print(f"[demo] Recording for {args.duration:.1f} s …")
        tracker.setRecordingState(True)

        deadline = time.monotonic() + args.duration
        while time.monotonic() < deadline:
            tracker._poll()
            time.sleep(0.01)

        tracker.setRecordingState(False)
        print("[demo] Recording stopped.")

        # ── inspect collected events ──────────────────────────────────────────
        events = list(tracker._native_event_buffer)
        samples = [e for e in events if e[4] == EventConstants.BINOCULAR_EYE_SAMPLE]
        fix_starts = [e for e in events if e[4] == EventConstants.FIXATION_START]
        fix_ends = [e for e in events if e[4] == EventConstants.FIXATION_END]

        print(
            f"[demo] Collected {len(events)} events: "
            f"{len(samples)} BinocularEyeSamples, "
            f"{len(fix_starts)} FixationStarts, "
            f"{len(fix_ends)} FixationEnds."
        )

        if samples:
            # BinocularEyeSampleEvent field layout (index → meaning):
            #   [7]  iohub_time   — PsychoPy clock time (seconds)
            #   [11] left_gaze_x  — display-unit x (pixels in this demo, no monitor cal)
            #   [12] left_gaze_y  — display-unit y
            #   [21] left_pupil   — arbitrary units (not mm)
            #   [49] status       — 0 = valid, 2 = invalid / uncalibrated
            s = samples[0]
            iohub_time = s[7]
            lgx, lgy = s[11], s[12]
            lpupil = s[21]
            status = s[49]
            validity = "valid" if status == 0 else "invalid/uncalibrated"
            print(
                f"[demo] First sample: "
                f"time={iohub_time:.4f} s  "
                f"left_gaze=({lgx:.1f}, {lgy:.1f})  "
                f"pupil={lpupil:.1f} (arb. units)  "
                f"status={validity}"
            )
            if not args.no_mock:
                print(
                    "[demo] Note: gaze coordinates are in screen pixels (no calibration / "
                    "display-unit mapping applied in mock mode)."
                )

        print("[demo] Done.")

    finally:
        tracker._close()
        _reset_singleton()
        if mock_srv is not None:
            mock_srv.stop()
            print("[demo] Mock server stopped.")


if __name__ == "__main__":
    main()
