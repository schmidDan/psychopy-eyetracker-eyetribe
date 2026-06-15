# REFERENCES — verified, externally-fixed facts

Phase 0 fills this in by reading the **installed** PsychoPy 2026.1.3 and the Eye Tribe
documentation. Items marked **[CONFIRMED]** are already verified; **[TO CONFIRM ON MACHINE]**
must be checked against the installed PsychoPy / hardware before the dependent phase relies on them.
The discrepancy procedure (DEVELOPMENT_PLAN.md section 2) applies if any check fails.

## Environment
- **[CONFIRMED]** PsychoPy **2026.1.3** Standalone (Windows), at `C:\Program Files\PsychoPy`.
- **[CONFIRMED]** Bundled interpreter: **Python 3.10.11** (`"C:\Program Files\PsychoPy\python.exe" --version`).

## Packaging & discovery
- **[CONFIRMED]** Reference plugin `psychopy/psychopy-eyetracker-pupil-labs`: setuptools, flat layout,
  `[tool.setuptools.packages.find] where = ["", "<pkg>"]`, `package-data "*" = ["*.yaml"]`.
- **[CONFIRMED]** Device entry-point group: `psychopy.iohub.devices.eyetracker` (name -> module).
- **[CONFIRMED]** Builder settings entry-point group: `psychopy.experiment.components.settings.eyetracking`.
- **[TO CONFIRM ON MACHINE]** The exact call/condition under which PsychoPy injects the entry-point
  device into the importable namespace `psychopy.iohub.devices.eyetracker.hw.eyetribe`
  (auto on iohub launch vs. explicit plugin scan). Record the verified mechanism here.

## ioHub device YAML
- **[CONFIRMED]** Filenames: `default_eyetracker.yaml` + `supported_config_settings.yaml`
  (names used by the in-tree GazePoint GP3 device).
- **[TO CONFIRM ON MACHINE]** Exact key set / schema tokens accepted by the 2026.1.3 loader
  (read the installed GazePoint/Tobii device YAML and align our keys).

## ioHub EyeTrackerDevice interface
- **[TO CONFIRM ON MACHINE]** Exact method signatures of
  `psychopy.iohub.devices.eyetracker.EyeTrackerDevice` in 2026.1.3 (read the installed source).
  Provisional surface used in the stub: `trackerTime/trackerSec`, `setConnectionState/isConnected`,
  `setRecordingState/isRecordingEnabled`, `enableEventReporting`, `runSetupProcedure`, `_poll`,
  `_eyeTrackerToDisplayCoords/_displayToEyeTrackerCoords`, `getEvents/clearEvents`, `getLastSample`,
  `getLastGazePosition/getPosition`, `getConfiguration`.
- **[TO CONFIRM ON MACHINE]** Exact `BinocularEyeSampleEvent` field names (esp. the pupil-size and
  per-eye camera-coordinate attributes) and the `status` validity convention.
- **[TO CONFIRM ON MACHINE]** Base class + signature for the Builder eyetracking settings backend
  (`EyetrackingBackend` import path used in `settings.py`).

## Eye Tribe Tracker API
- **[CONFIRMED via docs]** Wire format, `state` bitmask, calibration sequence, heartbeat — see
  DEVELOPMENT_PLAN.md section 3.
- **[TO CONFIRM ON HARDWARE — Phase 8/8a]** Validate section 3 against one captured real frame
  (`tests/manual/smoke_socket.py` saves `_captured_frame.json`).
