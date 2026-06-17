# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""[HARDWARE] Calibration demo (Phase 11b): full 9-point calibration on the Eye Tribe.

Runs the Eye Tribe 9-point calibration using :class:`~psychopy_eyetracker_eyetribe.eyetribe.calibration.CalibrationSequencer`
driven by a PsychoPy window, then prints and saves the accuracy report.

Development — against the mock (any machine with the package installed):
    python tests/manual/calibration_demo.py

Hardware — against the real ET1000 (Eye Tribe Server must be running):
    python tests/manual/calibration_demo.py --real
    "C:\\Program Files\\PsychoPy\\python.exe" tests/manual/calibration_demo.py --real

Keys:
    SPACE   — start / accept result
    ESCAPE  — abort
    R       — redo (on the result screen)

Output:
    ``calibration_result.json`` — raw ``calibresult`` payload from the server.
    ``docs/hardware_validation.md`` — checklist item 5 evidence (manual).
"""

from __future__ import annotations

import argparse
import json
import sys
import time

HOST = "127.0.0.1"
PORT = 6555

SETTLE_S = 0.75  # seconds to let participant fixate before sampling starts
SAMPLE_S = 1.00  # seconds sampling window per calibration point


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Eye Tribe calibration demo")
    p.add_argument(
        "--real",
        action="store_true",
        help="Connect to the real Eye Tribe Server on port 6555 (default: use mock).",
    )
    p.add_argument(
        "--output",
        default="calibration_result.json",
        metavar="PATH",
        help="Path to save the calibresult JSON (default: calibration_result.json).",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    try:
        import psychopy.event as pp_event
        import psychopy.visual as pp_visual
    except ImportError:
        print("ERROR: PsychoPy is required. Run with the PsychoPy interpreter.", file=sys.stderr)
        return 1

    from psychopy_eyetracker_eyetribe.eyetribe.calibration import (
        CalibrationSequencer,
        parse_calibresult,
        point_layout,
    )
    from psychopy_eyetracker_eyetribe.eyetribe.eyetribe_client import EyeTribeClient

    mock_srv = None
    port = PORT

    if not args.real:
        from psychopy_eyetracker_eyetribe.mock.mock_server import MockEyeTribeServer

        print("Starting mock Eye Tribe server …")
        mock_srv = MockEyeTribeServer(host=HOST, port=0, frame_rate=30)
        mock_srv.start()
        port = mock_srv.port
        time.sleep(0.05)

    client = EyeTribeClient(host=HOST, port=port)
    try:
        print(f"Connecting to {HOST}:{port} …")
        client.connect()
        params = client.get(["screenresw", "screenresh"])
        screen_w = int(params.get("screenresw", 1920))
        screen_h = int(params.get("screenresh", 1080))
        print(f"Connected: {screen_w}×{screen_h} px, {client.frame_rate} Hz")

        sequencer = CalibrationSequencer(client._request)
        layout = point_layout(9)

        win = pp_visual.Window(
            size=(screen_w, screen_h),
            units="pix",
            fullscr=True,
            allowGUI=False,
            color=(-1, -1, -1),
            colorSpace="rgb",
        )
        outer = pp_visual.Circle(
            win, radius=30, units="pix", fillColor=(0.8, 0, 0), lineColor=(1, 1, 1), lineWidth=2
        )
        inner = pp_visual.Circle(win, radius=8, units="pix", fillColor=(1, 1, 1), lineColor=None)
        msg_stim = pp_visual.TextStim(
            win,
            text="",
            units="pix",
            height=28,
            color=(1, 1, 1),
            wrapWidth=screen_w * 0.9,
        )

        win.setMouseVisible(False)
        calib_result_raw = None

        try:
            while True:  # redo loop
                # ── intro screen ──────────────────────────────────────────────
                msg_stim.setText(
                    "Eye Tribe Calibration  (9 points)\n\n"
                    "Look at each dot until it disappears.\n\n"
                    "SPACE  =  start     ESCAPE  =  abort"
                )
                while True:
                    msg_stim.draw()
                    win.flip()
                    keys = pp_event.getKeys(["space", "escape"])
                    if "escape" in keys:
                        print("Aborted by user on intro screen.")
                        return 1
                    if "space" in keys:
                        break

                pp_event.clearEvents()
                # abort() clears any stuck in-progress session from a crash/redo.
                # Do NOT call clear() here — it drops the server's gaze tracking state,
                # causing calibration capture to collect zero valid frames.
                sequencer.abort()
                start_reply = sequencer.start(9)
                if start_reply.get("statuscode", 200) != 200:
                    msg = start_reply.get("values", {}).get("statusmessage", "unknown error")
                    print(
                        f"ERROR: calibration start failed ({start_reply.get('statuscode')}): {msg}"
                    )
                    return 1
                abort = False
                last_calibresult_raw = None

                for x_norm, y_norm in layout:
                    x_px = x_norm * screen_w
                    y_px = y_norm * screen_h
                    # PsychoPy pix coords: centre-origin, Y-up
                    x_disp = x_px - screen_w / 2.0
                    y_disp = -(y_px - screen_h / 2.0)
                    outer.setPos((x_disp, y_disp))
                    inner.setPos((x_disp, y_disp))

                    # Settle — participant fixates
                    settle_end = time.monotonic() + SETTLE_S
                    while time.monotonic() < settle_end:
                        outer.draw()
                        inner.draw()
                        win.flip()
                        if pp_event.getKeys(["escape"]):
                            abort = True
                            break
                    if abort:
                        break

                    # Sample window
                    sequencer.point_start(x_px, y_px)
                    sample_end = time.monotonic() + SAMPLE_S
                    while time.monotonic() < sample_end:
                        outer.draw()
                        inner.draw()
                        win.flip()
                        if pp_event.getKeys(["escape"]):
                            abort = True
                            break

                    raw = sequencer.point_end()
                    if raw is not None:
                        last_calibresult_raw = raw
                    if abort:
                        break

                if abort:
                    sequencer.abort()
                    print("Calibration aborted mid-sequence.")
                    return 1

                # Real ET1000 does not embed calibresult in pointend replies —
                # fetch it separately after the sequence completes.
                if last_calibresult_raw is None:
                    fetched = client.get(["calibresult"])
                    last_calibresult_raw = fetched.get("calibresult")

                # ── accuracy summary ─────────────────────────────────────────
                if last_calibresult_raw is not None:
                    calib_result_raw = last_calibresult_raw
                    result = parse_calibresult(last_calibresult_raw)
                    ok_str = "OK" if result.success else "FAILED"
                    lines = [f"Calibration {ok_str}  |  Overall: {result.avg_error_deg:.2f}°"]
                    for i, pt in enumerate(result.per_point, 1):
                        ad = pt.get("acd", {}).get("ad", float("nan"))
                        lines.append(f"  Point {i:2d}: {ad:.2f}°")
                    lines.append("\nSPACE  =  accept     R  =  redo     ESCAPE  =  abort")
                    summary = "\n".join(lines)
                    # Print brief report to console
                    print(lines[0])
                else:
                    summary = (
                        "Calibration complete.\n\nSPACE = accept     R = redo     ESCAPE = abort"
                    )

                while True:
                    msg_stim.setText(summary)
                    msg_stim.draw()
                    win.flip()
                    keys = pp_event.getKeys(["space", "r", "escape"])
                    if "space" in keys:
                        if calib_result_raw is not None:
                            with open(args.output, "w", encoding="utf-8") as fh:
                                json.dump(calib_result_raw, fh, indent=2)
                            print(f"Calibration result saved → {args.output}")
                        print("Calibration accepted.")
                        return 0
                    if "r" in keys:
                        sequencer.clear()
                        break  # restart redo loop
                    if "escape" in keys:
                        print("Aborted by user on result screen.")
                        return 1

        finally:
            win.setMouseVisible(True)
            win.close()

    finally:
        client.close()
        if mock_srv is not None:
            mock_srv.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
