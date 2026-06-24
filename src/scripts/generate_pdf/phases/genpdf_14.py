from __future__ import annotations

try:
    from ..context import fmt_float, fmt_int, shorten
    from ..style import p, spacer, make_table, image_grid, note_box, metric_cards
    from ._genpdf_common import summary, dict_value, list_value, add_diagnostics
except Exception:
    from context import fmt_float, fmt_int, shorten
    from style import p, spacer, make_table, image_grid, note_box, metric_cards
    from _genpdf_common import summary, dict_value, list_value, add_diagnostics


VIEW_LABELS = {
    "natural": "Natural Holdout",
    "balanced": "Balanced Holdout",
    "cv": "Cross-validation",
}


def _s(ctx, app: str) -> dict:
    return summary(ctx, app, 14)


def _method(rec: dict) -> str:
    return str(rec.get("Method") or rec.get("method") or "-")


def _model(rec: dict) -> str:
    return str(rec.get("Model") or rec.get("model") or "-")


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


def _metrics(rec: dict, view: str) -> list[str]:
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


def _metric_pair(rec: dict, view: str) -> str:
    vals = _metrics(rec, view)
    # F1/AUC only, used for compact summary cells.
    return f"{vals[3]}/{vals[4]}"


def _features(rec: dict) -> str:
    return fmt_int(rec.get("train_features") or rec.get("feature_count") or rec.get("features"))


def _selection_label(value: object) -> str:
    text = str(value or "natural_holdout_f1_attack").strip()
    low = text.lower()
    if "natural" in low and "preferred" in low:
        return "natural holdout F1"
    if "natural_holdout_f1" in low:
        return "natural holdout F1"
    if "balanced_holdout_f1" in low:
        return "balanced holdout F1"
    if "auc" in low and "natural" in low:
        return "natural holdout AUC"
    return shorten(text, 28)


def _rows(rec: dict, view: str) -> str:
    train = fmt_int(rec.get("train_rows"))
    if view == "balanced":
        test = fmt_int(rec.get("balanced_test_rows") or rec.get("balanced_holdout_rows"))
    elif view == "cv":
        test = fmt_int(rec.get("cv_rows") or rec.get("train_rows"))
    else:
        test = fmt_int(rec.get("natural_test_rows") or rec.get("test_rows") or rec.get("holdout_rows"))
    return f"{train}/{test}"


def _metric_sort_key(rec: dict, view: str) -> float:
    if view == "balanced":
        return _score_float(rec, "balanced_holdout_f1_attack")
    if view == "cv":
        return _score_float(rec, "f1_attack", "cv_f1_attack", "cv_f1")
    return _score_float(rec, "natural_holdout_f1_attack", "holdout_f1_attack")


def _results(s: dict, view: str) -> list[dict]:
    fallback = {
        "natural": ["top_natural_holdout", "top_natural_results", "results_table"],
        "balanced": ["top_balanced_holdout", "top_balanced_results", "results_table"],
        "cv": ["top_cv", "top_cv_results", "results_table"],
    }.get(view, [view])
    vals: list[dict] = []
    for name in fallback:
        raw = list_value(s.get(name))
        if raw:
            vals = [x for x in raw if isinstance(x, dict)]
            break
    return sorted(vals, key=lambda r: _metric_sort_key(r, view), reverse=True)


def _best(ctx, app: str) -> dict:
    s = _s(ctx, app)
    best = dict_value(s.get("best_model") or s.get("best"))
    if best:
        return best
    vals = _results(s, "natural")
    return vals[0] if vals else {}


