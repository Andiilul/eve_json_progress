
from __future__ import annotations
try:
    from ..context import counts_text, fmt_int, safe_int
    from ..style import p, spacer, make_table, metric_cards
    from ._genpdf_common import summary, add_diagnostics
except Exception:
    from context import counts_text, fmt_int, safe_int
    from style import p, spacer, make_table, metric_cards
    from _genpdf_common import summary, add_diagnostics

def render(ctx, styles):
    story=[]; story.append(p("5. Feature Engineering Manifest",styles.heading))
    story.append(p("Phase 5 defines the base feature schema and feature groups. It does not materialize the full dataset; Phase 8 performs streaming materialization.",styles.body))
    rows=[["App","Total features","Training candidates","Audit / leakage cols","Dataset output","Feature groups"]]
    total_feat=0
    for app in ctx.selected_apps:
        s=summary(ctx,app,5); total_feat += safe_int(s.get('feature_count') or s.get('features'))
        rows.append([app.upper(),fmt_int(s.get('feature_count') or s.get('features')),fmt_int(s.get('training_candidate_count') or s.get('training_candidates')),fmt_int(s.get('audit_or_leakage_count') or s.get('audit_leakage_columns')),str(bool(s.get('dataset_output_written') or s.get('dataset_output'))),counts_text(s.get('feature_group_counts') or s.get('feature_groups'),max_items=10)])
    story.append(metric_cards([("Base Features",fmt_int(total_feat),"before computed features"),("Dataset Output","No","policy/schema only"),("Used Later","Phase 8","full streaming export"),("Scope","HTTP/TLS","selected apps")],styles,columns=4)); story.append(spacer())
    story.append(make_table(rows,styles,col_widths=[0.55*72,0.9*72,1.1*72,1.1*72,0.9*72,5.5*72],font_size=6.8))
    add_diagnostics(story,ctx,styles,5)
    return story
