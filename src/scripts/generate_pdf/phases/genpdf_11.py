
from __future__ import annotations
try:
    from ..context import counts_text, fmt_int
    from ..style import p, spacer, make_table
    from ._genpdf_common import summary, add_diagnostics
except Exception:
    from context import counts_text, fmt_int
    from style import p, spacer, make_table
    from _genpdf_common import summary, add_diagnostics

def render(ctx,styles):
    story=[]; story.append(p("11. Modeling Readiness and Split Audit",styles.heading))
    story.append(p("Phase 11 verifies Phase 8 train/test outputs and freezes the no-leak modeling feature contract for Phase 12 and Phase 13.",styles.body))
    rows=[["App","Total rows","Train","Test","Modeling features","Dropped cols","Train/Test OK"]]
    for app in ctx.selected_apps:
        s=summary(ctx,app,11); rows.append([app.upper(),fmt_int(s.get('total_rows')),fmt_int(s.get('train_rows')),fmt_int(s.get('test_rows')),fmt_int(s.get('modeling_feature_count') or s.get('modeling_features')),fmt_int(s.get('drop_columns_count') or s.get('drop_cols')),f"{bool(s.get('train_exists',True))}/{bool(s.get('test_exists',True))}"])
    story.append(make_table(rows,styles,font_size=7.0)); story.append(spacer())
    rows2=[["App","Global target","Train target","Test target"]]
    for app in ctx.selected_apps:
        s=summary(ctx,app,11); rows2.append([app.upper(),counts_text(s.get('global_target_counts') or s.get('target_counts')),counts_text(s.get('train_target_counts')),counts_text(s.get('test_target_counts'))])
    story.append(make_table(rows2,styles,font_size=6.8)); add_diagnostics(story,ctx,styles,11); return story
