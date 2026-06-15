# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Eye Tribe ioHub EyeTracker device (Common Eye Tracker Interface).

Phase 3: recording, polling, and BinocularEyeSampleEvent / fixation-event generation.
Phase 4: coordinate transforms via transforms.py; clock-offset model via time_sync.py.
Phase 5 will add PsychoPy-driven calibration.
"""

from __future__ import annotations

import logging
from typing import Any

from psychopy.iohub.constants import EventConstants, EyeTrackerConstants
from psychopy.iohub.devices import Computer, Device
from psychopy.iohub.devices.eyetracker import EyeTrackerDevice

from .eyetribe_client import STATE_CONNECTED, EyeTribeClient
from .frames import Frame, FrameParseError, parse_frame
from .time_sync import ClockSync
from .transforms import DisplayBounds, display_to_eyetribe_pixels, eyetribe_pixels_to_display

log = logging.getLogger(__name__)

ET_UNDEFINED = EyeTrackerConstants.UNDEFINED
getTime = Computer.getTime


class EyeTracker(EyeTrackerDevice):
    """ioHub Common Eye Tracker Interface implementation for The Eye Tribe (ET1000)."""

    # tracker ``time`` field is a monotonic millisecond counter (~uptime); 0.001 converts to sec
    DEVICE_TIMEBASE_TO_SEC = 0.001

    EVENT_CLASS_NAMES = [
        "BinocularEyeSampleEvent",
        "FixationStartEvent",
        "FixationEndEvent",
    ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
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
        return self._client.state == STATE_CONNECTED

    # ── recording lifecycle ───────────────────────────────────────────────────

    def setRecordingState(self, recording: bool) -> bool:
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
        return self._recording

    def enableEventReporting(self, enabled: bool = True) -> bool:
        return self.setRecordingState(enabled)

    # ── calibration stub (Phase 5) ────────────────────────────────────────────

    def runSetupProcedure(self, calibration_args: Any = None) -> int:
        return EyeTrackerConstants.EYETRACKER_INTERFACE_METHOD_NOT_SUPPORTED

    # ── polling ───────────────────────────────────────────────────────────────

    def _poll(self) -> None:
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
        device_time = frame.time_ms * self.DEVICE_TIMEBASE_TO_SEC

        # Phase 4: use ClockSync for accurate PsychoPy-timebase conversion.
        if self._clock_sync is not None:
            self._clock_sync.update(frame.time_ms, logged_time)
            iohub_time = self._clock_sync.to_psychopy_time(frame.time_ms)
        else:
            iohub_time = logged_time  # should not happen after setRecordingState(True)

        status = 0 if frame.is_gaze_valid() else 2

        gaze_source = self._gaze_source
        left_gaze = frame.left.raw if gaze_source == "raw" else frame.left.avg
        right_gaze = frame.right.raw if gaze_source == "raw" else frame.right.avg
        combined = frame.gaze(gaze_source)

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
        """Convert Eye Tribe pixel coords to ioHub display coords via transforms.py."""
        gaze_x, gaze_y = float(eyetracker_point[0]), float(eyetracker_point[1])
        try:
            bounds = self._get_display_bounds()
            return eyetribe_pixels_to_display(
                gaze_x, gaze_y, self._screen_w, self._screen_h, bounds
            )
        except Exception:
            return gaze_x, gaze_y

    def _displayToEyeTrackerCoords(self, x: float, y: float) -> tuple[float, float]:
        """Inverse: convert ioHub display coords back to Eye Tribe pixel coords."""
        try:
            bounds = self._get_display_bounds()
            return display_to_eyetribe_pixels(x, y, self._screen_w, self._screen_h, bounds)
        except Exception:
            return x, y

    def _get_display_bounds(self) -> DisplayBounds:
        """Return ``(left, top, right, bottom)`` in display units from the ioHub Display device.

        Falls back to Y-down pixel passthrough bounds ``(0, 0, screen_w, screen_h)``
        when no display device is available (e.g. unit-test harness) or when the
        device does not expose ``getBounds()``.
        """
        try:
            bounds = self._display_device.getBounds()
            if isinstance(bounds, dict):
                return (
                    float(bounds["left"]),
                    float(bounds["top"]),
                    float(bounds["right"]),
                    float(bounds["bottom"]),
                )
            return (float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3]))
        except (AttributeError, TypeError, KeyError, IndexError):
            # No display device or unrecognised format — Y-down pixel passthrough
            return (0.0, 0.0, float(self._screen_w), float(self._screen_h))

    # ── teardown ──────────────────────────────────────────────────────────────

    def _close(self) -> None:
        self.setRecordingState(False)
        self.setConnectionState(False)
        EyeTrackerDevice._close(self)
