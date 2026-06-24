# src/scripts/generate_pdf/_title/main.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        return int(x)
    except Exception:
        try:
            return int(float(x))
        except Exception:
            return default


def _float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _fmt_int(x: Any) -> str:
    return f"{_int(x):,}"


def _fmt_float(x: Any, digits: int = 2) -> str:
    return f"{_float(x):,.{digits}f}"


def _summary(ctx: Any, key: str) -> Dict[str, Any]:
    if hasattr(ctx, "summary"):
        try:
            obj = ctx.summary(key) or {}
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def _apps(ctx: Any) -> Tuple[str, ...]:
    apps = _get(ctx, "selected_apps", None)
    if isinstance(apps, (list, tuple)) and apps:
        return tuple(str(a).upper() for a in apps)
    return ("DNS", "HTTP", "TLS", "SSH")


def _phase1_rows(ctx: Any) -> Dict[str, Any]:
    p1 = _summary(ctx, "phase1")
    p1_obj = _get(ctx, "phase1", None)
    return {
        "input_file": (
            p1.get("input_file")
            or p1.get("source_file")
            or _get(p1_obj, "input_file", None)
            or "N/A"
        ),
        "total_lines_seen": p1.get("total_lines_seen", _get(p1_obj, "total_lines_seen", 0)),
        "decoded_events": p1.get("decoded_events", _get(p1_obj, "decoded_events", 0)),
        "rows_written": p1.get("rows_written", _get(p1_obj, "rows_written", 0)),
        "malformed": p1.get("malformed", _get(p1_obj, "malformed_json", 0)),
        "missing_src_ip": p1.get("missing_src_ip", _get(p1_obj, "missing_src_ip", 0)),
        "malicious_evidence": p1.get("malicious_evidence", _get(p1_obj, "malicious_evidence", 0)),
        "no_alert_unknown": p1.get("no_alert_unknown", _get(p1_obj, "no_alert_unknown", 0)),
        "shards_written": p1.get("shards_written", _get(p1_obj, "shards_written", 0)),
    }


def _sum_target_counts(summary: Dict[str, Any], key: str = "target_counts") -> Dict[str, int]:
    apps = summary.get("apps") or {}
    out = {"0": 0, "1": 0}
    if not isinstance(apps, dict):
        return out
    for app_summary in apps.values():
        if not isinstance(app_summary, dict):
            continue
        counts = app_summary.get(key) or {}
        if isinstance(counts, dict):
            out["0"] += _int(counts.get("0", counts.get(0, 0)))
            out["1"] += _int(counts.get("1", counts.get(1, 0)))
    return out


def _phase_total(summary: Dict[str, Any], *keys: str) -> int:
    for k in keys:
        v = summary.get(k)
        if v is not None:
            return _int(v)
    apps = summary.get("apps") or {}
    if isinstance(apps, dict):
        total = 0
        for s in apps.values():
            if not isinstance(s, dict):
                continue
            for k in keys:
                if k in s:
                    total += _int(s.get(k))
                    break
        return total
    return 0


def _processed_shape(ctx: Any) -> Dict[str, int]:
    # Prefer Phase 7 clean checkpoint because it is the downstream source of truth.
    p7 = _summary(ctx, "phase7")
    rows = _phase_total(p7, "total_rows_out", "rows_out", "rows_written")
    cols = 0
    apps = p7.get("apps") or {}
    if isinstance(apps, dict):
        for s in apps.values():
            if not isinstance(s, dict):
                continue
            cols = max(cols, _int(s.get("output_cols_max") or s.get("output_cols_min") or 0))
    return {"rows": rows, "cols": cols}


def _split_totals(ctx: Any) -> Dict[str, int]:
    split = _get(ctx, "split", None)
    return {
        "train_attack": _int(_get(split, "train_attack", 0)),
        "train_benign": _int(_get(split, "train_benign", 0)),
        "test_attack": _int(_get(split, "test_attack", 0)),
        "test_benign": _int(_get(split, "test_benign", 0)),
        "total_train": _int(_get(split, "total_train", 0)),
        "total_test": _int(_get(split, "total_test", 0)),
    }


def _best_models(ctx: Any) -> str:
    # Prefer final_summary.best_models_by_app when pipeline.py has written it.
    final = _summary(ctx, "final")
    best_final = final.get("best_models_by_app") or {}
    chunks: List[str] = []
    if isinstance(best_final, dict) and best_final:
        for app, best in best_final.items():
            if not isinstance(best, dict) or not best:
                continue
            chunks.append(
                f"{str(app).upper()}: {best.get('method', best.get('Method', 'N/A'))}/{best.get('model', best.get('Model', 'N/A'))} "
                f"F1={_fmt_float(best.get('f1_attack', 0), 4)} AUC={_fmt_float(best.get('auc', 0), 4)}"
            )
        if chunks:
            return " | ".join(chunks)

    # Fallback to Phase 13 per-app summaries.
    p13 = _summary(ctx, "phase13")
    apps = p13.get("apps") or p13.get("by_app") or {}
    if not isinstance(apps, dict):
        return "N/A"
    for app, s in apps.items():
        if not isinstance(s, dict):
            continue
        best = s.get("best_by_cv_f1_attack") or s.get("best") or {}
        if not isinstance(best, dict) or not best:
            continue
        chunks.append(
            f"{str(app).upper()}: {best.get('Method', best.get('method', 'N/A'))}/{best.get('Model', best.get('model', 'N/A'))} "
            f"F1={_fmt_float(best.get('f1_attack', 0), 4)} AUC={_fmt_float(best.get('auc', 0), 4)}"
        )
    return " | ".join(chunks) if chunks else "N/A"


