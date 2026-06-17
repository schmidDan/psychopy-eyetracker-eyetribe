# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""[HARDWARE] Validation experiment (Phase 11c): spatial accuracy, precision, and timing.

Presents a 9-point grid of targets, records gaze from the Eye Tribe for each,
and computes:

- **Spatial accuracy** — mean Euclidean offset in visual degrees (target vs. mean gaze).
- **Precision** — RMS inter-sample distance in visual degrees.
- **Timing** — median latency (ms) from target onset to first valid gaze shift toward
  the target (approximated from the display-flip timestamp).

Results are printed to the console, saved as JSON, and a pre-formatted table
suitable for pasting into ``docs/hardware_validation.md`` is printed.

Additionally, after calibration the first valid calibrated frame is saved as
``tests/manual/_captured_frame_calibrated.json`` to replace the placeholder
uncalibrated fixture when the human confirms the format is consistent.

Development — against the mock (any machine with the package installed):
    python tests/manual/validation_experiment.py

Hardware — after running calibration_demo.py on the real ET1000:
    python tests/manual/validation_experiment.py --real [options]
    "C:\\Program Files\\PsychoPy\\python.exe" tests/manual/validation_experiment.py --real

Options:
    --real              Connect to the real Eye Tribe Server (default: mock).
    --screen-w-cm CM    Physical screen width in cm (default: 53.1 for 24-inch).
    --screen-h-cm CM    Physical screen height in cm (default: 29.9 for 24-inch).
    --dist-cm CM        Eye-to-screen viewing distance in cm (default: 60).
    --target-s S        Gaze-recording duration per target in seconds (default: 1.0).
    --iti-s S           Inter-target interval (blank screen) in seconds (default: 0.5).
    --output PATH       JSON output path (default: validation_results.json).
    --capture-frame     Save the first valid calibrated frame (use after real calibration).

Press ESCAPE to abort.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

HOST = "127.0.0.1"
PORT = 6555

# Validation target layout: normalised (x, y), origin top-left, values in [0,1].
# Uses the same 9-point grid as the calibration layout (centre-first).
_TARGET_LAYOUT: tuple[tuple[float, float], ...] = (
    (0.5, 0.5),
    (0.1, 0.1),
    (0.9, 0.1),
    (0.9, 0.9),
    (0.1, 0.9),
    (0.1, 0.5),
    (0.9, 0.5),
    (0.5, 0.1),
    (0.5, 0.9),
)

# Radius around a target (pixels) within which a gaze sample counts as "on target"
# for the timing measurement.
_ON_TARGET_RADIUS_PX = 150.0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Eye Tribe validation experiment (Phase 11c)")
    p.add_argument("--real", action="store_true", help="Connect to the real Eye Tribe Server.")
    p.add_argument("--screen-w-cm", type=float, default=53.1, metavar="CM")
    p.add_argument("--screen-h-cm", type=float, default=29.9, metavar="CM")
    p.add_argument("--dist-cm", type=float, default=60.0, metavar="CM")
    p.add_argument("--settle-s", type=float, default=0.5, metavar="S",
                   help="Settle window per target (dot shown, no recording). Default: 0.5 s.")
    p.add_argument("--target-s", type=float, default=1.0, metavar="S",
                   help="Recording window per target (after settle). Default: 1.0 s.")
    p.add_argument("--iti-s", type=float, default=1.0, metavar="S",
                   help="Inter-target interval (fixation cross). Default: 1.0 s.")
    p.add_argument(
        "--output", default="validation_results.json", metavar="PATH", help="JSON output path."
    )
    p.add_argument(
        "--capture-frame",
        action="store_true",
        help="Save first valid calibrated frame to _captured_frame_calibrated.json.",
    )
    return p.parse_args()



