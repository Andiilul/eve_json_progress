from __future__ import annotations

try:
    from ..context import counts_text, fmt_float, fmt_int, fmt_pct, shorten, safe_float, safe_int
    from ..style import p, spacer, make_table, metric_cards, note_box
    from ._genpdf_common import summary, dict_value, list_value, add_diagnostics, feature_grid
except Exception:
    from context import counts_text, fmt_float, fmt_int, fmt_pct, shorten, safe_float, safe_int
    from style import p, spacer, make_table, metric_cards, note_box
    from _genpdf_common import summary, dict_value, list_value, add_diagnostics, feature_grid


def _phase12_summary(ctx, app: str) -> dict:
    s = summary(ctx, app, 12)
    return s if isinstance(s, dict) else {}


def _feature_sets(s: dict) -> dict:
    fs = dict_value(s.get("feature_sets") or s.get("selected_feature_sets"))
    mi = list_value(fs.get("MI") or fs.get("mi") or fs.get("mi_selected") or fs.get("mi_selected_features"))
    rfe = list_value(fs.get("RFE") or fs.get("rfe") or fs.get("rfe_selected") or fs.get("rfe_selected_features"))

    intersection = list_value(
        fs.get("intersection_MI_RFE")
        or fs.get("intersection_mi_rfe")
        or fs.get("intersection")
        or fs.get("common")
    )
    union = list_value(
        fs.get("union_MI_RFE")
        or fs.get("union_mi_rfe")
        or fs.get("union")
        or fs.get("combined")
    )

    if not intersection and mi and rfe:
        rfe_set = set(str(x) for x in rfe)
        intersection = [str(x) for x in mi if str(x) in rfe_set]
    if not union and (mi or rfe):
        seen = set()
        union = []
        for x in [*mi, *rfe]:
            sx = str(x)
            if sx not in seen:
                seen.add(sx)
                union.append(sx)

    pca = dict_value(fs.get("PCA") or fs.get("pca"))
    return {"MI": [str(x) for x in mi], "RFE": [str(x) for x in rfe], "intersection": intersection, "union": union, "PCA": pca}


def _class_kept_requested(s: dict) -> str:
    sample_info = dict_value(s.get("sample_info"))
    kept = dict_value(sample_info.get("sample_kept_by_class"))
    req = dict_value(sample_info.get("requested_by_class"))
    if kept or req:
        return f"0: {fmt_int(kept.get('0'))}/{fmt_int(req.get('0'))}, 1: {fmt_int(kept.get('1'))}/{fmt_int(req.get('1'))}"

    rows = list_value(s.get("sample_class_summary"))
    pieces = []
    for rec in rows:
        if not isinstance(rec, dict):
            continue
        cls = str(rec.get("class") or "")
        if cls in {"0", "1"}:
            pieces.append(f"{cls}: {fmt_int(rec.get('kept_rows'))}/{fmt_int(rec.get('requested_rows'))}")
    return ", ".join(pieces) if pieces else "-"


def _safe_for_phase13(s: dict, fs: dict) -> str:
    q = dict_value(s.get("selection_quality_checks"))
    if "safe_for_phase13" in q:
        return "Yes" if bool(q.get("safe_for_phase13")) else "No"
    has_feature_set = bool(fs.get("MI")) and bool(fs.get("RFE"))
    has_pca = safe_int(s.get("pca_n_components") or dict_value(s.get("pca_meta")).get("n_components"), 0) > 0
    has_numeric = safe_int(s.get("numeric_features_used") or dict_value(s.get("prep_info")).get("numeric_features_used"), 0) > 0
    return "Yes" if has_feature_set and has_pca and has_numeric else "No"


def _overview_table(ctx, styles):
    rows = [["App", "Sample rows", "Class kept/requested", "Numeric features", "MI", "RFE", "Intersection", "Union", "PCA comp.", "Safe P13"]]
    for app in ctx.selected_apps:
        s = _phase12_summary(ctx, app)
        fs = _feature_sets(s)
        pca = dict_value(s.get("pca_meta") or s.get("pca_metadata") or fs.get("PCA"))
        rows.append([
            app.upper(),
            fmt_int(s.get("fs_sample_rows") or s.get("sample_rows") or dict_value(s.get("sample_info")).get("sample_rows")),
            _class_kept_requested(s),
            fmt_int(s.get("numeric_features_used") or dict_value(s.get("prep_info")).get("numeric_features_used")),
            fmt_int(s.get("mi_selected_n") or s.get("mi_selected_count") or len(fs.get("MI", []))),
            fmt_int(s.get("rfe_selected_n") or s.get("rfe_selected_count") or len(fs.get("RFE", []))),
            fmt_int(len(fs.get("intersection", []))),
            fmt_int(len(fs.get("union", []))),
            fmt_int(s.get("pca_n_components") or pca.get("n_components") or pca.get("components")),
            _safe_for_phase13(s, fs),
        ])
    return make_table(rows, styles, col_widths=[0.50*72, 0.78*72, 1.40*72, 0.85*72, 0.45*72, 0.45*72, 0.70*72, 0.55*72, 0.65*72, 0.60*72], font_size=6.3)


