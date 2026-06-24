from __future__ import annotations

try:
    from ..context import fmt_float, fmt_int, fmt_seconds, shorten, safe_int
    from ..style import p, spacer, make_table, metric_cards, note_box
    from ._genpdf_common import summary, dict_value, list_value, add_diagnostics
except Exception:
    from context import fmt_float, fmt_int, fmt_seconds, shorten, safe_int
    from style import p, spacer, make_table, metric_cards, note_box
    from _genpdf_common import summary, dict_value, list_value, add_diagnostics


def _s(ctx, app: str) -> dict:
    return summary(ctx, app, 13)


def _results(s: dict, key: str) -> list:
    candidates = {
        "natural": ["top_natural_holdout", "top_natural_results", "top_primary_holdout", "results_table"],
        "balanced": ["top_balanced_holdout", "top_balanced_results", "results_table"],
        "cv": ["top_cv", "top_cv_results", "results_table"],
    }.get(key, [key])
    for name in candidates:
        value = list_value(s.get(name))
        if value:
            return value
    return []


def _score(rec: dict, *names: str):
    for name in names:
        if rec.get(name) is not None:
            return rec.get(name)
    return None


def _result_table(ctx, styles, key: str):
    rows = [["App", "Method", "Model", "CV Acc/Prec/Rec/F1/AUC", "Natural Acc/Prec/Rec/F1/AUC", "Balanced Acc/Prec/Rec/F1/AUC", "Features", "Train/Test"]]
    for app in ctx.selected_apps:
        vals = _results(_s(ctx, app), key)
        # When results_table is the fallback, sort according to requested view.
        if key == "natural":
            vals = sorted([x for x in vals if isinstance(x, dict)], key=lambda r: float(r.get("natural_holdout_f1_attack") or r.get("holdout_f1_attack") or 0), reverse=True)
        elif key == "balanced":
            vals = sorted([x for x in vals if isinstance(x, dict)], key=lambda r: float(r.get("balanced_holdout_f1_attack") or 0), reverse=True)
        elif key == "cv":
            vals = sorted([x for x in vals if isinstance(x, dict)], key=lambda r: float(r.get("f1_attack") or 0), reverse=True)

        for rec in vals[:8]:
            if not isinstance(rec, dict):
                continue
            cv = "/".join([
                fmt_float(_score(rec, "accuracy"), 4),
                fmt_float(_score(rec, "precision_attack"), 4),
                fmt_float(_score(rec, "recall_attack"), 4),
                fmt_float(_score(rec, "f1_attack"), 4),
                fmt_float(_score(rec, "auc"), 4),
            ])
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
            rows.append([
                app.upper(),
                rec.get("method") or rec.get("Method") or "-",
                rec.get("model") or rec.get("Model") or "-",
                cv,
                natural,
                balanced,
                fmt_int(rec.get("train_features") or rec.get("feature_count") or rec.get("features")),
                shorten(f"{fmt_int(rec.get('train_rows'))}/{fmt_int(rec.get('natural_test_rows') or rec.get('test_rows'))}", 48),
            ])
    if len(rows) == 1:
        rows.append(["-", "-", "No result rows found", "-", "-", "-", "-", "-"])
    return make_table(rows, styles, col_widths=[0.45*72,0.55*72,0.70*72,1.55*72,1.70*72,1.70*72,0.55*72,1.05*72], font_size=5.8)


def render(ctx, styles):
    story = []
    story.append(p("13. Model Training and Holdout Evaluation", styles.heading))
    story.append(p("Phase 13 trains DT, RFC, LinearSVC, and XGBoost using Phase 12 feature sets. Natural-distribution holdout is the primary evaluation; balanced holdout is a secondary class-separability check.", styles.body))

    rows = [["App", "Train rows", "Natural test", "Balanced test", "Results", "Best natural", "Natural F1/AUC", "Time"]]
    total_results = 0
    for app in ctx.selected_apps:
        s = _s(ctx, app)
        best = dict_value(s.get("best_by_natural_holdout_f1") or s.get("best_by_preferred_metric"))
        total_results += safe_int(s.get("results_rows"), 0)
        rows.append([
            app.upper(),
            fmt_int(s.get("train_rows_loaded") or dict_value(s.get("train_sample_info")).get("sample_rows")),
            fmt_int(s.get("natural_test_rows_loaded") or dict_value(s.get("natural_test_sample_info")).get("sample_rows")),
            fmt_int(s.get("balanced_test_rows_loaded") or dict_value(s.get("balanced_test_sample_info")).get("sample_rows")),
            fmt_int(s.get("results_rows")),
            shorten(f"{best.get('Method', best.get('method', '-'))}/{best.get('Model', best.get('model', '-'))}", 42),
            f"{fmt_float(best.get('natural_holdout_f1_attack') or best.get('holdout_f1_attack'), 4)}/{fmt_float(best.get('natural_holdout_auc') or best.get('holdout_auc'), 4)}",
            fmt_seconds(s.get("seconds") or ctx.app_phase(app, 13).get("seconds")),
        ])
    story.append(metric_cards([
        ("Result rows", fmt_int(total_results), "model-method evaluations"),
        ("Primary holdout", "Natural", "main reported evaluation"),
        ("Secondary holdout", "Balanced", "class separability check"),
        ("Metrics", "Acc/Prec/Rec/F1/AUC", "attack-focused precision/recall/F1"),
    ], styles, columns=4)); story.append(spacer())
    story.append(make_table(rows, styles, font_size=6.4)); story.append(spacer())

    story.append(note_box("Metric order in the tables below is Accuracy / Precision_attack / Recall_attack / F1_attack / AUC. Natural holdout should be used as the main thesis claim.", styles, title="How to read Phase 13 metrics")); story.append(spacer(0.04))
    story.append(p("13.1 Top Natural Holdout Results", styles.subheading)); story.append(_result_table(ctx, styles, "natural")); story.append(spacer())
    story.append(p("13.2 Top Balanced Holdout Results", styles.subheading)); story.append(_result_table(ctx, styles, "balanced")); story.append(spacer())
    story.append(p("13.3 Top Cross-validation Results", styles.subheading)); story.append(_result_table(ctx, styles, "cv"))
    add_diagnostics(story, ctx, styles, 13)
    return story
