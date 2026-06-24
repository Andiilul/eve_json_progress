from __future__ import annotations

"""
Phase 4 - Label Refinement Policy Builder

Purpose:
- Use Phase 3 aggregate probing evidence.
- Build conservative refinement keys/policy.
- Do NOT read the full app JSONL.
- Do NOT write a row-level labeled dataset.
- Do NOT perform IP-only relabeling.

Phase 4 does not directly finalize every row. Instead, it produces a policy and
key files that Phase 8 will apply while exporting the final feature-ready
dataset.

Input:
    outputs/<app>/phase3/phase3_<app>_probe_features.jsonl
    outputs/<app>/phase3/phase3_<app>_alert_ip_index.jsonl
    outputs/<app>/phase3/phase3_<app>_summary.json
    outputs/<app>/phase1/summary.json optional

Output:
    phase4_<app>_label_policy.json
    phase4_<app>_suspicious_keys.jsonl
    phase4_<app>_refined_label_summary.json
    phase4_<app>_refinement_audit.csv

Also writes generic aliases:
    label_policy.json
    suspicious_keys.jsonl
    refined_label_summary.json
    refinement_audit.csv
    summary.json
"""

import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from ..io_utils import (
    dumps_json,
    file_size_bytes,
    loads_json_line,
    now_iso,
    open_maybe_gzip,
    read_json,
    write_json,
)


VALID_APPS = {"http", "tls", "dns", "ssh"}


# ============================================================
# Helpers
# ============================================================

