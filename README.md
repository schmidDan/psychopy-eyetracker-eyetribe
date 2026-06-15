# psychopy-eyetracker-eyetribe

A native [PsychoPy](https://psychopy.org) ioHub eye-tracker plugin for **The Eye Tribe (ET1000)**.

Once installed, the device is selectable in the Builder *Eyetracker* component and usable from Coder
via the ioHub Common Eye Tracker Interface (config key `eyetracker.hw.eyetribe.EyeTracker`), with
PsychoPy-driven calibration.

> **Status: Phase 0 scaffold.** Module bodies are stubs that raise `NotImplementedError`; the package
> is installable and discoverable, and the test/lint skeleton is in place. Implementation proceeds per
> [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md).
>
> **Repository:** private, single-contributor for now. `main` branch protection is a **deferred TODO**
> — re-enable (require PR + passing CI) before adding collaborators or going public; until then the
> per-phase PR flow is followed by convention. See [`docs/HUMAN_TASKS.md`](docs/HUMAN_TASKS.md).

## Requirements

- **Windows 10/11 x64** (the Eye Tribe Server runs reliably only on Windows).
- **PsychoPy 2026.1.3** Standalone (bundles Python 3.10.11).
- The **Eye Tribe Server** running and an **ET1000** connected (for real use; development uses a mock).

## Install (development)

```bash
# from a Python 3.10 environment with PsychoPy available
pip install -e .[dev]
```

Distribution is via a built wheel attached to a GitHub Release (no public PyPI). Install a release with:

```bash
pip install psychopy_eyetracker_eyetribe-<version>-py3-none-any.whl
```

## Notes

- Sampling rate is auto-adopted from the Server (30 Hz ET1000 / 60 Hz Pro) — a relatively low rate;
  plan paradigms accordingly.
- Pupil size is reported in **arbitrary units**, not millimetres.
- Default gaze samples are **raw** (unfiltered); smoothed (`avg`) is available via config.

## License

GPL-3.0. See [`LICENSE`](LICENSE).
