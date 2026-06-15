# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/); the project uses
[Semantic Versioning](https://semver.org/). `CHANGELOG.md` is updated for every release tag.

## [Unreleased]

### Added
- **Phase 7 documentation & examples**: expanded `README.md` with prerequisites
  (Eye Tribe Server install source), install instructions, Coder and Builder quick
  starts, limitations table, and troubleshooting section. Added
  `examples/coder_demo.py` (runs end-to-end against the bundled mock — no hardware
  required), `examples/builder_example.psyexp` (ready-to-open Builder template with
  Eye Tribe configured), and `docs/implementation_notes.md` (device config keys,
  event field table, coordinate system, calibration protocol, known limitations).
  All public API now has docstrings. CI extended with a coder-demo step (runs the
  demo against the mock) and a doc-link check.
- **Phase 6 packaging & Builder backend**: fleshed out `EyeTribeEyetrackerBackend` with `key`,
  `getParams()` (host, port, gaze source, calibration target count), and `writeDeviceCode()` so the
  Eye Tribe device appears in the PsychoPy Builder Eyetracker component dropdown. Added a CI
  `wheel-smoke` job that builds the wheel, installs it into a clean environment (no source tree), and
  asserts entry points, YAML, and settings backend attributes resolve correctly.
- **Phase 0 scaffold**: repository structure, packaging & discovery configuration (`pyproject.toml`
  entry points), Windows CI skeleton, PsychoPy-free core module stubs, ioHub device YAML, mock-server
  stub, and the documentation skeleton. See `docs/DEVELOPMENT_PLAN.md`.
