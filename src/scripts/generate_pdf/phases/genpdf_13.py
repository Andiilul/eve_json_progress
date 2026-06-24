from __future__ import annotations

try:
    from ..context import fmt_float, fmt_int, fmt_seconds, shorten, safe_int
    from ..style import p, spacer, make_table, metric_cards, note_box
    from ._genpdf_common import summary, dict_value, list_value, add_diagnostics
except Exception:
    from context import fmt_float, fmt_int, fmt_seconds, shorten, safe_int
    from style import p, spacer, make_table, metric_cards, note_box
    from _genpdf_common import summary, dict_value, list_value, add_diagnostics


VIEW_LABELS = {
    "natural": "Natural Holdout",
    "balanced": "Balanced Holdout",
    "cv": "Cross-validation",
}


def _s(ctx, app: str) -> dict:
    return summary(ctx, app, 13)


def _method(rec: dict) -> str:
    return str(rec.get("method") or rec.get("Method") or "-")


def _model(rec: dict) -> str:
    return str(rec.get("model") or rec.get("Model") or "-")


def _score(rec: dict, *names: str):
    for name in names:
        if not name:
            continue
        value = rec.get(name)
        if value is not None:
            return value
    return None


def _score_float(rec: dict, *names: str) -> float:
    value = _score(rec, *names)
    try:
        return float(value)
    except Exception:
        return 0.0


def _features(rec: dict) -> str:
    return fmt_int(rec.get("train_features") or rec.get("feature_count") or rec.get("features"))


def _train_rows(rec: dict) -> str:
    return fmt_int(rec.get("train_rows"))


def _eval_rows(rec: dict, view: str) -> str:
    if view == "balanced":
        return fmt_int(rec.get("balanced_test_rows") or rec.get("balanced_holdout_rows"))
    if view == "cv":
        return fmt_int(rec.get("cv_rows") or rec.get("train_rows"))
    return fmt_int(rec.get("natural_test_rows") or rec.get("test_rows") or rec.get("holdout_rows"))


def _metrics(rec: dict, view: str) -> list[str]:
    """Return Accuracy, Precision, Recall, F1, AUC as five readable cells."""
    if view == "balanced":
        return [
            fmt_float(_score(rec, "balanced_holdout_accuracy"), 4),
            fmt_float(_score(rec, "balanced_holdout_precision_attack"), 4),
            fmt_float(_score(rec, "balanced_holdout_recall_attack"), 4),
            fmt_float(_score(rec, "balanced_holdout_f1_attack"), 4),
            fmt_float(_score(rec, "balanced_holdout_auc"), 4),
        ]
    if view == "cv":
        return [
            fmt_float(_score(rec, "accuracy", "cv_accuracy"), 4),
            fmt_float(_score(rec, "precision_attack", "cv_precision_attack"), 4),
            fmt_float(_score(rec, "recall_attack", "cv_recall_attack"), 4),
            fmt_float(_score(rec, "f1_attack", "cv_f1_attack", "cv_f1"), 4),
            fmt_float(_score(rec, "auc", "cv_auc"), 4),
        ]
    return [
        fmt_float(_score(rec, "natural_holdout_accuracy", "holdout_accuracy"), 4),
        fmt_float(_score(rec, "natural_holdout_precision_attack", "holdout_precision_attack"), 4),
        fmt_float(_score(rec, "natural_holdout_recall_attack", "holdout_recall_attack"), 4),
        fmt_float(_score(rec, "natural_holdout_f1_attack", "holdout_f1_attack"), 4),
        fmt_float(_score(rec, "natural_holdout_auc", "holdout_auc"), 4),
    ]


def _metric_sort_key(rec: dict, view: str) -> float:
    if view == "balanced":
        return _score_float(rec, "balanced_holdout_f1_attack")
    if view == "cv":
        return _score_float(rec, "f1_attack", "cv_f1_attack", "cv_f1")
    return _score_float(rec, "natural_holdout_f1_attack", "holdout_f1_attack")


def _results(s: dict, view: str) -> list[dict]:
    candidates = {
        "natural": ["top_natural_holdout", "top_natural_results", "top_primary_holdout", "results_table"],
        "balanced": ["top_balanced_holdout", "top_balanced_results", "results_table"],
        "cv": ["top_cv", "top_cv_results", "results_table"],
    }.get(view, [view])
    vals: list[dict] = []
    for name in candidates:
        raw = list_value(s.get(name))
        if raw:
            vals = [x for x in raw if isinstance(x, dict)]
            break
    return sorted(vals, key=lambda r: _metric_sort_key(r, view), reverse=True)


def _best_record(s: dict) -> dict:
    best = dict_value(s.get("best_by_natural_holdout_f1") or s.get("best_by_preferred_metric"))
    if best:
        return best
    vals = _results(s, "natural")
    return vals[0] if vals else {}


