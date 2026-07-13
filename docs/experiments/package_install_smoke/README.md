# Package Install Smoke

Status: `pass`.

This smoke test proves local wheel build/install, package data inclusion, CLI entry point, and Python API preflight. It is not a PyPI release or upstream LeRobot/Rerun integration claim.

## Checks

| Check | Pass |
|---|---:|
| wheel_built | True |
| installed_non_editable | True |
| cli_preflight_passed | True |
| api_preflight_passed | True |

## Wheel

- File: `worldepisode-0.1.0-py3-none-any.whl`
- Size bytes: `23802`
