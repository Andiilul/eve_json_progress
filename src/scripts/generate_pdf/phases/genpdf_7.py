
from __future__ import annotations
try:
    from ..context import counts_text, fmt_int, safe_int
    from ..style import p, spacer, make_table, metric_cards
    from ._genpdf_common import summary, add_diagnostics, feature_list_from_summary, feature_grid
except Exception:
    from context import counts_text, fmt_int, safe_int
    from style import p, spacer, make_table, metric_cards
    from _genpdf_common import summary, add_diagnostics, feature_list_from_summary, feature_grid

def render(ctx, styles):
    story=[]; story.append(p("7. Cleaning and Leakage Policy",styles.heading))
    story.append(p("Phase 7 freezes the cleaning policy, leakage drop list, and modeling-safe feature contract used by later correlation, feature selection, and training phases.",styles.body))
    rows=[["App","Schema cols","Dropped cols","Approved low-risk","Medium review","Rejected","Modeling candidates"]]
    total_model=0
    for app in ctx.selected_apps:
        s=summary(ctx,app,7); total_model += safe_int(s.get('modeling_feature_count') or s.get('approved_low_risk_count'))
        rows.append([app.upper(),fmt_int(s.get('schema_columns') or s.get('schema_cols')),fmt_int(s.get('drop_columns_count') or s.get('drop_cols')),fmt_int(s.get('approved_low_risk_count') or s.get('approved_low_risk')),fmt_int(s.get('medium_review_count') or s.get('medium_review')),fmt_int(s.get('rejected_count') or s.get('rejected')),fmt_int(s.get('modeling_feature_count') or s.get('training_feature_count'))])
    story.append(metric_cards([("Modeling Candidates",fmt_int(total_model),"before Phase 10 screening"),("Leakage Policy","Applied","alert/label shortcuts removed"),("Output Type","Policy only","no full dataset copy"),("Next","Phase 8/10","export + corr audit")],styles,columns=4)); story.append(spacer())
    story.append(make_table(rows,styles,font_size=7.0)); story.append(spacer())
    rows2=[["App","Schema groups","Schema sources"]]
    for app in ctx.selected_apps:
        s=summary(ctx,app,7); rows2.append([app.upper(),counts_text(s.get('schema_group_counts') or s.get('schema_groups'),max_items=12),counts_text(s.get('schema_source_counts') or s.get('schema_sources'),max_items=8)])
    story.append(p("7.1 Feature Group Audit",styles.subheading)); story.append(make_table(rows2,styles,col_widths=[0.55*72,6.0*72,3.0*72],font_size=6.5))
    add_diagnostics(story,ctx,styles,7)
    return story
