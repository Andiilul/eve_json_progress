from __future__ import annotations

try:
    from ..context import fmt_float, fmt_int, shorten
    from ..style import p, spacer, make_table, image_grid, note_box, metric_cards
    from ._genpdf_common import summary, dict_value, list_value, add_diagnostics
except Exception:
    from context import fmt_float, fmt_int, shorten
    from style import p, spacer, make_table, image_grid, note_box, metric_cards
    from _genpdf_common import summary, dict_value, list_value, add_diagnostics


def _s(ctx, app: str) -> dict:
    return summary(ctx, app, 14)


def _score(rec: dict, *names: str):
    for name in names:
        if rec.get(name) is not None:
            return rec.get(name)
    return None


def _metric_pair(rec: dict, f1_key: str, auc_key: str, alt_f1: str | None = None, alt_auc: str | None = None) -> str:
    return f"{fmt_float(_score(rec, f1_key, alt_f1 or ''), 4)}/{fmt_float(_score(rec, auc_key, alt_auc or ''), 4)}"


def _top(ctx, styles, key: str):
    rows = [["App", "Method", "Model", "Natural Acc/Prec/Rec/F1/AUC", "Balanced Acc/Prec/Rec/F1/AUC", "CV Acc/Prec/Rec/F1/AUC", "Features", "Rows"]]
    fallback = {
        "natural": ["top_natural_holdout", "top_natural_results", "results_table"],
        "balanced": ["top_balanced_holdout", "top_balanced_results", "results_table"],
        "cv": ["top_cv", "top_cv_results", "results_table"],
    }.get(key, [key])
    for app in ctx.selected_apps:
        s = _s(ctx, app)
        vals = []
        for name in fallback:
            vals = list_value(s.get(name))
            if vals:
                break
        if key == "natural":
            vals = sorted([x for x in vals if isinstance(x, dict)], key=lambda r: float(r.get("natural_holdout_f1_attack") or r.get("holdout_f1_attack") or 0), reverse=True)
        elif key == "balanced":
            vals = sorted([x for x in vals if isinstance(x, dict)], key=lambda r: float(r.get("balanced_holdout_f1_attack") or 0), reverse=True)
        elif key == "cv":
            vals = sorted([x for x in vals if isinstance(x, dict)], key=lambda r: float(r.get("f1_attack") or 0), reverse=True)
        for rec in vals[:6]:
            natural = "/".join([
                fmt_float(_score(rec, "natural_holdout_accuracy", "holdout_accuracy"), 4),
                fmt_float(_score(rec, "natural_holdout_precision_attack", "holdout_precision_attack"), 4),
                fmt_float(_score(rec, "natural_holdout_recall_attack", "holdout_recall_attack"), 4),
                fmt_float(_score(rec, "natural_holdout_f1_attack", "holdout_f1_attack"), 4),
                fmt_float(_score(rec, "natural_holdout_auc", "holdout_auc"), 4),
            ])
            balanced = "/".join([
                fmt_float(_score(rec, "balanced_holdout_accuracy"), 4),
                fmt_float(_score(rec, "balanced_holdout_precision_attack"), 4),
                fmt_float(_score(rec, "balanced_holdout_recall_attack"), 4),
                fmt_float(_score(rec, "balanced_holdout_f1_attack"), 4),
                fmt_float(_score(rec, "balanced_holdout_auc"), 4),
            ])
            cv = "/".join([
                fmt_float(_score(rec, "accuracy"), 4),
                fmt_float(_score(rec, "precision_attack"), 4),
                fmt_float(_score(rec, "recall_attack"), 4),
                fmt_float(_score(rec, "f1_attack"), 4),
                fmt_float(_score(rec, "auc"), 4),
            ])
            rows.append([
                app.upper(), rec.get("Method") or rec.get("method") or "-", rec.get("Model") or rec.get("model") or "-",
                natural, balanced, cv,
                fmt_int(rec.get("train_features") or rec.get("feature_count") or rec.get("features")),
                shorten(f"{fmt_int(rec.get('train_rows'))}/{fmt_int(rec.get('natural_test_rows') or rec.get('test_rows'))}", 45),
            ])
    if len(rows) == 1:
        rows.append(["-", "-", "No result rows found", "-", "-", "-", "-", "-"])
    return make_table(rows, styles, col_widths=[0.45*72,0.55*72,0.70*72,1.65*72,1.65*72,1.55*72,0.55*72,0.95*72], font_size=5.7)


def render(ctx, styles):
    story = []
    story.append(p("14. Final Evaluation Summary", styles.heading))
    story.append(p("Phase 14 consolidates the final model evidence chain. It is summary-driven and does not retrain models or reread raw EVE logs.", styles.body))

    rows = [["App", "Best method/model", "Selected by", "Natural F1/AUC", "Balanced F1/AUC", "CV F1/AUC"]]
    total_results = 0
    for app in ctx.selected_apps:
        s = _s(ctx, app)
        best = dict_value(s.get("best_model") or s.get("best"))
        total_results += len(list_value(s.get("results_table")))
        method = best.get("Method") or best.get("method") or s.get("best_method") or "-"
        model = best.get("Model") or best.get("model") or s.get("best_model_name") or "-"
        selected_by = dict_value(s.get("evaluation_policy")).get("best_model_selection") or s.get("best_metric") or "natural_holdout_f1_attack"
        rows.append([
            app.upper(),
            shorten(f"{method}/{model}", 45),
            shorten(selected_by, 45),
            _metric_pair(best, "natural_holdout_f1_attack", "natural_holdout_auc", "holdout_f1_attack", "holdout_auc"),
            _metric_pair(best, "balanced_holdout_f1_attack", "balanced_holdout_auc"),
            _metric_pair(best, "f1_attack", "auc"),
        ])
    story.append(metric_cards([
        ("Result rows", fmt_int(total_results), "loaded from Phase 13/14 summaries"),
        ("Primary metric", "Natural F1", "use for main claim"),
        ("Secondary metric", "Balanced F1/AUC", "separability check"),
        ("Best model", "Per app", "selected from available results"),
    ], styles, columns=4)); story.append(spacer())
    story.append(make_table(rows, styles, font_size=6.4)); story.append(spacer())

    story.append(p("14.1 Top Natural Holdout Results", styles.subheading)); story.append(_top(ctx, styles, "natural")); story.append(spacer())
    story.append(p("14.2 Top Balanced Holdout Results", styles.subheading)); story.append(_top(ctx, styles, "balanced")); story.append(spacer())
    story.append(p("14.3 Top Cross-validation Results", styles.subheading)); story.append(_top(ctx, styles, "cv")); story.append(spacer())

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
        story.append(p("14.4 Evaluation Figures", styles.subheading)); story.append(grid); story.append(spacer())

    story.append(note_box("Use natural holdout as the main claim. Balanced holdout is helpful to show separability, but it does not represent the real class distribution.", styles, title="Evaluation interpretation"))
    add_diagnostics(story, ctx, styles, 14)
    return story
