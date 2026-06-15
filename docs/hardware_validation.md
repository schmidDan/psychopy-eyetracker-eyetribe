# Hardware validation ([HARDWARE])

Each item is one script under `tests/manual/`; ordered so failures localize. Record for every run:
device serial, Eye Tribe Server version, Windows build, date, operator, result, evidence path.

1. **Server reachable** — `smoke_socket.py` connects to `:6555`; `get` returns `framerate`,
   `screenresw/h`, `trackerstate`. Pass: values returned, `trackerstate == 0`.
2. **Stream** — push enabled; >= 100 frames. Pass: rate ~30 Hz, plausible gaze pixels, sane `state`;
   one frame committed as golden fixture (`_captured_frame.json`).
3. **Heartbeat endurance** — stream 60 s with heartbeats. Pass: no disconnect.
4. **Plugin stream** — `stream_demo.py` gaze dot tracks the eyes. Pass: dot follows gaze.
5. **Calibration** — `calibration_demo.py` 9-point. Pass: completes, accuracy reported, redo works.
6. **Accuracy / precision / timing** — validation experiment (Phase 8d). Pass: metrics recorded below.

## Results

_None yet — populated in Phase 8._