def main() -> int:  # noqa: C901
    args = _parse_args()

    try:
        import psychopy.event as pp_event
        import psychopy.visual as pp_visual
    except ImportError:
        print("ERROR: PsychoPy is required. Run with the PsychoPy interpreter.", file=sys.stderr)
        return 1

    from psychopy_eyetracker_eyetribe.eyetribe.eyetribe_client import EyeTribeClient
    from psychopy_eyetracker_eyetribe.eyetribe.validation import (
        compute_accuracy,
        compute_precision,
        compute_timing_stats,
    )

    mock_srv = None
    port = PORT

    if not args.real:
        from psychopy_eyetracker_eyetribe.mock.mock_server import (
            MockEyeTribeServer,
            fixed_point_model,
        )

        print("Starting mock Eye Tribe server …")
        # Sweep through target positions so timing measurements are non-trivial
        mock_srv = MockEyeTribeServer(
            host=HOST,
            port=0,
            frame_rate=30,
            gaze_model=fixed_point_model(960.0, 540.0),
        )
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

        mon_w_cm: float = args.screen_w_cm
        mon_h_cm: float = args.screen_h_cm
        dist_cm: float = args.dist_cm
        settle_s: float = args.settle_s
        target_s: float = args.target_s
        iti_s: float = args.iti_s

        # Build window
        win = pp_visual.Window(
            size=(screen_w, screen_h),
            units="pix",
            fullscr=True,
            allowGUI=False,
            color=(-1, -1, -1),
            colorSpace="rgb",
        )
        target_dot = pp_visual.Circle(
            win, radius=15, units="pix", fillColor=(1, 0.8, 0), lineColor=(1, 1, 1), lineWidth=2
        )
        fixation = pp_visual.ShapeStim(
            win,
            vertices=((0, -10), (0, 10), (0, 0), (-10, 0), (10, 0)),
            units="pix",
            lineWidth=2,
            lineColor=(0.6, 0.6, 0.6),
            closeShape=False,
        )
        msg_stim = pp_visual.TextStim(
            win,
            text="",
            units="pix",
            height=28,
            color=(1, 1, 1),
            wrapWidth=screen_w * 0.9,
        )

        win.setMouseVisible(False)

        # ── wait for the participant to be ready ──────────────────────────────
        msg_stim.setText(
            "Eye Tribe Validation  (9 targets)\n\n"
            "Look at each yellow dot as it appears.\n\n"
            "SPACE  =  start     ESCAPE  =  abort"
        )
        while True:
            msg_stim.draw()
            win.flip()
            keys = pp_event.getKeys(["space", "escape"])
            if "escape" in keys:
                win.setMouseVisible(True)
                win.close()
                return 1
            if "space" in keys:
                break

        pp_event.clearEvents()

        # ── per-target recording ──────────────────────────────────────────────
        per_target_results: list[dict] = []
        calibrated_frame_saved = False
        captured_frame_path = Path("tests/manual/_captured_frame_calibrated.json")

        for t_idx, (x_norm, y_norm) in enumerate(_TARGET_LAYOUT):
            target_x_px = x_norm * screen_w
            target_y_px = y_norm * screen_h
            # PsychoPy pix: centre-origin, Y-up
            target_x_disp = target_x_px - screen_w / 2.0
            target_y_disp = -(target_y_px - screen_h / 2.0)
            target_dot.setPos((target_x_disp, target_y_disp))

            # Inter-target interval: fixation cross, drain buffer
            iti_end = time.monotonic() + iti_s
            client.frame_buffer.get_all()  # flush stale frames
            while time.monotonic() < iti_end:
                fixation.draw()
                win.flip()
                if pp_event.getKeys(["escape"]):
                    win.setMouseVisible(True)
                    win.close()
                    client.close()
                    if mock_srv:
                        mock_srv.stop()
                    return 1

            # Settle window: dot visible, saccade in progress — track latency but
            # discard frames so saccade-flight samples don't bias accuracy.
            client.frame_buffer.get_all()  # flush stale frames right before onset
            onset_t = time.monotonic()
            first_on_target_t: float | None = None
            settle_end = onset_t + settle_s
            while time.monotonic() < settle_end:
                now = time.monotonic()
                target_dot.draw()
                win.flip()
                for frame in client.frame_buffer.get_all():
                    if frame.get("state", 0) & 0x1 and first_on_target_t is None:
                        raw = frame.get("raw", {})
                        gx = float(raw.get("x", screen_w / 2))
                        gy = float(raw.get("y", screen_h / 2))
                        dx = gx - target_x_px
                        dy = gy - target_y_px
                        if math.hypot(dx, dy) < _ON_TARGET_RADIUS_PX:
                            first_on_target_t = now
                if pp_event.getKeys(["escape"]):
                    win.setMouseVisible(True)
                    win.close()
                    client.close()
                    if mock_srv:
                        mock_srv.stop()
                    return 1

            # Recording window: gaze settled on dot — collect samples.
            gaze_samples: list[tuple[float, float]] = []
            record_end = settle_end + target_s
            while True:
                now = time.monotonic()
                target_dot.draw()
                win.flip()

                for frame in client.frame_buffer.get_all():
                    if frame.get("state", 0) & 0x1:  # STATE_TRACKING_GAZE
                        raw = frame.get("raw", {})
                        gx = float(raw.get("x", screen_w / 2))
                        gy = float(raw.get("y", screen_h / 2))
                        gaze_samples.append((gx, gy))

                        # Save first valid calibrated frame if requested
                        if args.capture_frame and not calibrated_frame_saved:
                            with open(captured_frame_path, "w", encoding="utf-8") as fh:
                                json.dump(frame, fh, indent=2)
                            print(f"Calibrated frame saved → {captured_frame_path}")
                            calibrated_frame_saved = True

                        # Timing: first gaze within on-target radius (from dot onset)
                        if first_on_target_t is None:
                            dx = gx - target_x_px
                            dy = gy - target_y_px
                            if math.hypot(dx, dy) < _ON_TARGET_RADIUS_PX:
                                first_on_target_t = now

                if pp_event.getKeys(["escape"]):
                    win.setMouseVisible(True)
                    win.close()
                    client.close()
                    if mock_srv:
                        mock_srv.stop()
                    return 1

                if now >= record_end:
                    break

            # Compute per-target statistics
            valid = [(gx, gy) for gx, gy in gaze_samples]
            mean_gaze = (
                (
                    sum(gx for gx, _ in valid) / len(valid),
                    sum(gy for _, gy in valid) / len(valid),
                )
                if valid
                else (target_x_px, target_y_px)
            )
            latency_s = (first_on_target_t - onset_t) if first_on_target_t is not None else None

            per_target_results.append(
                {
                    "target_idx": t_idx + 1,
                    "target_px": [target_x_px, target_y_px],
                    "mean_gaze_px": list(mean_gaze),
                    "n_valid_samples": len(valid),
                    "latency_s": latency_s,
                    "samples": valid,
                }
            )
            print(
                f"  Target {t_idx + 1:2d} ({x_norm:.1f},{y_norm:.1f}): "
                f"{len(valid)} samples, latency={'N/A' if latency_s is None else f'{latency_s*1000:.0f} ms'}"
            )

        win.setMouseVisible(True)
        win.close()

        # ── aggregate metrics ─────────────────────────────────────────────────
        targets_px = [tuple(r["target_px"]) for r in per_target_results]
        gazes_px = [tuple(r["mean_gaze_px"]) for r in per_target_results]
        latencies = [r["latency_s"] for r in per_target_results if r["latency_s"] is not None]

        accuracy_deg = compute_accuracy(
            targets_px, gazes_px, screen_w, screen_h, mon_w_cm, mon_h_cm, dist_cm  # type: ignore[arg-type]
        )
        # Precision: RMS inter-sample jitter computed per target, then averaged.
        per_target_prec = [
            compute_precision(
                r["samples"], screen_w, screen_h, mon_w_cm, mon_h_cm, dist_cm  # type: ignore[arg-type]
            )
            for r in per_target_results
            if r["n_valid_samples"] >= 2
        ]
        prec_deg = (
            sum(per_target_prec) / len(per_target_prec) if per_target_prec else float("nan")
        )
        saccade_lat = compute_timing_stats(latencies)

        print("\n── Validation results ─────────────────────────────────────────────")
        print(f"  Accuracy (mean offset):          {accuracy_deg:.2f}°")
        print(f"  Precision (RMS jitter):          {prec_deg:.2f}°")
        print(f"  Saccade latency — median:  {saccade_lat['median_ms']:.0f} ms")
        print(f"  Saccade latency — mean:    {saccade_lat['mean_ms']:.0f} ms")
        print(f"  Saccade latency — min/max: {saccade_lat['min_ms']:.0f} / {saccade_lat['max_ms']:.0f} ms")
        print("\nMonitor: " f"{mon_w_cm:.1f}×{mon_h_cm:.1f} cm, {dist_cm:.0f} cm viewing distance")

        # ── save JSON ─────────────────────────────────────────────────────────
        per_target_for_json = [
            {k: v for k, v in r.items() if k != "samples"} for r in per_target_results
        ]
        output = {
            "screen_px": [screen_w, screen_h],
            "monitor_cm": [mon_w_cm, mon_h_cm],
            "viewing_distance_cm": dist_cm,
            "accuracy_deg": accuracy_deg,
            "precision_deg": prec_deg,
            "saccade_latency_ms": saccade_lat,
            "per_target": per_target_for_json,
        }
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(output, fh, indent=2)

        print(f"\nResults saved → {args.output}")

        # ── hardware_validation.md table ──────────────────────────────────────
        print("\n── hardware_validation.md entry (paste under item 6) ─────────────")
        print(f"| Accuracy (mean offset, °)       | {accuracy_deg:.2f} |")
        print(f"| Precision (RMS, °)              | {prec_deg:.2f} |")
        print(f"| Saccade latency median (ms)     | {saccade_lat['median_ms']:.0f} |")
        print(f"| Saccade latency mean (ms)       | {saccade_lat['mean_ms']:.0f} |")
        print(f"| n targets                       | {len(per_target_results)} |")

    finally:
        client.close()
        if mock_srv is not None:
            mock_srv.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
