"""One-line preflight checks for WorldEpisode, LeRobot, and Rerun artifacts."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .validator import Diagnostic, load_json, validate_dataset_manifest, validate_worldepisode


SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}
DEFAULT_FAIL_ON = "warning"


@dataclass
class PreflightReport:
    target: str
    kind: str
    diagnostics: list[Diagnostic] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    fail_on: str = DEFAULT_FAIL_ON

    @property
    def ok(self) -> bool:
        return not self.has_failures()

    def has_failures(self, fail_on: str | None = None) -> bool:
        threshold = SEVERITY_RANK[fail_on or self.fail_on]
        return any(SEVERITY_RANK.get(diag.severity, 2) >= threshold for diag in self.diagnostics)

    def counts(self) -> dict[str, int]:
        counts = {"error": 0, "warning": 0, "info": 0}
        for diag in self.diagnostics:
            counts[diag.severity] = counts.get(diag.severity, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "kind": self.kind,
            "ok": self.ok,
            "fail_on": self.fail_on,
            "counts": self.counts(),
            "summary": self.summary,
            "diagnostics": [diag.to_dict() for diag in self.diagnostics],
        }

    def raise_if_failed(self, fail_on: str | None = None) -> "PreflightReport":
        if self.has_failures(fail_on):
            counts = self.counts()
            raise RuntimeError(
                "WorldEpisode preflight failed for "
                f"{self.target} ({counts.get('error', 0)} errors, {counts.get('warning', 0)} warnings)."
            )
        return self

    def format_text(self) -> str:
        counts = self.counts()
        state = "PASS" if self.ok else "FAIL"
        lines = [
            f"WorldEpisode preflight: {state}",
            f"target: {self.target}",
            f"kind: {self.kind}",
            f"fail_on: {self.fail_on}",
            f"errors: {counts.get('error', 0)}  warnings: {counts.get('warning', 0)}  info: {counts.get('info', 0)}",
        ]
        if self.summary:
            lines.append("summary:")
            for key, value in sorted(self.summary.items()):
                lines.append(f"  {key}: {value}")
        if self.diagnostics:
            lines.append("diagnostics:")
            for diag in self.diagnostics:
                lines.append(f"  [{diag.severity}] {diag.requirement} {diag.location}: {diag.message}")
                if diag.hint:
                    lines.append(f"    hint: {diag.hint}")
        return "\n".join(lines)


def _diag(requirement: str, location: str, message: str, severity: str = "warning", hint: str | None = None) -> Diagnostic:
    return Diagnostic(requirement, location, message, severity, hint)


def _maybe_path(target: str | Path) -> Path:
    return target if isinstance(target, Path) else Path(str(target))


def _kind_from_json(payload: dict[str, Any]) -> str:
    schema_version = payload.get("schema_version")
    if schema_version == "worldepisode-0.1":
        return "worldepisode"
    if schema_version == "worldepisode-dataset-0.1":
        return "worldepisode-dataset"
    if schema_version == "worldepisode-conformance-0.1":
        return "conformance"
    if str(payload.get("profile", "")).startswith("worldepisode"):
        return "worldepisode-sidecar"
    return "json"


def _find_sidecar(root: Path, sidecar: str | Path | None = None) -> Path | None:
    if sidecar:
        candidate = _maybe_path(sidecar)
        return candidate if candidate.is_absolute() else (Path.cwd() / candidate)
    candidates = [
        root / "worldepisode.manifest.json",
        root / "worldepisode.json",
        root / "worldepisode.sidecar.json",
        root.with_suffix(".worldepisode.json") if root.suffix else root / "worldepisode.manifest.json",
        root.parent / "worldepisode.manifest.json",
        root.parent / "worldepisode.sidecar.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _validate_sidecar(sidecar_path: Path) -> tuple[list[Diagnostic], dict[str, Any]]:
    if not sidecar_path.exists():
        return [
            _diag(
                "PREFLIGHT.001",
                str(sidecar_path),
                "Declared WorldEpisode sidecar does not exist.",
                "error",
            )
        ], {"sidecar": str(sidecar_path), "sidecar_status": "missing"}

    payload = load_json(sidecar_path)
    kind = _kind_from_json(payload) if isinstance(payload, dict) else "json"
    if kind == "worldepisode":
        diagnostics = validate_worldepisode(payload)
        status = "valid" if not diagnostics else "invalid"
    elif kind == "worldepisode-dataset":
        diagnostics = validate_dataset_manifest(payload)
        status = "valid" if not diagnostics else "invalid"
    else:
        diagnostics = [
            _diag(
                "PREFLIGHT.002",
                str(sidecar_path),
                "Sidecar is not a full WorldEpisode episode or dataset manifest.",
                "warning",
                "Use a schema_version worldepisode-0.1 or worldepisode-dataset-0.1 manifest for blocking preflight.",
            )
        ]
        status = "partial"
    return diagnostics, {"sidecar": str(sidecar_path), "sidecar_kind": kind, "sidecar_status": status}


def _validate_json_target(path: Path, fail_on: str) -> PreflightReport:
    try:
        payload = load_json(path)
    except json.JSONDecodeError as exc:
        return PreflightReport(
            str(path),
            "json",
            [_diag("PREFLIGHT.003", str(path), f"Invalid JSON: {exc}", "error")],
            fail_on=fail_on,
        )
    kind = _kind_from_json(payload) if isinstance(payload, dict) else "json"
    if kind == "worldepisode":
        diagnostics = validate_worldepisode(payload)
    elif kind == "worldepisode-dataset":
        diagnostics = validate_dataset_manifest(payload)
    else:
        diagnostics = [
            _diag(
                "PREFLIGHT.004",
                str(path),
                "JSON file is not a WorldEpisode episode or dataset manifest.",
                "error",
            )
        ]
    return PreflightReport(str(path), kind, diagnostics, {"document_kind": kind}, fail_on)


def _resolve_huggingface_dataset(ref: str) -> Path | None:
    if ref.startswith("hf://"):
        repo_id = ref.removeprefix("hf://").split("@", 1)[0]
    elif "/" in ref and "://" not in ref:
        repo_id = ref
    else:
        return None
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "huggingface-hub is required for remote LeRobot preflight; install `worldepisode[lerobot]`."
        ) from exc
    cache_dir = Path(tempfile.gettempdir()) / "worldepisode-preflight-hf"
    return Path(
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            allow_patterns=["meta/**", "worldepisode*.json", "**/worldepisode*.json"],
            local_dir=cache_dir / repo_id.replace("/", "__"),
        )
    )


def _lerobot_native_diagnostics(root: Path, sidecar_found: bool) -> tuple[list[Diagnostic], dict[str, Any]]:
    diagnostics: list[Diagnostic] = []
    info_path = root / "meta" / "info.json"
    data_files = sorted((root / "data").glob("**/*.parquet")) if (root / "data").exists() else []
    video_files = sorted((root / "videos").glob("**/*.mp4")) if (root / "videos").exists() else []
    features: dict[str, Any] = {}

    if not info_path.exists():
        diagnostics.append(
            _diag("LEROBOT.001", "/meta/info.json", "LeRobot v3 metadata file is missing.", "error")
        )
    else:
        info = load_json(info_path)
        features = info.get("features", {}) if isinstance(info, dict) else {}
        if info.get("codebase_version") and not str(info.get("codebase_version")).startswith("v3"):
            diagnostics.append(
                _diag(
                    "LEROBOT.002",
                    "/meta/info.json/codebase_version",
                    f"Expected LeRobot v3 metadata, found {info.get('codebase_version')!r}.",
                    "warning",
                )
            )

    if not data_files:
        diagnostics.append(_diag("LEROBOT.003", "/data", "No LeRobot Parquet data shards found.", "error"))

    if "timestamp" not in features:
        diagnostics.append(
            _diag("TIME.001", "/meta/info.json/features", "Native LeRobot metadata does not expose a timestamp feature.", "error")
        )
    if "action" not in features:
        diagnostics.append(
            _diag("ACTION.001", "/meta/info.json/features", "Native LeRobot metadata does not expose an action feature.", "error")
        )
    else:
        action = features.get("action", {})
        if not action.get("names"):
            diagnostics.append(
                _diag(
                    "ACTION.001",
                    "/meta/info.json/features/action/names",
                    "Action tensor lacks component names.",
                    "warning",
                )
            )

    video_features = [name for name, value in features.items() if isinstance(value, dict) and value.get("dtype") == "video"]
    if video_features and not video_files:
        diagnostics.append(
            _diag(
                "LEROBOT.004",
                "/videos",
                "LeRobot metadata declares video features, but no local MP4 shards were found.",
                "warning",
                "This can be expected for metadata-only preflight; include videos for full replay checks.",
            )
        )

    if not sidecar_found:
        native_gaps = [
            ("WORLD.001", "/world_revision", "No immutable, content-addressed world revision is bound to this native LeRobot dataset."),
            ("ENTITY.001", "/entities", "No persistent entity identity graph is available across observations, assets, and annotations."),
            ("REP.001", "/entities/*/representations", "No representation-role graph declares appearance, collision, semantic, or learned roles."),
            ("FRAME.001", "/frame_graph", "Native LeRobot metadata does not provide a complete frame graph with explicit transform directions."),
            ("FRAME.002", "/frame_graph/transforms", "Native LeRobot metadata does not provide transform validity intervals."),
            ("TIME.002", "/clock_graph/mappings", "Native LeRobot metadata does not provide cross-clock drift/error mappings."),
            ("ACTION.001", "/action_space/channels", "Action units, reference frames, and absolute/delta/velocity semantics are not normative."),
            ("ACTION.002", "/action_space/channels", "Command-time versus effective-time semantics and latency model are absent."),
            ("SPLIT.001", "/splits", "No world-lineage-disjoint split manifest is attached."),
            ("CONVERT.001", "/conversion_report", "No machine-readable conversion-loss report is attached."),
        ]
        for requirement, location, message in native_gaps:
            diagnostics.append(
                _diag(
                    requirement,
                    location,
                    message,
                    "warning",
                    "Attach a WorldEpisode manifest/sidecar before treating this dataset as replay-safe.",
                )
            )

    summary = {
        "info_json": info_path.exists(),
        "data_parquet_files": len(data_files),
        "video_mp4_files": len(video_files),
        "feature_count": len(features),
        "video_feature_count": len(video_features),
        "worldepisode_sidecar_found": sidecar_found,
    }
    return diagnostics, summary


def preflight_lerobot(
    target: str | Path,
    *,
    sidecar: str | Path | None = None,
    fail_on: str = DEFAULT_FAIL_ON,
) -> PreflightReport:
    root = _maybe_path(target)
    if not root.exists():
        try:
            resolved = _resolve_huggingface_dataset(str(target))
        except RuntimeError as exc:
            return PreflightReport(
                str(target),
                "lerobot",
                [_diag("PREFLIGHT.005", str(target), str(exc), "error")],
                fail_on=fail_on,
            )
        if resolved is None:
            return PreflightReport(
                str(target),
                "lerobot",
                [_diag("PREFLIGHT.006", str(target), "LeRobot target path does not exist.", "error")],
                fail_on=fail_on,
            )
        root = resolved

    sidecar_path = _find_sidecar(root, sidecar)
    diagnostics: list[Diagnostic] = []
    sidecar_summary: dict[str, Any] = {"sidecar_status": "missing"}
    if sidecar_path:
        sidecar_diagnostics, sidecar_summary = _validate_sidecar(sidecar_path)
        diagnostics.extend(sidecar_diagnostics)

    native_diagnostics, summary = _lerobot_native_diagnostics(root, sidecar_found=sidecar_path is not None)
    diagnostics.extend(native_diagnostics)
    summary.update(sidecar_summary)
    return PreflightReport(str(target), "lerobot", diagnostics, summary, fail_on)


def preflight_rerun(
    target: str | Path,
    *,
    sidecar: str | Path | None = None,
    fail_on: str = DEFAULT_FAIL_ON,
) -> PreflightReport:
    path = _maybe_path(target)
    diagnostics: list[Diagnostic] = []
    if not path.exists():
        diagnostics.append(_diag("RERUN.001", str(path), "Rerun recording path does not exist.", "error"))
    elif path.suffix != ".rrd":
        diagnostics.append(_diag("RERUN.002", str(path), "Expected a .rrd Rerun recording.", "error"))

    sidecar_path = _find_sidecar(path, sidecar)
    sidecar_summary: dict[str, Any] = {"sidecar_status": "missing"}
    if sidecar_path:
        sidecar_diagnostics, sidecar_summary = _validate_sidecar(sidecar_path)
        diagnostics.extend(sidecar_diagnostics)
    else:
        for requirement, location, message in [
            ("WORLD.001", "/world_revision", "Rerun recordings do not by themselves declare immutable world revisions."),
            ("ACTION.001", "/action_space/channels", "Rerun streams do not by themselves make action units and frames normative."),
            ("ACTION.002", "/action_space/channels", "Rerun streams do not by themselves declare command/effective timing and latency."),
            ("ENTITY.001", "/entities", "Persistent cross-representation entity identity requires a WorldEpisode sidecar."),
            ("REP.001", "/entities/*/representations", "Representation roles require a WorldEpisode sidecar."),
            ("CONVERT.001", "/conversion_report", "Replay/conversion loss must be reported outside the .rrd stream."),
        ]:
            diagnostics.append(
                _diag(requirement, location, message, "warning", "Attach a WorldEpisode manifest beside the .rrd file.")
            )

    summary = {
        "rrd_path_exists": path.exists(),
        "worldepisode_sidecar_found": sidecar_path is not None,
        **sidecar_summary,
    }
    return PreflightReport(str(target), "rerun", diagnostics, summary, fail_on)


def preflight(
    target: str | Path,
    *,
    kind: str = "auto",
    sidecar: str | Path | None = None,
    fail_on: str = DEFAULT_FAIL_ON,
) -> PreflightReport:
    path = _maybe_path(target)
    if kind == "lerobot":
        return preflight_lerobot(target, sidecar=sidecar, fail_on=fail_on)
    if kind == "rerun":
        return preflight_rerun(target, sidecar=sidecar, fail_on=fail_on)
    if kind not in {"auto", "worldepisode", "worldepisode-dataset"}:
        return PreflightReport(
            str(target),
            kind,
            [_diag("PREFLIGHT.007", str(target), f"Unsupported preflight kind {kind!r}.", "error")],
            fail_on=fail_on,
        )

    if path.exists() and path.is_file() and path.suffix == ".rrd":
        return preflight_rerun(path, sidecar=sidecar, fail_on=fail_on)
    if path.exists() and path.is_file() and path.suffix == ".json":
        return _validate_json_target(path, fail_on)
    if path.exists() and path.is_dir():
        if (path / "meta" / "info.json").exists():
            return preflight_lerobot(path, sidecar=sidecar, fail_on=fail_on)
        sidecar_path = _find_sidecar(path, sidecar)
        if sidecar_path:
            return _validate_json_target(sidecar_path, fail_on)
        return PreflightReport(
            str(path),
            "directory",
            [_diag("PREFLIGHT.008", str(path), "Directory is not a recognized WorldEpisode, LeRobot, or Rerun artifact.", "error")],
            fail_on=fail_on,
        )
    if kind == "auto" and not path.exists():
        if str(target).startswith("hf://") or ("/" in str(target) and "://" not in str(target)):
            return preflight_lerobot(target, sidecar=sidecar, fail_on=fail_on)
    return PreflightReport(
        str(target),
        kind,
        [_diag("PREFLIGHT.009", str(target), "Target does not exist.", "error")],
        fail_on=fail_on,
    )
