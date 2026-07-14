#!/usr/bin/env python3
"""Build and smoke-test the packaged WorldEpisode wheel.

The release gate already validates source files and editable installation. This script checks the
packaged artifact: the wheel can be built, installed non-editably into a fresh virtual environment,
the `worldepisode` console script exists, package data schemas are present, and the Python API can
preflight a committed example.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "experiments" / "package_install_smoke"
SCHEMA = "worldepisode_package_install_smoke_v1"
AUDIT_DATE = "2026-07-13"


def run_command(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
        "passed": completed.returncode == 0,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def venv_script(venv_dir: Path, name: str) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / f"{name}.exe"
    return venv_dir / "bin" / name


def has_pip() -> bool:
    probe = run_command([sys.executable, "-m", "pip", "--version"])
    return probe["passed"]


def remove_generated_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def stable_command_value(value: Any, tmp_dir: Path) -> Any:
    if isinstance(value, str):
        stable = value.replace(str(tmp_dir), "$TMPDIR").replace(str(ROOT), "$REPO")
        stable = re.sub(r"\.tmp-[A-Za-z0-9_]+", ".tmp-<build>", stable)
        stable = re.sub(r"\b\d+ms\b", "<duration>", stable)
        return stable
    if isinstance(value, list):
        return [stable_command_value(item, tmp_dir) for item in value]
    if isinstance(value, dict):
        return {key: stable_command_value(item, tmp_dir) for key, item in value.items()}
    return value


def stable_command_record(record: dict[str, Any], tmp_dir: Path) -> dict[str, Any]:
    return {
        "command": stable_command_value(record.get("command", []), tmp_dir),
        "returncode": record.get("returncode"),
        "passed": record.get("passed"),
        "stdout": stable_command_value(record.get("stdout", ""), tmp_dir),
        "stderr": stable_command_value(record.get("stderr", ""), tmp_dir),
    }


def build_report(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    commands: list[dict[str, Any]] = []
    egg_info = ROOT / "worldepisode.egg-info"
    egg_info_existed = egg_info.exists()
    try:
        with tempfile.TemporaryDirectory(prefix="worldepisode-wheel-smoke-") as tmp:
            tmp_dir = Path(tmp)
            wheel_dir = tmp_dir / "wheels"
            wheel_dir.mkdir()
            venv_dir = tmp_dir / "venv"
            build_backend = "pip" if has_pip() else "uv"

            if build_backend == "pip":
                build = run_command(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "wheel",
                        "--no-deps",
                        "--no-build-isolation",
                        "--wheel-dir",
                        str(wheel_dir),
                        ".",
                    ]
                )
            elif shutil.which("uv"):
                build = run_command(["uv", "build", "--wheel", "--out-dir", str(wheel_dir)])
            else:
                build = {
                    "command": [sys.executable, "-m", "pip", "wheel", "."],
                    "returncode": None,
                    "stdout": "",
                    "stderr": "Neither python -m pip nor uv is available.",
                    "passed": False,
                }
            commands.append(build)
            wheels = sorted(wheel_dir.glob("worldepisode-*.whl"))

            venv_created = False
            if build["passed"] and wheels:
                if build_backend == "pip":
                    try:
                        venv.EnvBuilder(with_pip=True, system_site_packages=True, clear=True).create(venv_dir)
                        venv_created = True
                        install = run_command(
                            [
                                str(venv_python(venv_dir)),
                                "-m",
                                "pip",
                                "install",
                                "--no-deps",
                                str(wheels[0]),
                            ]
                        )
                    except Exception as exc:  # noqa: BLE001 - report environment-specific venv failures.
                        install = {
                            "command": [
                                str(venv_python(venv_dir)),
                                "-m",
                                "pip",
                                "install",
                                "--no-deps",
                                str(wheels[0]),
                            ],
                            "returncode": None,
                            "stdout": "",
                            "stderr": repr(exc),
                            "passed": False,
                        }
                else:
                    create_venv = run_command(
                        ["uv", "venv", "--python", sys.executable, "--system-site-packages", str(venv_dir)]
                    )
                    commands.append(create_venv)
                    venv_created = create_venv["passed"]
                    install = run_command(
                        [
                            "uv",
                            "pip",
                            "install",
                            "--python",
                            str(venv_python(venv_dir)),
                            "--no-deps",
                            str(wheels[0]),
                        ]
                    )
                commands.append(install)
            else:
                install = {
                    "passed": False,
                    "returncode": None,
                    "stdout": "",
                    "stderr": "wheel build failed or no wheel found",
                }

            if venv_created and install.get("passed"):
                cli = run_command(
                    [
                        str(venv_script(venv_dir, "worldepisode")),
                        "preflight",
                        str(ROOT / "examples" / "minimal.worldepisode.json"),
                        "--json",
                    ]
                )
                commands.append(cli)
                api = run_command(
                    [
                        str(venv_python(venv_dir)),
                        "-c",
                        (
                            "from importlib.resources import files; "
                            "from worldepisode import preflight; "
                            "schema = files('worldepisode').joinpath('schemas/worldepisode-core-v0.schema.json'); "
                            "report = preflight('examples/minimal.worldepisode.json'); "
                            "assert schema.is_file(); "
                            "assert not report.has_failures(); "
                            "print(schema.name)"
                        ),
                    ]
                )
                commands.append(api)
            else:
                cli = {"passed": False, "returncode": None, "stdout": "", "stderr": "install failed"}
                api = {"passed": False, "returncode": None, "stdout": "", "stderr": "install failed"}

            report = {
                "schema": SCHEMA,
                "audit_date": AUDIT_DATE,
                "status": "pass" if all(command.get("passed") for command in commands) else "fail",
                "claim_boundary": (
                    "This smoke test proves local wheel build/install, package data inclusion, CLI "
                    "entry point, and Python API preflight. It is not a PyPI release or upstream "
                    "LeRobot/Rerun integration claim."
                ),
                "python": {
                    "executable": sys.executable,
                    "version": sys.version,
                },
                "build_backend": build_backend,
                "wheel": {
                    "built": bool(wheels),
                    "filename": wheels[0].name if wheels else None,
                    "size_bytes": wheels[0].stat().st_size if wheels else None,
                },
                "checks": {
                    "wheel_built": bool(wheels) and build["passed"],
                    "installed_non_editable": bool(install.get("passed")),
                    "cli_preflight_passed": bool(cli.get("passed")),
                    "api_preflight_passed": bool(api.get("passed")),
                },
                "commands": [stable_command_record(command, tmp_dir) for command in commands],
                "artifacts": {
                    "json": rel(output_dir / "package_install_smoke_report.json"),
                    "markdown": rel(output_dir / "README.md"),
                },
            }
    finally:
        if not egg_info_existed:
            remove_generated_path(egg_info)

    write_json(output_dir / "package_install_smoke_report.json", report)
    write_text(output_dir / "README.md", render_markdown(report))
    return report


def render_markdown(report: dict[str, Any]) -> str:
    rows = [
        f"| {name} | {passed} |"
        for name, passed in report["checks"].items()
    ]
    return "\n".join(
        [
            "# Package Install Smoke",
            "",
            f"Status: `{report['status']}`.",
            "",
            report["claim_boundary"],
            "",
            "## Checks",
            "",
            "| Check | Pass |",
            "|---|---:|",
            *rows,
            "",
            "## Wheel",
            "",
            f"- File: `{report['wheel']['filename']}`",
            f"- Size bytes: `{report['wheel']['size_bytes']}`",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--strict", action="store_true", help="exit non-zero unless the package smoke test passes")
    args = parser.parse_args()
    report = build_report(args.output_dir)
    print(
        json.dumps(
            {
                "status": report["status"],
                "checks": report["checks"],
                "artifacts": report["artifacts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.strict and report["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
