# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Eye Tribe ioHub EyeTracker device (Common Eye Tracker Interface).

Phase 3: recording, polling, and BinocularEyeSampleEvent / fixation-event generation.
Phase 4: clock-offset model via time_sync.py.
Phase 5: PsychoPy-driven calibration.
Phase 9: coordinate conversion delegates to the ioHub Display device
         (_pixel2DisplayCoord / display2PIxelCoord), matching the base-class pattern.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from psychopy.iohub.constants import EventConstants, EyeTrackerConstants
from psychopy.iohub.devices import Computer, Device
from psychopy.iohub.devices.eyetracker import EyeTrackerDevice

from .eyetribe_client import STATE_CONNECTED, EyeTribeClient
from .frames import Frame, FrameParseError, parse_frame
from .time_sync import ClockSync

log = logging.getLogger(__name__)

ET_UNDEFINED = EyeTrackerConstants.UNDEFINED
getTime = Computer.getTime


class EyeTracker(EyeTrackerDevice):
    """ioHub Common Eye Tracker Interface implementation for The Eye Tribe (ET1000)."""

    # tracker ``time`` field is a monotonic millisecond counter (~uptime); 0.001 converts to sec
    DEVICE_TIMEBASE_TO_SEC = 0.001

    # Calibration timing (seconds); exposed as class attributes so tests can override them.
    _CALIB_SETTLE_S: float = 0.750  # = SETTLE_MS / 1000
    _CALIB_SAMPLE_S: float = 1.000  # = SAMPLE_MS / 1000

    EVENT_CLASS_NAMES = [
        "BinocularEyeSampleEvent",
        "FixationStartEvent",
        "FixationEndEvent",
    ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialise the Eye Tribe ioHub device from the device config dict."""
        EyeTrackerDevice.__init__(self, *args, **kwargs)
        config = self.getConfiguration()
        host = config.get("host", "127.0.0.1")
        port = int(config.get("port", 6555))
        self._gaze_source: str = config.get("gaze_source", "raw")
        self._client = EyeTribeClient(host=host, port=port)
        self._recording = False
        # Phase 4: ClockSync instance (created fresh at each recording start)
        self._clock_sync: ClockSync | None = None
        # Server-reported screen resolution (updated from server at connect)
        self._screen_w: int = 1920
        self._screen_h: int = 1080
        # fixation state tracking
        self._last_fix: bool = False
        self._fix_start_time: float = 0.0
        self._fix_start_gaze: tuple[float, float] = (0.0, 0.0)
        self._fix_start_pupil: float = 0.0
        self._latest_sample = None
        self._latest_gaze_position = None

    # ── connection lifecycle ──────────────────────────────────────────────────

    def setConnectionState(self, enable: bool) -> bool:
        """Connect to (``True``) or disconnect from (``False``) the Eye Tribe Server."""
        if enable:
            if self._client.state != STATE_CONNECTED:
                try:
                    self._client.connect()
                    self._fetch_screen_resolution()
                except Exception as exc:
                    log.error("EyeTracker: connect failed: %s", exc)
        else:
            self._client.close()
        return self.isConnected()

    def _fetch_screen_resolution(self) -> None:
        """Read screenresw / screenresh from the server and cache them."""
        try:
            params = self._client.get(["screenresw", "screenresh"])
            self._screen_w = int(params.get("screenresw", self._screen_w))
            self._screen_h = int(params.get("screenresh", self._screen_h))
            log.info(
                "EyeTracker: screen resolution from server = %dx%d",
                self._screen_w,
                self._screen_h,
            )
        except Exception as exc:
            log.warning(
                "EyeTracker: could not read screen resolution, using defaults (%dx%d): %s",
                self._screen_w,
                self._screen_h,
                exc,
            )

    def isConnected(self) -> bool:
        """Return ``True`` when the socket to the Eye Tribe Server is open."""
        return self._client.state == STATE_CONNECTED

    # ── recording lifecycle ───────────────────────────────────────────────────

    def setRecordingState(self, recording: bool) -> bool:
        """Enable or disable gaze-event recording and ioHub event reporting."""
        current = self.isRecordingEnabled()
        if recording and not current:
            self._recording = True
            self._clock_sync = ClockSync()  # fresh sync at each recording start
            self._last_fix = False
        elif not recording and current:
            self._recording = False
        # Directly update the ioHub reporting flag (avoids clearEvents → _iohub_server call)
        self._is_reporting_events = recording
        return recording

    def isRecordingEnabled(self) -> bool:
        """Return ``True`` while gaze recording is active."""
        return self._recording

    def enableEventReporting(self, enabled: bool = True) -> bool:
        """Delegate to :meth:`setRecordingState` (ioHub hook)."""
        return self.setRecordingState(enabled)

    # ── calibration (Phase 5) ─────────────────────────────────────────────────

    def runSetupProcedure(self, calibration_args: Any = None) -> Any:  # noqa: C901
        """PsychoPy-driven Eye Tribe calibration.

        Opens a full-screen window, presents animated targets for each calibration
        point, sequences the Eye Tribe calibration protocol via
        :class:`~.calibration.CalibrationSequencer`, parses the result, shows an
        accuracy summary, and offers accept / redo.  Restores the pre-calibration
        state (closes the calibration window) on exit.

        Returns
        -------
        ``EyeTrackerConstants.EYETRACKER_OK`` (200) on accept,
        ``EyeTrackerConstants.EYETRACKER_CALIBRATION_ERROR`` (203) on abort.
        """
        try:
            import psychopy.event as pp_event
            import psychopy.visual as pp_visual
        except ImportError:
            log.error("PsychoPy not available; cannot run calibration")
            return EyeTrackerConstants.EYETRACKER_INTERFACE_METHOD_NOT_SUPPORTED

        from .calibration import DEFAULT_TARGET_COUNT, SUPPORTED_TARGET_COUNTS

        config = self.getConfiguration()
        calib_cfg = config.get("calibration", {})
        target_count = int(calib_cfg.get("target_count", DEFAULT_TARGET_COUNT))
        if target_count not in SUPPORTED_TARGET_COUNTS:
            log.warning(
                "calibration.target_count %d unsupported; using %d",
                target_count,
                DEFAULT_TARGET_COUNT,
            )
            target_count = DEFAULT_TARGET_COUNT

        screen_w = self._screen_w
        screen_h = self._screen_h

        try:
            monitor_name = self._display_device.getPsychopyMonitorName()
            screen_index = self._display_device.getIndex()
        except AttributeError:
            monitor_name = "testMonitor"
            screen_index = 0

        win = pp_visual.Window(
            size=(screen_w, screen_h),
            monitor=monitor_name,
            units="pix",
            fullscr=True,
            allowGUI=False,
            screen=screen_index,
            color=(-1, -1, -1),
            colorSpace="rgb",
        )
        win.setMouseVisible(False)

        try:
            return self._run_calib_loop(win, target_count, screen_w, screen_h, pp_event, pp_visual)
        finally:
            win.setMouseVisible(True)
            win.close()

    def _run_calib_loop(
        self,
        win: Any,
        target_count: int,
        screen_w: int,
        screen_h: int,
        pp_event: Any,
        pp_visual: Any,
    ) -> Any:
        """Inner calibration loop; separated from window creation for testability."""
        from .calibration import CalibrationSequencer, parse_calibresult, point_layout

        settle_s = self._CALIB_SETTLE_S
        sample_s = self._CALIB_SAMPLE_S

        sequencer = CalibrationSequencer(self._client._request)

        # ── stimuli ────────────────────────────────────────────────────────────
        outer = pp_visual.Circle(
            win, radius=30, units="pix", fillColor=(0.8, 0, 0), lineColor=(1, 1, 1), lineWidth=2
        )
        inner = pp_visual.Circle(win, radius=8, units="pix", fillColor=(1, 1, 1), lineColor=None)
        msg_stim = pp_visual.TextStim(
            win, text="", units="pix", height=28, color=(1, 1, 1), wrapWidth=screen_w * 0.9
        )

        layout = point_layout(target_count)

        while True:  # redo loop
            # ── intro screen ───────────────────────────────────────────────────
            msg_stim.setText(
                f"Eye Tribe Calibration  ({target_count} points)\n\n"
                "Look at each dot until it disappears.\n\n"
                "SPACE  =  start     ESCAPE  =  abort"
            )
            while True:
                msg_stim.draw()
                win.flip()
                keys = pp_event.getKeys(["space", "escape"])
                if "escape" in keys:
                    return EyeTrackerConstants.EYETRACKER_CALIBRATION_ERROR
                if "space" in keys:
                    break

            pp_event.clearEvents()
            sequencer.start(target_count)

            abort = False
            last_calibresult_raw: dict[str, Any] | None = None

            for x_norm, y_norm in layout:
                # Pixel coords for the Eye Tribe API (top-left origin)
                x_px = x_norm * screen_w
                y_px = y_norm * screen_h
                # PsychoPy pix coords (centre origin, Y-up)
                x_disp = x_px - screen_w / 2.0
                y_disp = -(y_px - screen_h / 2.0)

                outer.setPos((x_disp, y_disp))
                inner.setPos((x_disp, y_disp))

                # Settle — participant fixates the target
                settle_end = time.monotonic() + settle_s
                while time.monotonic() < settle_end:
                    outer.draw()
                    inner.draw()
                    win.flip()
                    if pp_event.getKeys(["escape"]):
                        abort = True
                        break
                if abort:
                    break

                # Sample window — Eye Tribe records gaze
                sequencer.point_start(x_px, y_px)
                sample_end = time.monotonic() + sample_s
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
                return EyeTrackerConstants.EYETRACKER_CALIBRATION_ERROR

            # ── accuracy summary ───────────────────────────────────────────────
            if last_calibresult_raw is not None:
                result = parse_calibresult(last_calibresult_raw)
                ok_str = "OK" if result.success else "FAILED"
                lines = [f"Calibration {ok_str}  |  Overall: {result.avg_error_deg:.2f}°"]
                for i, pt in enumerate(result.per_point, 1):
                    ad = pt.get("ad", float("nan"))
                    lines.append(f"  Point {i:2d}: {ad:.2f}°")
                lines.append("\nSPACE  =  accept     R  =  redo     ESCAPE  =  abort")
                summary = "\n".join(lines)
            else:
                summary = "Calibration complete.\n\nSPACE = accept     R = redo     ESCAPE = abort"

            while True:
                msg_stim.setText(summary)
                msg_stim.draw()
                win.flip()
                keys = pp_event.getKeys(["space", "r", "escape"])
                if "space" in keys:
                    return EyeTrackerConstants.EYETRACKER_OK
                if "r" in keys:
                    sequencer.clear()
                    break  # restart redo loop
                if "escape" in keys:
                    return EyeTrackerConstants.EYETRACKER_CALIBRATION_ERROR

    # ── polling ───────────────────────────────────────────────────────────────

    def _poll(self) -> None:
        """Drain the frame buffer and emit ioHub events (called by the ioHub timer)."""
        if not self.isConnected() or not self.isRecordingEnabled():
            return

        logged_time = getTime()
        raw_frames = self._client.frame_buffer.get_all()

        for raw_frame in raw_frames:
            try:
                frame = parse_frame(raw_frame)
            except FrameParseError as exc:
                log.warning("EyeTracker._poll: skipping frame: %s", exc)
                continue

            self._process_frame(frame, logged_time)

    def _process_frame(self, frame: Frame, logged_time: float) -> None:
        """Convert one :class:`~.frames.Frame` to ioHub events and push them to the buffer."""
        device_time = frame.time_ms * self.DEVICE_TIMEBASE_TO_SEC

        # Phase 4: use ClockSync for accurate PsychoPy-timebase conversion.
        if self._clock_sync is not None:
            self._clock_sync.update(frame.time_ms, logged_time)
            iohub_time = self._clock_sync.to_psychopy_time(frame.time_ms)
        else:
            iohub_time = logged_time  # should not happen after setRecordingState(True)

        gaze_source = self._gaze_source
        left_gaze = frame.left.raw if gaze_source == "raw" else frame.left.avg
        right_gaze = frame.right.raw if gaze_source == "raw" else frame.right.avg
        combined = frame.gaze(gaze_source)

        in_bounds = 0 <= combined.x <= self._screen_w and 0 <= combined.y <= self._screen_h
        is_zero_sentinel = combined.x == 0.0 and combined.y == 0.0
        status = 0 if (frame.is_gaze_valid() and in_bounds and not is_zero_sentinel) else 2

        lgx, lgy = self._eyeTrackerToDisplayCoords((left_gaze.x, left_gaze.y))
        rgx, rgy = self._eyeTrackerToDisplayCoords((right_gaze.x, right_gaze.y))
        cgx, cgy = self._eyeTrackerToDisplayCoords((combined.x, combined.y))

        # BinocularEyeSampleEvent — 50 fields matching CLASS_ATTRIBUTE_NAMES order:
        # [experiment_id, session_id, device_id, event_id, type,
        #  device_time, logged_time, time, confidence_interval, delay, filter_id,
        #  left_gaze_x … left_velocity_xy,
        #  right_gaze_x … right_velocity_xy,
        #  status]
        sample = [
            0,
            0,
            0,
            Device._getNextEventID(),
            EventConstants.BINOCULAR_EYE_SAMPLE,
            device_time,
            logged_time,
            iohub_time,
            0,
            0,
            0,
            # left eye (19 fields)
            lgx,
            lgy,
            ET_UNDEFINED,  # gaze_x/y/z
            frame.left.pcenter.x,
            frame.left.pcenter.y,
            ET_UNDEFINED,  # eye_cam_x/y/z
            ET_UNDEFINED,
            ET_UNDEFINED,  # angle_x/y
            frame.left.raw.x,
            frame.left.raw.y,  # raw_x/y (device pixels)
            frame.left.psize,
            EyeTrackerConstants.PUPIL_AREA,  # pupil_measure1, _type
            ET_UNDEFINED,
            ET_UNDEFINED,  # pupil_measure2, _type
            ET_UNDEFINED,
            ET_UNDEFINED,  # ppd_x/y
            ET_UNDEFINED,
            ET_UNDEFINED,
            ET_UNDEFINED,  # velocity_x/y/xy
            # right eye (19 fields)
            rgx,
            rgy,
            ET_UNDEFINED,
            frame.right.pcenter.x,
            frame.right.pcenter.y,
            ET_UNDEFINED,
            ET_UNDEFINED,
            ET_UNDEFINED,
            frame.right.raw.x,
            frame.right.raw.y,
            frame.right.psize,
            EyeTrackerConstants.PUPIL_AREA,
            ET_UNDEFINED,
            ET_UNDEFINED,
            ET_UNDEFINED,
            ET_UNDEFINED,
            ET_UNDEFINED,
            ET_UNDEFINED,
            ET_UNDEFINED,
            # status (1 field)
            status,
        ]

        self._latest_sample = sample
        if status == 0:
            self._latest_gaze_position = (cgx, cgy)
        self._addNativeEventToBuffer(sample)

        self._emit_fixation_events(frame, iohub_time, logged_time, lgx, lgy, frame.left.psize)

    def _emit_fixation_events(
        self,
        frame: Frame,
        iohub_time: float,
        logged_time: float,
        gaze_x: float,
        gaze_y: float,
        pupil: float,
    ) -> None:
        """Emit FixationStartEvent / FixationEndEvent on ``fix`` state transitions."""
        was_fix = self._last_fix
        is_fix = frame.fix

        if is_fix and not was_fix:
            # Fixation start — 29 fields
            self._fix_start_time = iohub_time
            self._fix_start_gaze = (gaze_x, gaze_y)
            self._fix_start_pupil = pupil
            fix_start = [
                0,
                0,
                0,
                Device._getNextEventID(),
                EventConstants.FIXATION_START,
                iohub_time,
                logged_time,
                iohub_time,
                0,
                0,
                0,
                EyeTrackerConstants.BINOCULAR,  # eye
                gaze_x,
                gaze_y,
                ET_UNDEFINED,  # gaze_x/y/z
                ET_UNDEFINED,
                ET_UNDEFINED,  # angle_x/y
                ET_UNDEFINED,
                ET_UNDEFINED,  # raw_x/y
                pupil,
                EyeTrackerConstants.PUPIL_AREA,  # pupil_measure1, _type
                ET_UNDEFINED,
                ET_UNDEFINED,  # pupil_measure2, _type
                ET_UNDEFINED,
                ET_UNDEFINED,  # ppd_x/y
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,  # velocity_x/y/xy
                0,  # status
            ]
            self._addNativeEventToBuffer(fix_start)

        elif not is_fix and was_fix:
            # Fixation end — 65 fields
            duration = iohub_time - self._fix_start_time
            sg_x, sg_y = self._fix_start_gaze
            sp = self._fix_start_pupil
            avg_x = (sg_x + gaze_x) / 2.0
            avg_y = (sg_y + gaze_y) / 2.0
            avg_p = (sp + pupil) / 2.0
            fix_end = [
                0,
                0,
                0,
                Device._getNextEventID(),
                EventConstants.FIXATION_END,
                iohub_time,
                logged_time,
                iohub_time,
                0,
                0,
                0,
                EyeTrackerConstants.BINOCULAR,  # eye
                duration,  # duration
                # start (16 fields)
                sg_x,
                sg_y,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                sp,
                EyeTrackerConstants.PUPIL_AREA,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                # end (16 fields)
                gaze_x,
                gaze_y,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                pupil,
                EyeTrackerConstants.PUPIL_AREA,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                # average (16 fields)
                avg_x,
                avg_y,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                avg_p,
                EyeTrackerConstants.PUPIL_AREA,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                # peak velocity (3 fields)
                ET_UNDEFINED,
                ET_UNDEFINED,
                ET_UNDEFINED,
                # status
                0,
            ]
            self._addNativeEventToBuffer(fix_end)

        self._last_fix = is_fix

    # ── timing ────────────────────────────────────────────────────────────────

    def trackerTime(self) -> float:
        """Return estimated current tracker time in milliseconds.

        Uses the ClockSync offset when recording has been started at least once
        (and a frame has arrived).  Falls back to ``getTime() / DEVICE_TIMEBASE_TO_SEC``
        if the sync has not been initialised yet.
        """
        if self._clock_sync is not None and self._clock_sync.is_initialized:
            # offset = local_s - tracker_s  →  tracker_s = local_s - offset
            return (getTime() - self._clock_sync.offset) / self.DEVICE_TIMEBASE_TO_SEC
        return getTime() / self.DEVICE_TIMEBASE_TO_SEC

    def trackerSec(self) -> float:
        """Return estimated current tracker time in seconds."""
        return self.trackerTime() * self.DEVICE_TIMEBASE_TO_SEC

    # ── coordinate transforms ─────────────────────────────────────────────────

    def _eyeTrackerToDisplayCoords(self, eyetracker_point: Any) -> tuple[float, float]:
        """Convert Eye Tribe pixel coords (top-left origin) to ioHub display coords.

        Delegates to the ioHub Display device's ``_pixel2DisplayCoord`` method,
        which handles all unit systems (pix, norm, height, deg) and multi-monitor
        index resolution — matching the base-class default pattern exactly.
        Falls back to a pixel pass-through when no display device is present
        (unit-test harness without ioHub).
        """
        gaze_x, gaze_y = float(eyetracker_point[0]), float(eyetracker_point[1])
        try:
            return self._display_device._pixel2DisplayCoord(  # type: ignore[no-any-return]
                gaze_x, gaze_y, self._display_device.getIndex()
            )
        except (AttributeError, TypeError):
            log.debug("_eyeTrackerToDisplayCoords: no display device, passing through pixels")
            return gaze_x, gaze_y

    def _displayToEyeTrackerCoords(self, x: float, y: float) -> tuple[float, float]:
        """Inverse: convert ioHub display coords back to Eye Tribe pixel coords.

        Delegates to the ioHub Display device's ``display2PIxelCoord`` method
        (note the capitalisation: ``PIxel``, matching the installed PsychoPy source).
        Falls back to a pixel pass-through when no display device is present.
        """
        try:
            return self._display_device.display2PIxelCoord(  # type: ignore[no-any-return]
                x, y, self._display_device.getIndex()
            )
        except (AttributeError, TypeError):
            log.debug("_displayToEyeTrackerCoords: no display device, passing through pixels")
            return x, y

    # ── teardown ──────────────────────────────────────────────────────────────

    def _close(self) -> None:
        """Stop recording, disconnect, and call the base-class teardown."""
        self.setRecordingState(False)
        self.setConnectionState(False)
        EyeTrackerDevice._close(self)
