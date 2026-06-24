
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
    story=[]; story.append(p("6. Computed Feature Rules",styles.heading))
    story.append(p("Phase 6 defines derived features such as traffic rates, ratios, log transforms, port flags, time features, IP/subnet indicators, and interaction features.",styles.body))
    rows=[["App","Rules","Training-candidate rules","High leakage rules","Rule groups"]]
    total_rules=0
    for app in ctx.selected_apps:
        s=summary(ctx,app,6); total_rules += safe_int(s.get('rule_count') or s.get('rules'))
        rows.append([app.upper(),fmt_int(s.get('rule_count') or s.get('rules')),fmt_int(s.get('training_candidate_rules') or s.get('training_candidate_rule_count')),fmt_int(s.get('high_leakage_rules') or s.get('high_leakage_rule_count')),counts_text(s.get('rule_group_counts') or s.get('rule_groups'),max_items=12)])
    story.append(metric_cards([("Computed Rules",fmt_int(total_rules),"feature construction"),("Full Dataset","Not here","applied in Phase 8"),("Core Groups","rate / ratio / port","metadata-derived"),("Payload","Not used","metadata only")],styles,columns=4)); story.append(spacer())
    story.append(make_table(rows,styles,col_widths=[0.55*72,0.8*72,1.35*72,1.1*72,6.1*72],font_size=6.8))
    add_diagnostics(story,ctx,styles,6)
    return story
