# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/); the project uses
[Semantic Versioning](https://semver.org/). `CHANGELOG.md` is updated for every release tag.

## [Unreleased]

### Added
- **Phase 6 packaging & Builder backend**: fleshed out `EyeTribeEyetrackerBackend` with `key`,
  `getParams()` (host, port, gaze source, calibration target count), and `writeDeviceCode()` so the
  Eye Tribe device appears in the PsychoPy Builder Eyetracker component dropdown. Added a CI
  `wheel-smoke` job that builds the wheel, installs it into a clean environment (no source tree), and
  asserts entry points, YAML, and settings backend attributes resolve correctly.
- **Phase 0 scaffold**: repository structure, packaging & discovery configuration (`pyproject.toml`
  entry points), Windows CI skeleton, PsychoPy-free core module stubs, ioHub device YAML, mock-server
  stub, and the documentation skeleton. See `docs/DEVELOPMENT_PLAN.md`.
