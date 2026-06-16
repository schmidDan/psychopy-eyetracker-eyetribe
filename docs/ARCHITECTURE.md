# Architecture

See DEVELOPMENT_PLAN.md section 4 for the authoritative diagram and narrative.

Summary: an ioHub `EyeTracker` (the only PsychoPy-coupled module, plus the Builder `settings.py`
backend) drives a PsychoPy-free transport (`EyeTribeClient`) that talks the Eye Tribe TCP/JSON
protocol. The PsychoPy-free core — `eyetribe_client`, `frames`, `time_sync`, `calibration`,
`mock_server` — is unit-testable standalone and is exercised against `MockEyeTribeServer` in CI.
(`transforms.py` was removed in Phase 9; coordinate conversion is delegated to the ioHub Display device.)