def _sampling_table(ctx, styles):
    rows = [["App", "Strategy", "Requested", "Requested/class", "Rows scanned", "Chunks", "Quota 0", "Quota 1", "MI method", "RFE method"]]
    for app in ctx.selected_apps:
        s = _phase12_summary(ctx, app)
        info = dict_value(s.get("sample_info"))
        quota = dict_value(info.get("quota_satisfied_by_class"))
        mi_info = dict_value(s.get("mi_info"))
        rfe_info = dict_value(s.get("rfe_info"))
        rows.append([
            app.upper(),
            s.get("fs_sampling_strategy") or info.get("sampling_strategy") or "-",
            fmt_int(s.get("fs_sample_rows_requested") or info.get("requested_total_rows")),
            fmt_int(s.get("fs_per_class_rows_requested") or info.get("requested_per_class_rows")),
            fmt_int(info.get("rows_scanned_from_train")),
            fmt_int(info.get("chunks_read")),
            str(quota.get("0", "-")),
            str(quota.get("1", "-")),
            mi_info.get("method") or mi_info.get("status") or "-",
            rfe_info.get("method") or rfe_info.get("status") or "-",
        ])
    return make_table(rows, styles, col_widths=[0.50*72, 0.80*72, 0.75*72, 0.85*72, 0.90*72, 0.55*72, 0.55*72, 0.55*72, 1.15*72, 1.15*72], font_size=6.1)


def _pca_table(ctx, styles):
    rows = [["App", "Components", "Fit rows", "Features used", "Cumulative variance", "First EVR values"]]
    for app in ctx.selected_apps:
        s = _phase12_summary(ctx, app)
        fs = _feature_sets(s)
        pca = dict_value(s.get("pca_meta") or s.get("pca_metadata") or fs.get("PCA"))
        evr = list_value(pca.get("explained_variance_ratio"))
        evr_txt = ", ".join(fmt_float(x, 4) for x in evr[:8]) if evr else "-"
        cv = pca.get("cumulative_variance", s.get("pca_cumulative_variance"))
        cv_float = safe_float(cv, None)
        cv_text = "-" if cv_float is None else fmt_pct(cv_float * 100.0 if cv_float <= 1 else cv_float, 2)
        rows.append([
            app.upper(),
            fmt_int(pca.get("n_components") or s.get("pca_n_components")),
            fmt_int(pca.get("fit_rows")),
            fmt_int(len(list_value(pca.get("feature_columns")))),
            cv_text,
            evr_txt,
        ])
    return make_table(rows, styles, col_widths=[0.55*72, 0.75*72, 0.75*72, 0.85*72, 1.0*72, 4.3*72], font_size=6.3)


def _add_feature_set_block(story, styles, app: str, label: str, features: list[str]) -> None:
    story.append(p(f"{app.upper()} - {label} ({len(features)} features)", styles.subheading))
    if features:
        # max_items deliberately above expected feature-set size so no selected feature is hidden.
        story.append(feature_grid(features, styles, title=f"{app.upper()} {label}", max_items=200))
    else:
        story.append(p("No features found in Phase 12 metrics for this set.", styles.body))
    story.append(spacer(0.035))


def render(ctx, styles):
    story = []
    story.append(p("12. Feature Selection", styles.heading))
    story.append(p(
        "Phase 12 performs train-only feature selection using a bounded balanced sample. It compares MI, RFE, and PCA without reading raw EVE logs or the test split.",
        styles.body,
    ))

    cards = []
    total_sample = 0
    total_mi = 0
    total_rfe = 0
    for app in ctx.selected_apps:
        s = _phase12_summary(ctx, app)
        fs = _feature_sets(s)
        total_sample += safe_int(s.get("fs_sample_rows") or dict_value(s.get("sample_info")).get("sample_rows"), 0)
        total_mi += len(fs.get("MI", []))
        total_rfe += len(fs.get("RFE", []))
    cards.extend([
        ("Total FS sample", fmt_int(total_sample), "balanced train-only sample"),
        ("MI selected", fmt_int(total_mi), "sum across selected apps"),
        ("RFE selected", fmt_int(total_rfe), "sum across selected apps"),
        ("PCA components/app", "30", "from current metrics"),
    ])
    story.append(metric_cards(cards, styles, columns=4)); story.append(spacer())

    story.append(p("12.1 Feature Selection Overview", styles.subheading))
    story.append(_overview_table(ctx, styles)); story.append(spacer())

    story.append(p("12.2 Sampling and Method Audit", styles.subheading))
    story.append(_sampling_table(ctx, styles)); story.append(spacer())

    story.append(p("12.3 Full Selected Feature Sets", styles.subheading))
    story.append(note_box(
        "The lists below are intentionally not truncated. Intersection = features selected by both MI and RFE. Union = combined MI/RFE feature set after de-duplication.",
        styles,
        title="How to read selected features",
    ))
    story.append(spacer(0.035))
    for app in ctx.selected_apps:
        fs = _feature_sets(_phase12_summary(ctx, app))
        _add_feature_set_block(story, styles, app, "MI selected", fs.get("MI", []))
        _add_feature_set_block(story, styles, app, "RFE selected", fs.get("RFE", []))
        _add_feature_set_block(story, styles, app, "MI/RFE intersection", fs.get("intersection", []))
        _add_feature_set_block(story, styles, app, "MI/RFE union", fs.get("union", []))

    story.append(p("12.4 PCA Metadata", styles.subheading))
    story.append(_pca_table(ctx, styles)); story.append(spacer())

    add_diagnostics(story, ctx, styles, 12)
    return story
