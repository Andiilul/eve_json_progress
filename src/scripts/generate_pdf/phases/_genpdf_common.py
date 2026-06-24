
from __future__ import annotations

"""Common helpers for redesigned genpdf_N renderers."""

from pathlib import Path
from typing import Any, Callable

try:
    from ..context import counts_text, fmt_bytes, fmt_float, fmt_int, fmt_pct, fmt_seconds, safe_float, safe_int, shorten
    from ..style import CONTENT_WIDTH, p, spacer, make_table, warning_table, metric_cards, note_box, image_grid, image_from_path
except Exception:
    from context import counts_text, fmt_bytes, fmt_float, fmt_int, fmt_pct, fmt_seconds, safe_float, safe_int, shorten
    from style import CONTENT_WIDTH, p, spacer, make_table, warning_table, metric_cards, note_box, image_grid, image_from_path


def item(ctx, app: str, phase: int):
    return ctx.app_phase(app, phase)


def summary(ctx, app: str, phase: int) -> dict[str, Any]:
    s = item(ctx, app, phase).summary
    return s if isinstance(s, dict) else {}


def dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def count_value(counts: Any, key: str | int) -> int:
    if not isinstance(counts, dict):
        return 0
    return safe_int(counts.get(str(key), counts.get(key, 0)), 0)


def pct(num: Any, den: Any, ndigits: int = 2) -> str:
    n = safe_float(num, 0.0)
    d = safe_float(den, 0.0)
    if d <= 0:
        return "-"
    return f"{(n / d) * 100.0:.{ndigits}f}%"


def app_label_counts(s: dict[str, Any]) -> tuple[int, int, int]:
    # Phase 1/2 metrics have appeared in several shapes across runs:
    #   {label_counts:{benign, malicious}}
    #   {benign, attack, total}
    #   {source_counts:{label_counts:{...}, written_rows:...}}
    # Support all of them so the PDF does not show 0/0 when direct summaries
    # are copied into metrics_json.
    counts = dict_value(s.get("label_counts"))
    if not counts:
        counts = dict_value(dict_value(s.get("source_counts")).get("label_counts"))

    benign = (
        count_value(counts, "benign")
        or count_value(counts, 0)
        or safe_int(s.get("benign"), 0)
        or safe_int(s.get("initial_benign"), 0)
    )
    attack = (
        count_value(counts, "malicious")
        or count_value(counts, "attack")
        or count_value(counts, 1)
        or safe_int(s.get("attack"), 0)
        or safe_int(s.get("malicious"), 0)
        or safe_int(s.get("initial_attack"), 0)
    )
    source_counts = dict_value(s.get("source_counts"))
    total = safe_int(
        s.get("total")
        or s.get("rows")
        or s.get("matched_rows")
        or s.get("written_rows")
        or source_counts.get("written_rows")
        or source_counts.get("matched_rows"),
        0,
    )
    if total <= 0:
        total = benign + attack
    return total, benign, attack


def phase8_diag(s: dict[str, Any]) -> dict[str, Any]:
    return dict_value(s.get("phase8_label_diagnostics"))


def target_counts(s: dict[str, Any]) -> dict[str, Any]:
    return dict_value(s.get("target_counts"))


def target_alert_counts(s: dict[str, Any]) -> dict[str, Any]:
    return dict_value(s.get("target_alert_counts"))


def simple_diagnostics(ctx, phase: int, checks: list[tuple[str, Callable[[dict[str, Any], Any], str | None]]] | None = None) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for app in ctx.selected_apps:
        it = item(ctx, app, phase)
        s = it.summary
        if not it.exists:
            out.append((app, f"Phase {phase} central metrics file is missing."))
            continue
        if not isinstance(s, dict) or not s:
            out.append((app, f"Phase {phase} metrics exists, but detailed summary is empty."))
            continue
        for w in it.warnings:
            out.append((app, str(w)))
        raw = s.get("warnings")
        if isinstance(raw, list):
            for w in raw:
                if str(w).strip():
                    out.append((app, str(w)))
        elif isinstance(raw, str) and raw.strip():
            out.append((app, raw.strip()))
        for _, fn in checks or []:
            try:
                msg = fn(s, it)
            except Exception as exc:
                msg = f"Diagnostic check failed: {exc}"
            if msg:
                out.append((app, msg))
    # de-duplicate while preserving order
    seen = set()
    dedup = []
    for x in out:
        if x not in seen:
            dedup.append(x); seen.add(x)
    return dedup


def add_diagnostics(story: list[Any], ctx, styles, phase: int, *, title: str = "Diagnostics", checks=None) -> None:
    diag = simple_diagnostics(ctx, phase, checks=checks)
    if diag:
        story.append(p(title, styles.subheading)); story.append(warning_table(diag, styles)); story.append(spacer(0.04))


def first_existing_path(*values: Any) -> str | None:
    for value in values:
        if not value:
            continue
        try:
            pth = Path(str(value))
            if pth.exists() and pth.is_file():
                return str(pth)
        except Exception:
            pass
    return None


def feature_list_from_summary(s: dict[str, Any]) -> list[str]:
    keys = [
        "features_for_modeling", "approved_numeric_features", "approved_model_features",
        "modeling_features", "training_features", "no_leak_features_list", "selected_features",
        "feature_list", "columns"
    ]
    for key in keys:
        value = s.get(key)
        if isinstance(value, list):
            out = []
            for x in value:
                if isinstance(x, dict):
                    name = x.get("name") or x.get("feature") or x.get("column")
                    if name: out.append(str(name))
                else:
                    out.append(str(x))
            if out:
                return out
    fc = s.get("feature_counts") if isinstance(s.get("feature_counts"), dict) else {}
    value = fc.get("features_for_modeling") or fc.get("approved_numeric_features")
    if isinstance(value, list):
        return [str(x) for x in value]
    return []


def feature_grid(features: list[str], styles, *, title: str, max_items: int = 120):
    rows = [["#", "Feature", "#", "Feature", "#", "Feature"]]
    shown = features[:max_items]
    for i in range(0, len(shown), 3):
        row = []
        for j in range(3):
            idx = i+j
            if idx < len(shown):
                row.extend([str(idx+1), shown[idx]])
            else:
                row.extend(["", ""])
        rows.append(row)
    if len(features) > max_items:
        rows.append(["", f"... {len(features)-max_items} more features not shown", "", "", "", ""])
    return make_table(rows, styles, col_widths=[0.35*72, 2.8*72, 0.35*72, 2.8*72, 0.35*72, 2.8*72], font_size=6.5)
