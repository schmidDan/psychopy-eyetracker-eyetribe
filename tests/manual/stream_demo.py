# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""[HARDWARE] Stream demo (Phase 10a): gaze-contingent dot via the Eye Tribe plugin.

A minimal PsychoPy window displays a white circle that follows the gaze
position in real time, fed by :class:`~psychopy_eyetracker_eyetribe.eyetribe.eyetribe_client.EyeTribeClient`.

Development — against the mock (any machine with the package installed):
    python tests/manual/stream_demo.py

Hardware — against the real ET1000 (Eye Tribe Server must be running):
    python tests/manual/stream_demo.py --real
    "C:\\Program Files\\PsychoPy\\python.exe" tests/manual/stream_demo.py --real

Press ESCAPE to quit.
"""

from __future__ import annotations

import argparse
import sys
import time

HOST = "127.0.0.1"
PORT = 6555
DOT_RADIUS_PX = 20


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Eye Tribe stream demo")
    p.add_argument(
        "--real",
        action="store_true",
        help="Connect to the real Eye Tribe Server on port 6555 (default: use mock).",
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

    from psychopy_eyetracker_eyetribe.eyetribe.eyetribe_client import EyeTribeClient

    mock_srv = None
    port = PORT

    if not args.real:
        from psychopy_eyetracker_eyetribe.mock.mock_server import (
            MockEyeTribeServer,
            linear_sweep_model,
        )

        print("Starting mock Eye Tribe server …")
        mock_srv = MockEyeTribeServer(
            host=HOST,
            port=0,  # bind any free port
            frame_rate=30,
            gaze_model=linear_sweep_model(),
        )
        mock_srv.start()
        port = mock_srv.port
        time.sleep(0.05)  # let the accept thread spin up

    client = EyeTribeClient(host=HOST, port=port)
    try:
        print(f"Connecting to Eye Tribe Server at {HOST}:{port} …")
        client.connect()
        params = client.get(["screenresw", "screenresh"])
        screen_w = int(params.get("screenresw", 1920))
        screen_h = int(params.get("screenresh", 1080))
        print(f"Connected: {screen_w}×{screen_h} px, {client.frame_rate} Hz")

        win = pp_visual.Window(
            size=(screen_w, screen_h),
            units="pix",
            fullscr=True,
            allowGUI=False,
            color=(-1, -1, -1),
            colorSpace="rgb",
        )
        dot = pp_visual.Circle(
            win,
            radius=DOT_RADIUS_PX,
            units="pix",
            fillColor=(1, 1, 1),
            lineColor=None,
        )
        label = pp_visual.TextStim(
            win,
            text="Press ESCAPE to quit",
            units="pix",
            height=24,
            color=(0.5, 0.5, 0.5),
            pos=(0, -(screen_h // 2) + 40),
        )

        # Track the most recent valid gaze (start at screen centre)
        gaze_x: float = screen_w / 2.0
        gaze_y: float = screen_h / 2.0

        win.setMouseVisible(False)
        try:
            while True:
                if pp_event.getKeys(["escape"]):
                    break

                # Drain all buffered frames; keep the most recent valid gaze
                for frame in client.frame_buffer.get_all():
                    if frame.get("state", 0) & 0x1:  # STATE_TRACKING_GAZE
                        raw = frame.get("raw", {})
                        gaze_x = float(raw.get("x", gaze_x))
                        gaze_y = float(raw.get("y", gaze_y))

                # Convert from Eye Tribe (top-left origin) to PsychoPy (centre, Y-up)
                dot_x = gaze_x - screen_w / 2.0
                dot_y = -(gaze_y - screen_h / 2.0)
                dot.setPos((dot_x, dot_y))
                dot.draw()
                label.draw()
                win.flip()
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