def _normalize_app(app: str) -> str:
    app = str(app).strip().lower()
    if app not in VALID_APPS:
        raise ValueError(f"Invalid app={app!r}. Expected one of {sorted(VALID_APPS)}")
    return app


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _parse_window(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    try:
        text = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _window_key(value: Any) -> str:
    dt = _parse_window(value)
    if dt is None:
        return str(value or "").strip()
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _minutes_between(a: datetime, b: datetime) -> float:
    return abs((a - b).total_seconds()) / 60.0


def _jsonl_iter(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return

    with open_maybe_gzip(path, "rb") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = loads_json_line(line)
                if isinstance(obj, dict):
                    yield obj
            except Exception:
                continue


def _write_jsonl_record(handle, record: dict[str, Any]) -> None:
    handle.write(dumps_json(record, indent=False))
    handle.write(b"\n")


def _copy_text_file(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())


def _phase_dir(app_output_dir: Path, name: str) -> Path:
    return Path(app_output_dir) / name


def _sibling_phase_dir(phase_dir: Path, sibling: str) -> Path:
    return Path(phase_dir).parent / sibling


def _find_first_existing(candidates: Iterable[Path]) -> Optional[Path]:
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None


def _phase3_paths(app: str, phase_dir: Path) -> dict[str, Optional[Path]]:
    phase3_dir = _sibling_phase_dir(phase_dir, "phase3")

    return {
        "probe_features": _find_first_existing([
            phase3_dir / f"phase3_{app}_probe_features.jsonl",
            phase3_dir / "probe_features.jsonl",
        ]),
        "alert_ip_index": _find_first_existing([
            phase3_dir / f"phase3_{app}_alert_ip_index.jsonl",
            phase3_dir / "alert_ip_index.jsonl",
        ]),
        "suspicious_windows": _find_first_existing([
            phase3_dir / f"phase3_{app}_suspicious_windows.jsonl",
            phase3_dir / "suspicious_windows.jsonl",
        ]),
        "summary": _find_first_existing([
            phase3_dir / f"phase3_{app}_summary.json",
            phase3_dir / "summary.json",
        ]),
    }


def _phase1_summary_path(phase_dir: Path) -> Optional[Path]:
    phase1 = _sibling_phase_dir(phase_dir, "phase1") / "summary.json"
    return phase1 if phase1.exists() else None


def _load_phase3_summary(path: Optional[Path]) -> dict[str, Any]:
    if path is None:
        return {}
    data = read_json(path, default={}, required=False)
    return data if isinstance(data, dict) else {}


def _load_phase1_summary(path: Optional[Path]) -> dict[str, Any]:
    if path is None:
        return {}
    data = read_json(path, default={}, required=False)
    return data if isinstance(data, dict) else {}


def _percentile_key(percentile: float) -> str:
    # Phase 3 summaries usually store p90, p95, p99. This helper keeps
    # Phase 4 aligned with the configured percentile instead of always
    # reading p90 for same-window refinement.
    pct = int(round(float(percentile)))
    return f"p{pct}"


def _threshold_from_stats(stats: dict[str, Any], percentile: float, fallback: float = 0.0) -> float:
    if not isinstance(stats, dict):
        return float(fallback)

    key = _percentile_key(percentile)
    if key in stats:
        return _safe_float(stats.get(key), fallback)

    # Conservative fallback: use the nearest higher stored percentile when the
    # exact configured percentile is not present.
    available: list[tuple[float, float]] = []
    for k, v in stats.items():
        text = str(k).strip().lower()
        if not text.startswith("p"):
            continue
        try:
            available.append((float(text[1:]), _safe_float(v, fallback)))
        except Exception:
            continue
    if not available:
        return float(fallback)

    available.sort(key=lambda x: x[0])
    for pct, value in available:
        if pct >= float(percentile):
            return float(value)
    return float(available[-1][1])


def _get_thresholds_from_phase3(phase3_summary: dict[str, Any], cfg: Any) -> dict[str, float]:
    probing_cfg = getattr(cfg, "probing", None)

    same_percentile = float(getattr(probing_cfg, "same_window_probe_percentile", 90.0) or 90.0)
    near_percentile = float(getattr(probing_cfg, "near_window_probe_percentile", 95.0) or 95.0)
    extreme_percentile = float(getattr(probing_cfg, "extreme_probe_percentile", 99.0) or 99.0)

    stats = phase3_summary.get("probe_score_stats", {})
    no_alert = stats.get("probe_score_no_alert", {}) if isinstance(stats, dict) else {}

    # Use thresholds that match the configured percentiles. Previously same-window
    # always read p90, which kept the policy too permissive even when config was
    # changed to p95.
    same = _threshold_from_stats(no_alert, same_percentile, _safe_float(no_alert.get("p90"), 0.0))
    near = _threshold_from_stats(no_alert, near_percentile, same)
    extreme = _threshold_from_stats(no_alert, extreme_percentile, near)

    return {
        "same_window_percentile": same_percentile,
        "near_window_percentile": near_percentile,
        "extreme_percentile": extreme_percentile,
        "same_window_score_threshold": same,
        "near_window_score_threshold": near,
        "extreme_score_threshold": extreme,
    }


def _load_alert_windows(alert_ip_index_path: Optional[Path]) -> tuple[set[tuple[str, str]], dict[str, list[datetime]], int]:
    """
    Returns:
        alert_key_set: {(src_ip, window_start)}
        alert_windows_by_src_ip: {src_ip: [datetime, ...]}
        count
    """
    alert_key_set: set[tuple[str, str]] = set()
    alert_windows_by_src_ip: dict[str, list[datetime]] = defaultdict(list)

    if alert_ip_index_path is None or not alert_ip_index_path.exists():
        return alert_key_set, alert_windows_by_src_ip, 0

    count = 0
    for rec in _jsonl_iter(alert_ip_index_path):
        src_ip = str(rec.get("src_ip", "")).strip()
        win_key = _window_key(rec.get("window_start"))
        win_dt = _parse_window(win_key)

        if not src_ip or not win_key:
            continue

        alert_key_set.add((src_ip, win_key))
        if win_dt is not None:
            alert_windows_by_src_ip[src_ip].append(win_dt)
        count += 1

    for src_ip in list(alert_windows_by_src_ip):
        alert_windows_by_src_ip[src_ip] = sorted(alert_windows_by_src_ip[src_ip])

    return alert_key_set, alert_windows_by_src_ip, count


def _nearest_alert_window(
    *,
    src_ip: str,
    window_start: str,
    alert_windows_by_src_ip: dict[str, list[datetime]],
    near_window_radius: int,
    window_minutes: int,
) -> tuple[bool, Optional[str], Optional[float]]:
    win_dt = _parse_window(window_start)
    if win_dt is None:
        return False, None, None

    max_minutes = max(0, int(near_window_radius)) * max(1, int(window_minutes))
    if max_minutes <= 0:
        return False, None, None

    best_dt: Optional[datetime] = None
    best_minutes: Optional[float] = None

    for alert_dt in alert_windows_by_src_ip.get(src_ip, []):
        diff = _minutes_between(win_dt, alert_dt)

        # near window excludes same window; same-window is handled separately.
        if diff <= 0:
            continue

        if diff <= max_minutes:
            if best_minutes is None or diff < best_minutes:
                best_minutes = diff
                best_dt = alert_dt

    if best_dt is None:
        return False, None, None

    return True, best_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), best_minutes


def _make_policy(
    *,
    app: str,
    thresholds: dict[str, float],
    window_minutes: int,
    near_window_radius: int,
    max_benign_conversion_pct: float,
    allow_same_window_conversion: bool,
    allow_near_window_conversion: bool,
    allow_extreme_probe_conversion: bool,
    min_valid_alert_count_for_refinement: int,
    require_fanout_for_refinement: bool,
    max_conversion_per_key: int,
) -> dict[str, Any]:
    return {
        "phase": 4,
        "title": "Label Refinement Policy",
        "app": app,
        "created_at": now_iso(),

        "prohibited_rule": (
            "Do not relabel all traffic from a source IP only because the source IP was once malicious. "
            "IP-only relabeling is disabled because it can cause label explosion."
        ),

        "label_columns": {
            "Target_alert": "Initial label based on event_type=alert OR valid Suricata alert evidence.",
            "Target_refined": "Final label after conservative probing-based refinement.",
            "suspicious_by_probe": "Suspicious probing marker; not always malicious.",
            "label_source": "Source of label decision.",
            "refinement_reason": "Technical reason used by the policy.",
        },

        "policy_order": [
            {
                "rule": "base_alert_positive",
                "condition": "row has event_type=alert OR valid Suricata alert evidence",
                "Target_refined": 1,
                "suspicious_by_probe": 0,
                "label_source": "alert_confirmed",
            },
            {
                "rule": "probe_refined_same_window",
                "condition": (
                    "no-alert row + same src_ip + same 5-minute alert window + "
                    "alert_support_count >= min_valid_alert_count_for_refinement + "
                    "probe_score_no_alert >= same_window_score_threshold + fanout_high + "
                    "known conversion size + per-key conversion cap"
                ),
                "Target_refined": 1 if allow_same_window_conversion else 0,
                "suspicious_by_probe": 1,
                "label_source": "probe_refined_same_window" if allow_same_window_conversion else "suspicious_probe_only",
            },
            {
                "rule": "probe_refined_near_alert_window",
                "condition": (
                    "near alert window evidence is retained for audit, but target conversion is disabled "
                    "by default because it is weaker than same-window confirmation"
                ),
                "Target_refined": 1 if allow_near_window_conversion else 0,
                "suspicious_by_probe": 1,
                "label_source": "probe_refined_near_alert_window" if allow_near_window_conversion else "suspicious_probe_only",
            },
            {
                "rule": "suspicious_probe_only",
                "condition": (
                    "no-alert row + extreme probing without strong alert association. "
                    "This remains Target_refined=0 but suspicious_by_probe=1."
                ),
                "Target_refined": 0,
                "suspicious_by_probe": 1,
                "label_source": "suspicious_probe_only",
            },
            {
                "rule": "benign_no_evidence",
                "condition": "no base alert evidence and no conservative probing association",
                "Target_refined": 0,
                "suspicious_by_probe": 0,
                "label_source": "benign_no_evidence",
            },
        ],

        "thresholds": {
            **thresholds,
            "window_minutes": int(window_minutes),
            "near_window_radius": int(near_window_radius),
            "max_benign_conversion_pct": float(max_benign_conversion_pct),
            "allow_same_window_conversion": bool(allow_same_window_conversion),
            "allow_near_window_conversion": bool(allow_near_window_conversion),
            "allow_extreme_probe_conversion": bool(allow_extreme_probe_conversion),
            "min_valid_alert_count_for_refinement": int(min_valid_alert_count_for_refinement),
            "require_fanout_for_refinement": bool(require_fanout_for_refinement),
            "max_conversion_per_key": int(max_conversion_per_key),
        },

        "phase8_application_note": (
            "Phase 8 applies this policy while exporting the final dataset. "
            "Rows with event_type=alert OR valid alerts become Target_refined=1 directly. "
            "Only no-base-alert rows may use keys in suspicious_keys.jsonl. "
            "Phase 4 also estimates no-alert row conversion from window aggregates and caps "
            "target-changing keys using max_benign_conversion_pct to prevent label explosion."
        ),
    }


def _audit_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "app": record.get("app"),
        "src_ip": record.get("src_ip"),
        "window_start": record.get("window_start"),
        "label_action": record.get("label_action"),
        "label_source": record.get("label_source"),
        "Target_refined_for_no_alert": record.get("Target_refined_for_no_alert"),
        "suspicious_by_probe": record.get("suspicious_by_probe"),
        "probe_score_no_alert": record.get("probe_score_no_alert"),
        "probe_score_with_alert": record.get("probe_score_with_alert"),
        "probe_level": record.get("probe_level"),
        "fanout_high": record.get("fanout_high"),
        "event_count_window": record.get("event_count_window"),
        "unique_dest_ip_window": record.get("unique_dest_ip_window"),
        "unique_dest_port_window": record.get("unique_dest_port_window"),
        "event_type_alert_count_window": record.get("event_type_alert_count_window"),
        "valid_alert_count_window": record.get("valid_alert_count_window"),
        "base_alert_positive_count_window": record.get("base_alert_positive_count_window"),
        "alert_support_count_window": record.get("alert_support_count_window"),
        "alert_count_window": record.get("alert_count_window"),
        "no_alert_count_window": record.get("no_alert_count_window"),
        "estimated_conversion_rows": record.get("estimated_conversion_rows"),
        "original_label_action": record.get("original_label_action"),
        "conversion_guard_demoted": record.get("conversion_guard_demoted"),
        "matched_alert_window": record.get("matched_alert_window"),
        "minutes_to_alert_window": record.get("minutes_to_alert_window"),
        "refinement_reason": record.get("refinement_reason"),
    }