def _phase_status_summary(ctx: Any) -> str:
    counts: Dict[str, int] = {}
    for i in range(1, 15):
        s = _summary(ctx, f"phase{i}")
        status = str(s.get("status") or ("available" if s else "missing"))
        counts[status] = counts.get(status, 0) + 1
    return ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))


def _style(styles: Any, key: str, attr: str):
    if isinstance(styles, dict) and key in styles:
        return styles[key]
    try:
        return styles[key]
    except Exception:
        return getattr(styles, attr)


def build_title(story: List[Any], *, cfg: Any, styles: Dict[str, Any], ctx: Any) -> None:
    title_style = _style(styles, "title_style", "H1")
    text_style = _style(styles, "text_style", "P")

    pipeline_start: Optional[datetime] = _get(cfg, "pipeline_start", None)
    if pipeline_start is None:
        pipeline_start = datetime.now()

    run_id = _get(cfg, "run_id", "run")
    artifacts_dir = _get(cfg, "artifacts_dir", "N/A")
    sample_size = _int(_get(cfg, "sample_size", 0), 0)

    p1 = _phase1_rows(ctx)
    p4_counts = _sum_target_counts(_summary(ctx, "phase4"), "target_counts")
    proc = _processed_shape(ctx)
    split = _split_totals(ctx)

    report_title = "SURICATA EVE APP-AWARE PIPELINE REPORT"
    story.append(Paragraph(report_title, title_style))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        "Fourteen-phase report for application-filtered Suricata EVE log feature engineering, "
        "label refinement, leakage-aware modeling, and advanced evaluation.",
        text_style,
    ))
    story.append(Spacer(1, 0.18 * inch))

    summary_data = [
        ["Report Generated", pipeline_start.strftime("%Y-%m-%d %H:%M:%S")],
        ["Run ID", str(run_id)],
        ["Sample Size Tag", f"{sample_size:,}"],
        ["Selected Apps", ", ".join(_apps(ctx))],
        ["Artifacts Dir", str(artifacts_dir)],
        ["", ""],

        ["Raw Input / Phase 1", ""],
        ["Input File", str(p1["input_file"])],
        ["Total Lines Seen", _fmt_int(p1["total_lines_seen"])],
        ["Decoded Events", _fmt_int(p1["decoded_events"])],
        ["Rows Written to Staging", _fmt_int(p1["rows_written"])],
        ["Malformed / Missing src_ip", f"{_fmt_int(p1['malformed'])} / {_fmt_int(p1['missing_src_ip'])}"],
        ["Malicious Evidence / Unknown", f"{_fmt_int(p1['malicious_evidence'])} / {_fmt_int(p1['no_alert_unknown'])}"],
        ["Staging Shards", _fmt_int(p1["shards_written"])],
        ["", ""],

        ["Final Label / Clean Checkpoint", ""],
        ["Final Target Counts", f"Benign: {_fmt_int(p4_counts['0'])} | Malicious: {_fmt_int(p4_counts['1'])}"],
        ["Clean Dataset Size", f"{proc['rows']:,} rows × {proc['cols']:,} cols"],
        ["Train/Test Rows", f"Train: {split['total_train']:,} | Test: {split['total_test']:,}"],
        ["Train Target", f"Benign: {split['train_benign']:,} | Attack: {split['train_attack']:,}"],
        ["Test Target", f"Benign: {split['test_benign']:,} | Attack: {split['test_attack']:,}"],
        ["", ""],

        ["Modeling / Evaluation", ""],
        ["Best Phase 13 Models", _best_models(ctx)],
        ["Phase Status Summary", _phase_status_summary(ctx)],
    ]

    t = Table(summary_data, colWidths=[2.35 * inch, 4.15 * inch])
    section_rows = [6, 15, 23]
    spacer_rows = [5, 14, 22]
    commands = [
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#ecf0f1")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for r in section_rows:
        commands.extend([
            ("BACKGROUND", (0, r), (-1, r), colors.HexColor("#dfe6e9")),
            ("SPAN", (0, r), (1, r)),
            ("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"),
        ])
    for r in spacer_rows:
        commands.extend([
            ("BACKGROUND", (0, r), (-1, r), colors.white),
            ("GRID", (0, r), (-1, r), 0, colors.white),
        ])
    t.setStyle(TableStyle(commands))
    story.append(t)
    story.append(PageBreak())
