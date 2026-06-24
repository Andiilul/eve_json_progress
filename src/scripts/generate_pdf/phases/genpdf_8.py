
from __future__ import annotations
try:
    from ..context import counts_text, fmt_bytes, fmt_int, fmt_pct, safe_int, safe_float, shorten
    from ..style import p, spacer, make_table, metric_cards, note_box
    from ._genpdf_common import summary, dict_value, phase8_diag, pct, count_value, add_diagnostics
except Exception:
    from context import counts_text, fmt_bytes, fmt_int, fmt_pct, safe_int, safe_float, shorten
    from style import p, spacer, make_table, metric_cards, note_box
    from _genpdf_common import summary, dict_value, phase8_diag, pct, count_value, add_diagnostics

def render(ctx, styles):
    story=[]; story.append(p("8. Exported Dataset and Train/Test Split",styles.heading))
    story.append(p("Phase 8 is the first full materialization step. It writes train/test files and records the exact counts needed by visualization, correlation, feature selection, and model evaluation.",styles.body))
    total_rows=total_train=total_test=0
    for app in ctx.selected_apps:
        s=summary(ctx,app,8); total_rows+=safe_int(s.get('rows_written')); total_train+=safe_int(s.get('train_rows')); total_test+=safe_int(s.get('test_rows'))
    story.append(metric_cards([("Exported Rows",fmt_int(total_rows),"all selected apps"),("Train Rows",fmt_int(total_train),"group-hash split"),("Test Rows",fmt_int(total_test),"holdout split"),("Output", "train/test CSV", "feature-ready dataset")],styles,columns=4)); story.append(spacer())
    rows=[["App","Rows Exported","Train","Test","Features","Format","Corr Sample","Viz Sample"]]
    for app in ctx.selected_apps:
        s=summary(ctx,app,8)
        rows.append([app.upper(),fmt_int(s.get('rows_written')),fmt_int(s.get('train_rows')),fmt_int(s.get('test_rows')),fmt_int(s.get('feature_count')),str(s.get('output_format','-')),fmt_int(s.get('corr_leak_sample_rows')),fmt_int(s.get('visualization_sample_rows'))])
    story.append(p("8.1 Export Overview",styles.subheading)); story.append(make_table(rows,styles,font_size=7.0)); story.append(spacer())
    rows2=[["App","Raw Benign","Raw Attack","Raw Attack %","Final Benign","Final Attack","Final Attack %","Converted Benign"]]
    for app in ctx.selected_apps:
        d=phase8_diag(summary(ctx,app,8)); total=safe_int(summary(ctx,app,8).get('rows_written'))
        rows2.append([app.upper(),fmt_int(d.get('initial_benign_rows')),fmt_int(d.get('initial_attack_rows')),fmt_pct(d.get('initial_attack_pct'),2),fmt_int(d.get('refined_benign_rows')),fmt_int(d.get('refined_attack_rows')),fmt_pct(d.get('refined_attack_pct'),2),fmt_int(d.get('no_alert_refined_to_attack_rows'))])
    story.append(p("8.2 Raw vs Refined Label Counts",styles.subheading)); story.append(make_table(rows2,styles,font_size=6.8)); story.append(spacer())
    rows3=[["App","Split","Rows","Benign","Attack","Attack %","Target counts"]]
    for app in ctx.selected_apps:
        fs=dict_value(summary(ctx,app,8).get('file_class_summary'))
        for split in ('dataset_total','train','test'):
            one=dict_value(fs.get(split)); rows3.append([app.upper(),split,fmt_int(one.get('data_rows')),fmt_int(one.get('benign')),fmt_int(one.get('attack') or one.get('malicious')),pct(one.get('attack') or one.get('malicious'), one.get('data_rows')),counts_text(one.get('target_counts'),max_items=4)])
    story.append(p("8.3 Train/Test Distribution",styles.subheading)); story.append(make_table(rows3,styles,col_widths=[0.55*72,0.95*72,1.0*72,1.0*72,1.0*72,0.75*72,2.4*72],font_size=6.7)); story.append(spacer())
    rows4=[["App","Label source counts"]]
    for app in ctx.selected_apps:
        rows4.append([app.upper(), counts_text(summary(ctx,app,8).get('label_source_counts'), max_items=8)])
    story.append(p("8.4 Label Source Breakdown",styles.subheading)); story.append(make_table(rows4,styles,col_widths=[0.55*72,8.6*72],font_size=6.8)); story.append(spacer())
    story.append(note_box("Target_alert is the original alert baseline. Target_refined is the final modeling label. suspicious_probe_only is kept as evidence and should not be interpreted as malicious.",styles,title="Label interpretation"))
    add_diagnostics(story,ctx,styles,8,checks=[('conversion', lambda s,i: 'Label conversion exceeds configured cap.' if phase8_diag(s).get('conversion_limit_exceeded') else None)])
    return story