def _summary_table(ctx, styles):
    rows = [["App", "Best method", "Best model", "Selected by", "Natural F1", "Natural AUC", "Balanced F1", "Balanced AUC", "CV F1", "CV AUC"]]
    total_results = 0
    for app in ctx.selected_apps:
        s = _s(ctx, app)
        total_results += len(list_value(s.get("results_table")))
        rec = _best(ctx, app)
        selected_by = dict_value(s.get("evaluation_policy")).get("best_model_selection") or s.get("best_metric") or "natural_holdout_f1_attack"
        rows.append([
            app.upper(), _method(rec), _model(rec), _selection_label(selected_by),
            _metrics(rec, "natural")[3], _metrics(rec, "natural")[4],
            _metrics(rec, "balanced")[3], _metrics(rec, "balanced")[4],
            _metrics(rec, "cv")[3], _metrics(rec, "cv")[4],
        ])
    cards = metric_cards([
        ("Result rows", fmt_int(total_results), "loaded from Phase 13/14 summaries"),
        ("Main claim", "Natural F1/AUC", "primary evaluation"),
        ("Secondary", "Balanced", "separability check"),
        ("Output", "Per app", "best available model"),
    ], styles, columns=4)
    return cards, make_table(rows, styles, col_widths=[0.45*72,0.80*72,0.80*72,1.15*72,0.65*72,0.65*72,0.70*72,0.70*72,0.60*72,0.60*72], font_size=6.0)


def _detail_table(ctx, styles, app: str, view: str, limit: int = 6):
    rows = [["Method", "Model", "Acc", "Precision", "Recall", "F1", "AUC", "Features", "Rows"]]
    vals = _results(_s(ctx, app), view)[:limit]
    for rec in vals:
        rows.append([
            _method(rec), _model(rec), *_metrics(rec, view), _features(rec), _rows(rec, view)
        ])
    if len(rows) == 1:
        rows.append(["-", "No result rows found", "-", "-", "-", "-", "-", "-", "-"])
    return make_table(rows, styles, col_widths=[0.75*72,0.85*72,0.70*72,0.78*72,0.70*72,0.65*72,0.65*72,0.65*72,1.15*72], font_size=6.1)


def _render_detail_section(story, ctx, styles, view: str, section_no: str):
    story.append(p(f"14.{section_no} Top {VIEW_LABELS[view]} Results", styles.subheading))
    for app in ctx.selected_apps:
        story.append(p(f"{app.upper()} - {VIEW_LABELS[view]}", styles.small_heading if hasattr(styles, "small_heading") else styles.subheading))
        story.append(_detail_table(ctx, styles, app, view))
        story.append(spacer(0.08))


def render(ctx, styles):
    story = []
    story.append(p("14. Final Evaluation Summary", styles.heading))
    story.append(p("Phase 14 consolidates the final model evidence chain. It is summary-driven and does not retrain models or reread raw EVE logs.", styles.body))

    cards, table = _summary_table(ctx, styles)
    story.append(cards)
    story.append(spacer())
    story.append(table)
    story.append(spacer())

    story.append(note_box(
        "Use natural holdout as the main claim. Balanced holdout is useful as a secondary class-separability check, but it does not represent the real class distribution.",
        styles,
        title="Evaluation interpretation",
    ))
    story.append(spacer(0.08))

    _render_detail_section(story, ctx, styles, "natural", "1")
    _render_detail_section(story, ctx, styles, "balanced", "2")
    _render_detail_section(story, ctx, styles, "cv", "3")

    imgs = []
    for app in ctx.selected_apps:
        figs = dict_value(_s(ctx, app).get("figures")) or dict_value(_s(ctx, app).get("outputs"))
        for fig_key in ["natural_holdout_metrics", "balanced_holdout_metrics", "performance_heatmap", "cv_metrics", "confusion_matrix", "roc_curves"]:
            for key_name in [f"figure_{fig_key}", fig_key]:
                if figs.get(key_name):
                    imgs.append((f"{app.upper()} {fig_key.replace('_', ' ').title()}", figs.get(key_name)))
                    break
    grid = image_grid(imgs[:6], styles, columns=2, max_height=2.3*72)
    if grid:
        story.append(p("14.4 Evaluation Figures", styles.subheading))
        story.append(grid)
        story.append(spacer())

    add_diagnostics(story, ctx, styles, 14)
    return story
