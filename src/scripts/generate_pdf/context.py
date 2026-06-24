from __future__ import annotations

"""
Context loader for the modular CBR / Suricata EVE PDF report.

Policy:
- Do not read raw EVE JSONL.
- Do not read train.csv/test.csv.
- Read only central metrics JSON files produced by pipeline.py:
    outputs_test/metrics_json/<app>/phaseXX_summary.json

The PDF renderer is intentionally dumb: it should consume standardized
per-phase summaries, not discover scattered phase output directories.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional
import json
import math


PHASE_TITLES: dict[int, str] = {
    1: "Initial Application Summary",
    2: "Pre-split Application Validation",
    3: "Probing Analysis",
    4: "Label Refinement",
    5: "Feature Engineering Manifest",
    6: "Computed Feature Rules",
    7: "Cleaning and Leakage Policy",
    8: "Dataset Export and Train/Test Split",
    9: "Summary-driven Visualization",
    10: "Correlation and Leakage Analysis",
    11: "Modeling Readiness / Split Audit",
    12: "Feature Selection",
    13: "Model Training and Holdout Evaluation",
    14: "Final Evaluation Summary",
}

DEFAULT_APPS = ("http", "tls", "dns", "ssh")


# ---------------------------------------------------------------------------
# Generic safe helpers
# ---------------------------------------------------------------------------

def load_json(path: Path | str | None, default: Any = None) -> Any:
    if default is None:
        default = {}
    if path is None:
        return default
    try:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return default
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, float) and not math.isfinite(value):
            return default
        return int(float(value))
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        out = float(value)
        return out if math.isfinite(out) else default
    except Exception:
        return default


def fmt_int(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return f"{safe_int(value):,}"


def fmt_float(value: Any, ndigits: int = 4) -> str:
    if value is None or value == "":
        return "-"
    return f"{safe_float(value):.{int(ndigits)}f}"


def fmt_pct(value: Any, ndigits: int = 2) -> str:
    if value is None or value == "":
        return "-"
    return f"{safe_float(value):.{int(ndigits)}f}%"


def fmt_seconds(value: Any) -> str:
    sec = safe_float(value, 0.0)
    if sec <= 0:
        return "-"
    if sec < 60:
        return f"{sec:.2f}s"
    return f"{sec / 60.0:.2f} min"


def fmt_bytes(value: Any) -> str:
    n = safe_float(value, 0.0)
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    idx = 0
    while n >= 1024.0 and idx < len(units) - 1:
        n /= 1024.0
        idx += 1
    if idx == 0:
        return f"{int(n):,} {units[idx]}"
    return f"{n:.2f} {units[idx]}"


def shorten(value: Any, max_len: int = 120) -> str:
    s = str(value if value is not None else "-")
    s = s.replace("\n", " ").replace("\r", " ").replace("\\", "/")
    s = " ".join(s.split())
    if len(s) <= int(max_len):
        return s
    return s[: max(0, int(max_len) - 3)] + "..."


def counts_text(value: Any, *, max_items: int = 8) -> str:
    if not isinstance(value, dict) or not value:
        return "-"
    items: list[str] = []
    for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))[: int(max_items)]:
        items.append(f"{k}: {fmt_int(v)}")
    if len(value) > int(max_items):
        items.append("...")
    return ", ".join(items)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def deep_get(data: Any, *keys: str, default: Any = None) -> Any:
    cur = data
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def normalize_app(app: str) -> str:
    return str(app).strip().lower()


def normalize_phase_key(phase: int | str) -> str:
    if isinstance(phase, str) and phase.lower().startswith("phase"):
        digits = "".join(ch for ch in phase if ch.isdigit())
        phase_num = safe_int(digits, 0)
    else:
        phase_num = safe_int(phase, 0)
    return f"phase{phase_num:02d}"


def phase_num_from_key(phase: int | str) -> int:
    if isinstance(phase, str) and phase.lower().startswith("phase"):
        digits = "".join(ch for ch in phase if ch.isdigit())
        return safe_int(digits, 0)
    return safe_int(phase, 0)


# ---------------------------------------------------------------------------
# Context objects
# ---------------------------------------------------------------------------

@dataclass
class PhaseMetrics:
    app: str
    phase: int
    path: Path
    exists: bool
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        return str(self.payload.get("status") or ("missing" if not self.exists else "unknown"))

    @property
    def phase_key(self) -> str:
        return normalize_phase_key(self.phase)

    @property
    def summary(self) -> dict[str, Any]:
        # Central metrics may be stored either as a wrapper {"summary": {...}}
        # or directly as the phase summary itself. Support both formats.
        value = self.payload.get("summary")
        if isinstance(value, dict):
            return value
        return self.payload if isinstance(self.payload, dict) else {}

    @property
    def warnings(self) -> list[str]:
        raw = self.payload.get("warnings")
        if raw is None:
            return []
        if isinstance(raw, list):
            return [str(x) for x in raw if str(x).strip()]
        return [str(raw)] if str(raw).strip() else []

    def get(self, key: str, default: Any = None) -> Any:
        return self.payload.get(key, default)


@dataclass
class PDFContext:
    artifacts_dir: Path
    metrics_dir: Path
    reports_dir: Path
    run_summary_path: Path
    artifact_manifest_path: Path
    pipeline_summary_path: Path
    run_summary: dict[str, Any]
    artifact_manifest: dict[str, Any]
    pipeline_summary: dict[str, Any]
    selected_apps: list[str]
    phases: dict[str, dict[int, PhaseMetrics]]

    def phase_title(self, phase: int) -> str:
        return PHASE_TITLES.get(int(phase), f"Phase {int(phase)}")

    def app_phase(self, app: str, phase: int) -> PhaseMetrics:
        app_key = normalize_app(app)
        phase_num = int(phase)
        path = self.metrics_dir / app_key / f"phase{phase_num:02d}_summary.json"
        return self.phases.get(app_key, {}).get(
            phase_num,
            PhaseMetrics(app=app_key, phase=phase_num, path=path, exists=False),
        )

    def all_phase(self, phase: int) -> list[PhaseMetrics]:
        return [self.app_phase(app, int(phase)) for app in self.selected_apps]

    def has_phase_data(self, phase: int) -> bool:
        return any(item.exists for item in self.all_phase(int(phase)))

    def warnings_for_phase(self, phase: int) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for item in self.all_phase(int(phase)):
            for warning in item.warnings:
                out.append((item.app, warning))
        return out


# ---------------------------------------------------------------------------
# Context loading
# ---------------------------------------------------------------------------

def _resolve_artifacts_dir(artifacts_dir: Path | str | None, metrics_dir: Path | str | None) -> Path:
    if artifacts_dir is not None:
        return Path(artifacts_dir).resolve()
    if metrics_dir is not None:
        m = Path(metrics_dir).resolve()
        return m.parent if m.name.lower() == "metrics_json" else m
    return Path.cwd().resolve()


def _resolve_metrics_dir(artifacts_dir: Path, metrics_dir: Path | str | None) -> Path:
    if metrics_dir is not None:
        return Path(metrics_dir).resolve()
    if artifacts_dir.name.lower() == "metrics_json":
        return artifacts_dir
    return artifacts_dir / "metrics_json"


def _apps_from_sources(metrics_dir: Path, run_summary: dict[str, Any], artifact_manifest: dict[str, Any], pipeline_summary: dict[str, Any]) -> list[str]:
    candidates: list[str] = []

    for source in (
        run_summary.get("selected_apps"),
        pipeline_summary.get("selected_apps"),
        deep_get(pipeline_summary, "config", "selected_apps"),
    ):
        for app in as_list(source):
            app_key = normalize_app(str(app))
            if app_key and app_key not in candidates:
                candidates.append(app_key)

    manifest_apps = artifact_manifest.get("apps")
    if isinstance(manifest_apps, dict):
        for app in manifest_apps:
            app_key = normalize_app(str(app))
            if app_key and app_key not in candidates:
                candidates.append(app_key)

    if metrics_dir.exists():
        for p in sorted(metrics_dir.iterdir()):
            if p.is_dir() and not p.name.startswith("_"):
                app_key = normalize_app(p.name)
                if app_key and app_key not in candidates:
                    candidates.append(app_key)

    return [app for app in candidates if app] or []


def _load_phase_metrics(metrics_dir: Path, apps: Iterable[str]) -> dict[str, dict[int, PhaseMetrics]]:
    phases: dict[str, dict[int, PhaseMetrics]] = {}
    for app in apps:
        app_key = normalize_app(app)
        phases[app_key] = {}
        for phase_num in range(1, 15):
            path = metrics_dir / app_key / f"phase{phase_num:02d}_summary.json"
            payload = load_json(path, default={})
            exists = bool(path.exists() and path.is_file())
            if isinstance(payload, dict):
                phases[app_key][phase_num] = PhaseMetrics(
                    app=app_key,
                    phase=phase_num,
                    path=path,
                    exists=exists,
                    payload=payload,
                )
            else:
                phases[app_key][phase_num] = PhaseMetrics(
                    app=app_key,
                    phase=phase_num,
                    path=path,
                    exists=exists,
                    payload={},
                )
    return phases


def build_context(
    *,
    artifacts_dir: Path | str | None = None,
    metrics_dir: Path | str | None = None,
    output_pdf: Path | str | None = None,
) -> PDFContext:
    artifacts = _resolve_artifacts_dir(artifacts_dir, metrics_dir)
    metrics = _resolve_metrics_dir(artifacts, metrics_dir)
    reports = artifacts / "reports"

    run_summary_path = metrics / "run_summary.json"
    artifact_manifest_path = metrics / "artifact_manifest.json"
    pipeline_summary_path = artifacts / "_run_logs" / "pipeline_summary.json"

    run_summary = load_json(run_summary_path, default={})
    artifact_manifest = load_json(artifact_manifest_path, default={})
    pipeline_summary = load_json(pipeline_summary_path, default={})

    selected_apps = _apps_from_sources(metrics, run_summary, artifact_manifest, pipeline_summary)
    phases = _load_phase_metrics(metrics, selected_apps)

    return PDFContext(
        artifacts_dir=artifacts,
        metrics_dir=metrics,
        reports_dir=reports,
        run_summary_path=run_summary_path,
        artifact_manifest_path=artifact_manifest_path,
        pipeline_summary_path=pipeline_summary_path,
        run_summary=run_summary,
        artifact_manifest=artifact_manifest,
        pipeline_summary=pipeline_summary,
        selected_apps=selected_apps,
        phases=phases,
    )


def default_output_pdf(ctx: PDFContext) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return ctx.reports_dir / f"pipeline_report_modular_{stamp}.pdf"