def _app_overview(ctx, styles):
    rows = [["App", "Train rows", "Natural test", "Balanced test", "Result rows", "Best natural", "Natural F1", "Natural AUC", "Time"]]
    total_results = 0
    for app in ctx.selected_apps:
        s = _s(ctx, app)
        best = _best_record(s)
        total_results += safe_int(s.get("results_rows"), 0)
        rows.append([
            app.upper(),
            fmt_int(s.get("train_rows_loaded") or dict_value(s.get("train_sample_info")).get("sample_rows")),
            fmt_int(s.get("natural_test_rows_loaded") or dict_value(s.get("natural_test_sample_info")).get("sample_rows")),
            fmt_int(s.get("balanced_test_rows_loaded") or dict_value(s.get("balanced_test_sample_info")).get("sample_rows")),
            fmt_int(s.get("results_rows")),
            shorten(f"{_method(best)}/{_model(best)}", 36),
            fmt_float(_score(best, "natural_holdout_f1_attack", "holdout_f1_attack"), 4),
            fmt_float(_score(best, "natural_holdout_auc", "holdout_auc"), 4),
            fmt_seconds(s.get("seconds") or ctx.app_phase(app, 13).get("seconds")),
        ])
    cards = metric_cards([
        ("Result rows", fmt_int(total_results), "model-method evaluations"),
        ("Main holdout", "Natural", "primary thesis evaluation"),
        ("Secondary", "Balanced", "class separability check"),
        ("Metrics", "Acc, Prec, Rec, F1, AUC", "shown as separate columns"),
    ], styles, columns=4)
    return cards, make_table(rows, styles, col_widths=[0.50*72,0.85*72,0.85*72,0.85*72,0.70*72,0.90*72,0.65*72,0.65*72,0.75*72], font_size=6.1)


def _best_natural_table(ctx, styles):
    rows = [["App", "Method", "Model", "Acc", "Precision", "Recall", "F1", "AUC", "Features", "Train", "Natural test", "Balanced test"]]
    for app in ctx.selected_apps:
        s = _s(ctx, app)
        rec = _best_record(s)
        if not rec:
            rows.append([app.upper(), "-", "No result", "-", "-", "-", "-", "-", "-", "-", "-", "-"])
            continue
        rows.append([
            app.upper(), _method(rec), _model(rec), *_metrics(rec, "natural"), _features(rec),
            _train_rows(rec), _eval_rows(rec, "natural"), _eval_rows(rec, "balanced"),
        ])
    return make_table(rows, styles, col_widths=[0.45*72,0.55*72,0.65*72,0.55*72,0.65*72,0.60*72,0.55*72,0.55*72,0.55*72,0.75*72,0.85*72,0.85*72], font_size=5.8)


def _detail_table(ctx, styles, app: str, view: str, limit: int = 8):
    vals = _results(_s(ctx, app), view)[:limit]
    rows = [["Method", "Model", "Acc", "Precision", "Recall", "F1", "AUC", "Features", "Train rows", "Eval rows"]]
    for rec in vals:
        rows.append([
            _method(rec), _model(rec), *_metrics(rec, view), _features(rec), _train_rows(rec), _eval_rows(rec, view)
        ])
    if len(rows) == 1:
        rows.append(["-", "No result rows found", "-", "-", "-", "-", "-", "-", "-", "-"])
    return make_table(rows, styles, col_widths=[0.70*72,0.80*72,0.65*72,0.70*72,0.65*72,0.60*72,0.60*72,0.60*72,0.90*72,0.90*72], font_size=6.1)


def _render_detail_section(story, ctx, styles, view: str, section_no: str):
    story.append(p(f"13.{section_no} {VIEW_LABELS[view]} Detail", styles.subheading))
    for app in ctx.selected_apps:
        story.append(p(f"{app.upper()} - {VIEW_LABELS[view]} metrics", styles.small_heading if hasattr(styles, "small_heading") else styles.subheading))
        story.append(_detail_table(ctx, styles, app, view))
        story.append(spacer(0.08))


def render(ctx, styles):
    story = []
    story.append(p("13. Model Training and Holdout Evaluation", styles.heading))
    story.append(p(
        "Phase 13 trains DT, RFC, LinearSVC, and XGBoost using Phase 12 feature sets. "
        "Natural-distribution holdout is the primary evaluation; balanced holdout is a secondary class-separability check.",
        styles.body,
    ))

    cards, overview = _app_overview(ctx, styles)
    story.append(cards)
    story.append(spacer())
    story.append(overview)
    story.append(spacer())

    story.append(note_box(
        "Precision, recall, and F1 are attack-class metrics. Natural holdout should be used as the main thesis claim; balanced holdout is useful for class-separability analysis.",
        styles,
        title="How to read Phase 13 metrics",
    ))
    story.append(spacer(0.06))

    story.append(p("13.1 Best Natural Holdout per App", styles.subheading))
    story.append(_best_natural_table(ctx, styles))
    story.append(spacer())

    _render_detail_section(story, ctx, styles, "natural", "2")
    _render_detail_section(story, ctx, styles, "balanced", "3")
    _render_detail_section(story, ctx, styles, "cv", "4")

    add_diagnostics(story, ctx, styles, 13)
    return story