# ============================================================
# Runner
# ============================================================

def run_phase4(
    *,
    cfg: Any,
    app: str,
    phase_dir: Path,
    app_output_dir: Optional[Path] = None,
    **_: Any,
) -> dict[str, Any]:
    app = _normalize_app(app)
    phase_dir = Path(phase_dir)
    phase_dir.mkdir(parents=True, exist_ok=True)

    probing_cfg = getattr(cfg, "probing", None)
    window_minutes = int(getattr(probing_cfg, "window_minutes", 5) or 5)
    near_window_radius = int(getattr(probing_cfg, "near_window_radius", 1) or 1)
    max_benign_conversion_pct = float(getattr(probing_cfg, "max_benign_conversion_pct", 5.0) or 5.0)
    stop_if_conversion_exceeds_limit = bool(
        getattr(probing_cfg, "stop_if_conversion_exceeds_limit", True)
    )
    allow_same_window_conversion = bool(getattr(probing_cfg, "allow_same_window_conversion", True))
    allow_near_window_conversion = bool(getattr(probing_cfg, "allow_near_window_conversion", False))
    allow_extreme_probe_conversion = bool(
        getattr(probing_cfg, "allow_extreme_probe_conversion", getattr(probing_cfg, "extreme_probe_changes_target", False))
    )
    min_valid_alert_count_for_refinement = max(1, int(
        getattr(probing_cfg, "min_valid_alert_count_for_refinement", 2) or 2
    ))
    require_fanout_for_refinement = bool(getattr(probing_cfg, "require_fanout_for_refinement", True))
    max_conversion_per_key = max(0, int(getattr(probing_cfg, "max_conversion_per_key", 500) or 500))

    phase3 = _phase3_paths(app, phase_dir)
    phase3_summary = _load_phase3_summary(phase3.get("summary"))
    phase1_summary = _load_phase1_summary(_phase1_summary_path(phase_dir))

    thresholds = _get_thresholds_from_phase3(phase3_summary, cfg)

    prefix = f"phase4_{app}"
    label_policy_path = phase_dir / f"{prefix}_label_policy.json"
    suspicious_keys_path = phase_dir / f"{prefix}_suspicious_keys.jsonl"
    refined_summary_path = phase_dir / f"{prefix}_refined_label_summary.json"
    audit_path = phase_dir / f"{prefix}_refinement_audit.csv"
    manifest_path = phase_dir / "manifest.json"

    # Generic aliases expected by later phases.
    label_policy_alias = phase_dir / "label_policy.json"
    suspicious_keys_alias = phase_dir / "suspicious_keys.jsonl"
    refined_summary_alias = phase_dir / "refined_label_summary.json"
    audit_alias = phase_dir / "refinement_audit.csv"
    summary_alias = phase_dir / "summary.json"

    print("\n" + "=" * 72)
    print("Phase 4 - Label Refinement Policy Builder")
    print("=" * 72)
    print(f"Current Run : {app.upper()}")
    print(f"Reading     : {phase3.get('probe_features')}")
    print("Mode        : conservative keys/policy only")
    print("=" * 72)

    if phase3.get("probe_features") is None or not Path(phase3["probe_features"]).exists():
        summary = {
            "phase": 4,
            "title": "Label Refinement Policy Builder",
            "status": "completed_with_warning",
            "app": app,
            "current_run": app.upper(),
            "generated_at": now_iso(),
            "warning": "Phase 3 probe_features file was not found. No refinement keys were generated.",
            "phase3_files": {k: str(v) if v else None for k, v in phase3.items()},
        }
        policy = _make_policy(
            app=app,
            thresholds=thresholds,
            window_minutes=window_minutes,
            near_window_radius=near_window_radius,
            max_benign_conversion_pct=max_benign_conversion_pct,
            allow_same_window_conversion=allow_same_window_conversion,
            allow_near_window_conversion=allow_near_window_conversion,
            allow_extreme_probe_conversion=allow_extreme_probe_conversion,
            min_valid_alert_count_for_refinement=min_valid_alert_count_for_refinement,
            require_fanout_for_refinement=require_fanout_for_refinement,
            max_conversion_per_key=max_conversion_per_key,
        )
        write_json(policy, label_policy_path)
        write_json(policy, label_policy_alias)
        write_json(summary, refined_summary_path)
        write_json(summary, refined_summary_alias)
        write_json(summary, summary_alias)
        suspicious_keys_path.write_bytes(b"")
        suspicious_keys_alias.write_bytes(b"")
        audit_path.write_text("", encoding="utf-8")
        audit_alias.write_text("", encoding="utf-8")
        write_json({
            "phase": 4,
            "app": app,
            "created_at": now_iso(),
            "files": {
                "label_policy": str(label_policy_path),
                "suspicious_keys": str(suspicious_keys_path),
                "refined_label_summary": str(refined_summary_path),
                "refinement_audit": str(audit_path),
                "summary_alias": str(summary_alias),
            },
            "summary": {
                "status": summary.get("status"),
                "keys_written": 0,
                "warning": summary.get("warning"),
            },
        }, manifest_path)
        return summary

    alert_key_set, alert_windows_by_src_ip, alert_ip_windows = _load_alert_windows(phase3.get("alert_ip_index"))

    policy = _make_policy(
        app=app,
        thresholds=thresholds,
        window_minutes=window_minutes,
        near_window_radius=near_window_radius,
        max_benign_conversion_pct=max_benign_conversion_pct,
        allow_same_window_conversion=allow_same_window_conversion,
        allow_near_window_conversion=allow_near_window_conversion,
        allow_extreme_probe_conversion=allow_extreme_probe_conversion,
        min_valid_alert_count_for_refinement=min_valid_alert_count_for_refinement,
        require_fanout_for_refinement=require_fanout_for_refinement,
        max_conversion_per_key=max_conversion_per_key,
    )
    write_json(policy, label_policy_path)
    write_json(policy, label_policy_alias)

    target_change_candidates: list[dict[str, Any]] = []
    suspicious_only_candidates: list[dict[str, Any]] = []

    probe_windows_read = 0
    target_change_candidate_keys = 0
    same_window_candidate_keys = 0
    near_window_candidate_keys = 0
    suspicious_only_candidate_keys = 0
    near_window_evidence_only_keys = 0
    extreme_probe_target_candidate_keys = 0
    target_change_blocked_by_min_alert_count = 0
    target_change_blocked_by_unknown_size = 0
    target_change_blocked_by_per_key_cap = 0
    target_change_disabled_by_policy = 0

    total_no_alert_windows = 0
    total_no_alert_rows_in_windows = 0

    audit_fieldnames = [
        "app",
        "src_ip",
        "window_start",
        "label_action",
        "label_source",
        "Target_refined_for_no_alert",
        "suspicious_by_probe",
        "probe_score_no_alert",
        "probe_score_with_alert",
        "probe_level",
        "fanout_high",
        "event_count_window",
        "unique_dest_ip_window",
        "unique_dest_port_window",
        "event_type_alert_count_window",
        "valid_alert_count_window",
        "base_alert_positive_count_window",
        "alert_support_count_window",
        "alert_count_window",
        "no_alert_count_window",
        "estimated_conversion_rows",
        "original_label_action",
        "conversion_guard_demoted",
        "matched_alert_window",
        "minutes_to_alert_window",
        "refinement_reason",
    ]

    # Build candidates first, then enforce the conversion guard before writing keys.
    # The old streaming implementation could produce a small number of keys that
    # mapped to a very large number of no-alert rows in Phase 8, causing label explosion.
    for rec in _jsonl_iter(Path(phase3["probe_features"])):
        probe_windows_read += 1

        src_ip = str(rec.get("src_ip", "")).strip()
        win = _window_key(rec.get("window_start"))

        if not src_ip or not win:
            continue

        key = (src_ip, win)

        score_no_alert = _safe_float(rec.get("probe_score_no_alert"), 0.0)
        score_with_alert = _safe_float(rec.get("probe_score_with_alert"), 0.0)
        fanout_high = _safe_int(rec.get("fanout_high"), 0) == 1
        no_alert_count_window = _safe_int(rec.get("no_alert_count_window"), 0)
        if no_alert_count_window > 0:
            total_no_alert_windows += 1
            total_no_alert_rows_in_windows += no_alert_count_window

        same_alert_window = key in alert_key_set
        near_alert_window, matched_alert_window, minutes_to_alert = _nearest_alert_window(
            src_ip=src_ip,
            window_start=win,
            alert_windows_by_src_ip=alert_windows_by_src_ip,
            near_window_radius=near_window_radius,
            window_minutes=window_minutes,
        )

        label_action: Optional[str] = None
        target_for_no_alert = 0
        suspicious_by_probe = 0
        label_source = "benign_no_evidence"
        refinement_reason = "below_conservative_threshold"

        event_type_alert_count_window = _safe_int(rec.get("event_type_alert_count_window"), 0)
        valid_alert_count_window = _safe_int(rec.get("valid_alert_count_window"), 0)
        base_alert_positive_count_window = _safe_int(
            rec.get("base_alert_positive_count_window", rec.get("valid_alert_count_window", 0)),
            0,
        )
        alert_count_window = _safe_int(rec.get("alert_count_window"), 0)
        alert_support_count_window = max(
            event_type_alert_count_window,
            valid_alert_count_window,
            base_alert_positive_count_window,
            alert_count_window,
        )

        fanout_ok = bool(fanout_high or not require_fanout_for_refinement)
        same_window_evidence = bool(
            same_alert_window
            and fanout_ok
            and score_no_alert >= thresholds["same_window_score_threshold"]
        )
        near_window_evidence = bool(
            near_alert_window
            and fanout_ok
            and score_no_alert >= thresholds["near_window_score_threshold"]
        )
        extreme_probe_evidence = bool(
            fanout_high
            and score_no_alert >= thresholds["extreme_score_threshold"]
        )

        # Strict conservative priority:
        # 1. Same alert window may change Target_refined only if enabled, supported
        #    by multiple alert events, has known row impact, and does not exceed
        #    the per-key conversion cap.
        # 2. Near alert window is audit evidence by default; it does not convert.
        # 3. Extreme probe without strong alert association is suspicious only.
        if same_window_evidence:
            same_window_candidate_keys += 1
            if not allow_same_window_conversion:
                label_action = "suspicious_probe_only"
                target_for_no_alert = 0
                suspicious_by_probe = 1
                label_source = "suspicious_probe_only"
                refinement_reason = "same_window_evidence_target_conversion_disabled_by_policy"
                target_change_disabled_by_policy += 1
            elif alert_support_count_window < min_valid_alert_count_for_refinement:
                label_action = "suspicious_probe_only"
                target_for_no_alert = 0
                suspicious_by_probe = 1
                label_source = "suspicious_probe_only"
                refinement_reason = (
                    "same_window_evidence_but_alert_support_below_minimum;"
                    f"required={min_valid_alert_count_for_refinement};observed={alert_support_count_window}"
                )
                target_change_blocked_by_min_alert_count += 1
            elif no_alert_count_window <= 0:
                label_action = "suspicious_probe_only"
                target_for_no_alert = 0
                suspicious_by_probe = 1
                label_source = "suspicious_probe_only"
                refinement_reason = "same_window_evidence_but_unknown_conversion_size"
                target_change_blocked_by_unknown_size += 1
            elif max_conversion_per_key > 0 and no_alert_count_window > max_conversion_per_key:
                label_action = "suspicious_probe_only"
                target_for_no_alert = 0
                suspicious_by_probe = 1
                label_source = "suspicious_probe_only"
                refinement_reason = (
                    "same_window_evidence_but_exceeds_max_conversion_per_key;"
                    f"cap={max_conversion_per_key};observed={no_alert_count_window}"
                )
                target_change_blocked_by_per_key_cap += 1
            else:
                label_action = "probe_refined_same_window"
                target_for_no_alert = 1
                suspicious_by_probe = 1
                label_source = "probe_refined_same_window"
                refinement_reason = (
                    "same_src_ip_same_alert_window_and_probe_score_ge_configured_threshold_"
                    "and_fanout_high_and_alert_support_ge_minimum_and_per_key_cap"
                )

        elif near_window_evidence:
            near_window_candidate_keys += 1
            if allow_near_window_conversion:
                if alert_support_count_window >= min_valid_alert_count_for_refinement and no_alert_count_window > 0:
                    label_action = "probe_refined_near_alert_window"
                    target_for_no_alert = 1
                    suspicious_by_probe = 1
                    label_source = "probe_refined_near_alert_window"
                    refinement_reason = "near_alert_window_target_conversion_enabled_by_policy"
                else:
                    label_action = "suspicious_probe_only"
                    target_for_no_alert = 0
                    suspicious_by_probe = 1
                    label_source = "suspicious_probe_only"
                    refinement_reason = "near_window_evidence_but_alert_support_or_size_not_sufficient"
            else:
                label_action = "suspicious_probe_only"
                target_for_no_alert = 0
                suspicious_by_probe = 1
                label_source = "suspicious_probe_only"
                refinement_reason = "near_alert_window_evidence_target_conversion_disabled_by_policy"
                near_window_evidence_only_keys += 1

        elif extreme_probe_evidence:
            suspicious_only_candidate_keys += 1
            if allow_extreme_probe_conversion and no_alert_count_window > 0:
                label_action = "probe_refined_extreme_probe"
                target_for_no_alert = 1
                suspicious_by_probe = 1
                label_source = "probe_refined_extreme_probe"
                refinement_reason = "extreme_probe_target_conversion_enabled_by_policy"
                extreme_probe_target_candidate_keys += 1
            else:
                label_action = "suspicious_probe_only"
                target_for_no_alert = 0
                suspicious_by_probe = 1
                label_source = "suspicious_probe_only"
                refinement_reason = "extreme_probe_without_strong_alert_association"

        if label_action is None:
            continue

        out = {
            "app": app,
            "src_ip": src_ip,
            "window_start": win,
            "key": {
                "app": app,
                "src_ip": src_ip,
                "window_start": win,
            },
            "label_action": label_action,
            "label_source": label_source,
            "Target_refined_for_no_alert": int(target_for_no_alert),
            "suspicious_by_probe": int(suspicious_by_probe),
            "refinement_reason": refinement_reason,

            "probe_score_no_alert": float(score_no_alert),
            "probe_score_with_alert": float(score_with_alert),
            "probe_level": rec.get("probe_level"),
            "fanout_high": int(fanout_high),

            "event_count_window": _safe_int(rec.get("event_count_window"), 0),
            "unique_dest_ip_window": _safe_int(rec.get("unique_dest_ip_window"), 0),
            "unique_dest_port_window": _safe_int(rec.get("unique_dest_port_window"), 0),
            "total_bytes_window": _safe_int(rec.get("total_bytes_window"), 0),
            "total_pkts_window": _safe_int(rec.get("total_pkts_window"), 0),
            "event_type_alert_count_window": int(event_type_alert_count_window),
            "valid_alert_count_window": int(valid_alert_count_window),
            "base_alert_positive_count_window": int(base_alert_positive_count_window),
            "alert_support_count_window": int(alert_support_count_window),
            "alert_count_window": int(alert_count_window),
            "no_alert_count_window": int(no_alert_count_window),
            "estimated_conversion_rows": int(no_alert_count_window if target_for_no_alert == 1 else 0),
            "original_label_action": label_action,
            "conversion_guard_demoted": 0,

            "same_alert_window": int(same_alert_window),
            "near_alert_window": int(near_alert_window),
            "matched_alert_window": matched_alert_window,
            "minutes_to_alert_window": minutes_to_alert,
        }

        if int(target_for_no_alert) == 1:
            target_change_candidate_keys += 1
            target_change_candidates.append(out)
        else:
            suspicious_only_candidates.append(out)

    initial_label_counts = phase1_summary.get("label_counts", {})
    initial_benign = phase1_summary.get("benign") or phase1_summary.get("initial_benign")
    initial_attack = phase1_summary.get("attack") or phase1_summary.get("initial_malicious")

    # If Phase 1 was skipped/compact, derive the pre-refinement baseline from Phase 3.
    phase3_rows_scanned = _safe_int(phase3_summary.get("decoded_events", phase3_summary.get("rows_scanned", 0)), 0)
    phase3_alert_rows = _safe_int(phase3_summary.get("base_alert_positive_rows", phase3_summary.get("any_alert_rows", 0)), 0)
    if initial_benign is None and phase3_rows_scanned > 0:
        initial_benign = max(0, phase3_rows_scanned - phase3_alert_rows)
    if initial_attack is None and phase3_alert_rows > 0:
        initial_attack = phase3_alert_rows

    baseline_benign_rows = _safe_int(initial_benign, 0)
    if baseline_benign_rows <= 0:
        baseline_benign_rows = max(0, phase3_rows_scanned - phase3_alert_rows)
    if baseline_benign_rows <= 0:
        baseline_benign_rows = int(total_no_alert_rows_in_windows)

    conversion_limit_rows = int(baseline_benign_rows * (max_benign_conversion_pct / 100.0)) if baseline_benign_rows > 0 else 0
    estimated_conversion_rows_before_guard = int(sum(_safe_int(r.get("estimated_conversion_rows"), 0) for r in target_change_candidates))

    target_change_candidates.sort(
        key=lambda r: (
            0 if r.get("label_action") == "probe_refined_same_window" else 1,
            -_safe_int(r.get("alert_support_count_window"), 0),
            -_safe_float(r.get("probe_score_no_alert"), 0.0),
            -_safe_float(r.get("probe_score_with_alert"), 0.0),
            _safe_int(r.get("estimated_conversion_rows"), 0),
        )
    )

    selected_target_change: list[dict[str, Any]] = []
    demoted_by_guard: list[dict[str, Any]] = []
    estimated_conversion_rows_after_guard = 0

    guard_active = bool(stop_if_conversion_exceeds_limit and conversion_limit_rows > 0)
    for rec in target_change_candidates:
        est_rows = _safe_int(rec.get("estimated_conversion_rows"), 0)
        if (not guard_active) or (estimated_conversion_rows_after_guard + est_rows <= conversion_limit_rows):
            selected_target_change.append(rec)
            estimated_conversion_rows_after_guard += est_rows
            continue

        demoted = dict(rec)
        demoted["Target_refined_for_no_alert"] = 0
        demoted["suspicious_by_probe"] = 1
        demoted["label_source"] = "suspicious_probe_only"
        demoted["label_action"] = "suspicious_probe_only"
        demoted["estimated_conversion_rows"] = 0
        demoted["conversion_guard_demoted"] = 1
        demoted["refinement_reason"] = f"{demoted.get('refinement_reason')};demoted_by_max_benign_conversion_guard"
        demoted_by_guard.append(demoted)

    records_to_write = selected_target_change + suspicious_only_candidates + demoted_by_guard

    action_counter: Counter = Counter()
    probe_level_counter: Counter = Counter()
    same_window_keys = 0
    near_window_keys = 0
    suspicious_only_keys = 0

    with (
        suspicious_keys_path.open("wb") as f_keys,
        audit_path.open("w", newline="", encoding="utf-8") as f_audit,
    ):
        writer = csv.DictWriter(f_audit, fieldnames=audit_fieldnames)
        writer.writeheader()
        for out in records_to_write:
            _write_jsonl_record(f_keys, out)
            writer.writerow(_audit_row(out))

            label_action = str(out.get("label_action") or "unknown")
            action_counter[label_action] += 1
            probe_level_counter[str(out.get("probe_level", "unknown"))] += 1
            if label_action == "probe_refined_same_window":
                same_window_keys += 1
            elif label_action == "probe_refined_near_alert_window":
                near_window_keys += 1
            elif label_action == "suspicious_probe_only":
                suspicious_only_keys += 1

    keys_written = len(records_to_write)
    # Generic alias copies.
    _copy_text_file(suspicious_keys_path, suspicious_keys_alias)
    _copy_text_file(audit_path, audit_alias)

    probe_refined_keys = same_window_keys + near_window_keys
    conversion_guard_triggered = bool(
        guard_active and estimated_conversion_rows_before_guard > conversion_limit_rows
    )
    conversion_pct_before_guard = (
        (estimated_conversion_rows_before_guard / baseline_benign_rows) * 100.0
        if baseline_benign_rows > 0 else 0.0
    )
    conversion_pct_after_guard = (
        (estimated_conversion_rows_after_guard / baseline_benign_rows) * 100.0
        if baseline_benign_rows > 0 else 0.0
    )
    summary_warnings = []
    if conversion_guard_triggered:
        summary_warnings.append(
            "Estimated no-alert rows affected by target-changing refinement exceeded "
            "max_benign_conversion_pct; excess keys were demoted to suspicious_probe_only."
        )

    summary = {
        "phase": 4,
        "title": "Label Refinement Policy Builder",
        "status": "completed_with_warning" if conversion_guard_triggered else "completed",
        "current_run": app.upper(),
        "app": app,
        "generated_at": now_iso(),

        "input": {
            "phase3_probe_features": str(phase3.get("probe_features")),
            "phase3_alert_ip_index": str(phase3.get("alert_ip_index")),
            "phase3_summary": str(phase3.get("summary")),
            "phase1_summary": str(_phase1_summary_path(phase_dir)) if _phase1_summary_path(phase_dir) else None,
        },
        "output": {
            "label_policy": str(label_policy_path),
            "suspicious_keys": str(suspicious_keys_path),
            "refined_label_summary": str(refined_summary_path),
            "refinement_audit": str(audit_path),
            "summary_alias": str(summary_alias),
            "manifest": str(manifest_path),
        },

        "label_policy": {
            "label_mode": "event_type_or_valid_alert",
            "base_alert_positive": "event_type == alert OR valid Suricata alert evidence",
            "phase3_alert_ip_index_note": (
                "Patched Phase 3 writes alert_ip_index windows when "
                "base_alert_positive_count_window > 0. Legacy valid-alert-only "
                "indexes are still readable but may undercount alert windows."
            ),
        },
        "probe_windows_read": int(probe_windows_read),
        "alert_ip_windows": int(alert_ip_windows),
        "keys_written": int(keys_written),
        "probe_refined_keys": int(probe_refined_keys),
        "same_window_refined_keys": int(same_window_keys),
        "near_window_refined_keys": int(near_window_keys),
        "suspicious_only_keys": int(suspicious_only_keys),

        "candidate_counts_before_guard": {
            "target_change_candidate_keys": int(target_change_candidate_keys),
            "same_window_candidate_keys": int(same_window_candidate_keys),
            "near_window_candidate_keys": int(near_window_candidate_keys),
            "suspicious_only_candidate_keys": int(suspicious_only_candidate_keys),
            "near_window_evidence_only_keys": int(near_window_evidence_only_keys),
            "extreme_probe_target_candidate_keys": int(extreme_probe_target_candidate_keys),
            "target_change_blocked_by_min_alert_count": int(target_change_blocked_by_min_alert_count),
            "target_change_blocked_by_unknown_size": int(target_change_blocked_by_unknown_size),
            "target_change_blocked_by_per_key_cap": int(target_change_blocked_by_per_key_cap),
            "target_change_disabled_by_policy": int(target_change_disabled_by_policy),
        },
        "conversion_guard": {
            "enabled": bool(stop_if_conversion_exceeds_limit),
            "triggered": bool(conversion_guard_triggered),
            "baseline_benign_rows": int(baseline_benign_rows),
            "max_benign_conversion_pct": float(max_benign_conversion_pct),
            "conversion_limit_rows": int(conversion_limit_rows),
            "estimated_conversion_rows_before_guard": int(estimated_conversion_rows_before_guard),
            "estimated_conversion_pct_before_guard": float(conversion_pct_before_guard),
            "estimated_conversion_rows_after_guard": int(estimated_conversion_rows_after_guard),
            "estimated_conversion_pct_after_guard": float(conversion_pct_after_guard),
            "demoted_keys": int(len(demoted_by_guard)),
            "guard_action": "demote_excess_target_change_keys_to_suspicious_only",
        },
        "active_refinement_policy": {
            "policy_version": "strict_same_window_v2",
            "target_alert_is_never_modified": True,
            "target_refined_can_change_only_for_selected_no_alert_keys": True,
            "allow_same_window_conversion": bool(allow_same_window_conversion),
            "allow_near_window_conversion": bool(allow_near_window_conversion),
            "allow_extreme_probe_conversion": bool(allow_extreme_probe_conversion),
            "min_valid_alert_count_for_refinement": int(min_valid_alert_count_for_refinement),
            "require_fanout_for_refinement": bool(require_fanout_for_refinement),
            "max_conversion_per_key": int(max_conversion_per_key),
            "same_window_probe_percentile": float(thresholds.get("same_window_percentile", 0.0)),
            "same_window_score_threshold": float(thresholds.get("same_window_score_threshold", 0.0)),
            "near_window_policy": "suspicious_only" if not allow_near_window_conversion else "target_conversion_enabled",
            "extreme_probe_policy": "suspicious_only" if not allow_extreme_probe_conversion else "target_conversion_enabled",
        },
        "warnings": summary_warnings,

        "action_counts": {str(k): int(v) for k, v in action_counter.items()},
        "probe_level_counts": {str(k): int(v) for k, v in probe_level_counter.items()},

        "initial_label_counts_from_phase1": initial_label_counts,
        "initial_benign_from_phase1": initial_benign,
        "initial_attack_from_phase1": initial_attack,

        "thresholds": thresholds,
        "window_minutes": int(window_minutes),
        "near_window_radius": int(near_window_radius),
        "max_benign_conversion_pct": float(max_benign_conversion_pct),
        "max_conversion_per_key": int(max_conversion_per_key),
        "min_valid_alert_count_for_refinement": int(min_valid_alert_count_for_refinement),

        "safety_guards": {
            "ip_only_relabeling_enabled": False,
            "requires_same_alert_window_for_target_change": True,
            "near_alert_window_target_conversion_enabled": bool(allow_near_window_conversion),
            "extreme_probe_target_conversion_enabled": bool(allow_extreme_probe_conversion),
            "requires_minimum_alert_support_count": True,
            "requires_fanout_for_refinement": bool(require_fanout_for_refinement),
            "max_conversion_per_key_enabled": bool(max_conversion_per_key > 0),
            "extreme_probe_without_alert_association_is_suspicious_only": not bool(allow_extreme_probe_conversion),
            "max_benign_conversion_guard_enabled": bool(stop_if_conversion_exceeds_limit),
            "max_benign_conversion_guard_triggered": bool(conversion_guard_triggered),
            "estimated_conversion_guard_applied_in_phase4": True,
            "final_row_counts_verified_in_phase8": True,
        },

        "output_size_bytes": {
            "label_policy": int(file_size_bytes(label_policy_path)),
            "suspicious_keys": int(file_size_bytes(suspicious_keys_path)),
            "refinement_audit": int(file_size_bytes(audit_path)),
        },

        "methodology_note": (
            "Phase 4 creates strict conservative refinement keys from Phase 3 aggregate evidence. "
            "It does not scan the full app JSONL and does not write a row-level labeled dataset. "
            "It uses base alert windows aligned with split/Phase 8: event_type=alert OR valid alert evidence. "
            "Phase 8 applies these keys while exporting the final dataset."
        ),
    }

    write_json(summary, refined_summary_path)
    write_json(summary, refined_summary_alias)
    write_json(summary, summary_alias)
    write_json({
        "phase": 4,
        "app": app,
        "created_at": now_iso(),
        "files": {
            "label_policy": str(label_policy_path),
            "suspicious_keys": str(suspicious_keys_path),
            "refined_label_summary": str(refined_summary_path),
            "refinement_audit": str(audit_path),
            "summary_alias": str(summary_alias),
        },
        "summary": {
            "status": summary.get("status"),
            "probe_windows_read": int(probe_windows_read),
            "alert_ip_windows": int(alert_ip_windows),
            "keys_written": int(keys_written),
            "probe_refined_keys": int(probe_refined_keys),
            "suspicious_only_keys": int(suspicious_only_keys),
            "conversion_guard_triggered": bool(conversion_guard_triggered),
            "estimated_conversion_rows_after_guard": int(estimated_conversion_rows_after_guard),
            "strict_policy_version": "strict_same_window_v2",
            "allow_near_window_conversion": bool(allow_near_window_conversion),
            "max_conversion_per_key": int(max_conversion_per_key),
        },
    }, manifest_path)

    print("\n" + "=" * 72)
    print("Phase 4 - Label Refinement Policy Builder")
    print("=" * 72)
    print(f"Current Run           : {app.upper()}")
    print(f"Reading               : {phase3.get('probe_features')}")
    print(f"Alert IP Windows      : {alert_ip_windows:,}")
    print("Alert Policy          : event_type_or_valid_alert")
    print(f"Probe Windows Read    : {probe_windows_read:,}")
    print(f"Probe Refined Keys    : {probe_refined_keys:,}")
    print(f"Suspicious-only Keys  : {suspicious_only_keys:,}")
    print(f"Strict Policy         : same-window only | min_alert={min_valid_alert_count_for_refinement} | max_key={max_conversion_per_key:,}")
    print(f"Est. Conversion Guard : {estimated_conversion_rows_after_guard:,}/{conversion_limit_rows:,} rows "
          f"({conversion_pct_after_guard:.2f}% / cap {max_benign_conversion_pct:.2f}%)")
    if conversion_guard_triggered:
        print(f"Guard Demoted Keys    : {len(demoted_by_guard):,}")
    print(f"Output                : {refined_summary_path}")
    print("=" * 72 + "\n")

    return summary


# Backward-compatible aliases for pipeline fallback registry.
phase4_run = run_phase4
phase4_label_refinement = run_phase4
