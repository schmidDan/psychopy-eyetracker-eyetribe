# Coordinate systems & timing (Phase 4)

Placeholder to be completed in Phase 4.

- **Spatial:** Eye Tribe reports gaze in screen **pixels, origin top-left**. `transforms.py` normalizes
  by the Server resolution (`screenresw/h`) into 0-1, then maps to the ioHub Display coordinate bounds
  (origin-centre, configured unit). Include a diagram and a worked example; document the inverse.
- **Temporal:** Eye Tribe `time` is epoch **milliseconds**. `time_sync.ClockSync` maps it to the
  PsychoPy timebase via an offset (RTT-corrected, re-estimated every 5 s). Document the residual
  latency budget = sampling latency (1/rate) + transport.
