
from __future__ import annotations
from typing import Any
try:
    from ..context import counts_text, fmt_float, fmt_int, fmt_pct, fmt_seconds, safe_int, safe_float, shorten
    from ..style import p, spacer, make_table, metric_cards, note_box
    from ._genpdf_common import summary, dict_value, phase8_diag, pct, add_diagnostics
except Exception:
    from context import counts_text, fmt_float, fmt_int, fmt_pct, fmt_seconds, safe_int, safe_float, shorten
    from style import p, spacer, make_table, metric_cards, note_box
    from _genpdf_common import summary, dict_value, phase8_diag, pct, add_diagnostics


def render(ctx, styles) -> list[Any]:
    story=[]
    story.append(p("4. Label Refinement", styles.heading))
    story.append(p("Phase 4 builds conservative refinement keys from probing evidence. Final before/after row counts are taken from Phase 8 because Phase 8 is where row-level labels are materialized.", styles.body))
    rows=[["App","Raw Benign","Raw Attack","Refined Benign","Refined Attack","Converted Benign","Conversion %"]]
    total_converted=0
    for app in ctx.selected_apps:
        d=phase8_diag(summary(ctx,app,8)); s4=summary(ctx,app,4); guard=dict_value(s4.get('conversion_guard'))
        init_b=safe_int(d.get('initial_benign_rows') or guard.get('baseline_benign_rows'))
        init_a=safe_int(d.get('initial_attack_rows'))
        ref_b=safe_int(d.get('refined_benign_rows'))
        ref_a=safe_int(d.get('refined_attack_rows'))
        conv=safe_int(d.get('no_alert_refined_to_attack_rows') or guard.get('estimated_conversion_rows_after_guard'))
        total_converted += conv
        rows.append([app.upper(),fmt_int(init_b),fmt_int(init_a),fmt_int(ref_b),fmt_int(ref_a),fmt_int(conv),pct(conv,init_b)])
    story.append(metric_cards([("Converted Benign",fmt_int(total_converted),"Target_alert=0 -> Target_refined=1"),("Near Window", "Suspicious only", "not malicious"),("Extreme Probe", "Suspicious only", "not malicious"),("Main Target", "Target_refined", "final modeling label")],styles,columns=4)); story.append(spacer())
    story.append(p("4.1 Before vs After Refinement",styles.subheading)); story.append(make_table(rows,styles,font_size=7.1)); story.append(spacer())
    rows2=[["App","Policy","Same-window keys","Suspicious-only keys","Guard action","Cap","Time"]]
    for app in ctx.selected_apps:
        s=summary(ctx,app,4); guard=dict_value(s.get('conversion_guard'))
        rows2.append([app.upper(), s.get('active_refinement_policy') or 'strict/conservative', fmt_int(s.get('same_window_refined_keys')), fmt_int(s.get('suspicious_only_keys')), shorten(guard.get('guard_action') or '-',60), fmt_pct(guard.get('max_benign_conversion_pct') or s.get('max_benign_conversion_pct'),2), fmt_seconds(s.get('seconds') or ctx.app_phase(app,4).get('seconds'))])
    story.append(p("4.2 Refinement Policy Result",styles.subheading)); story.append(make_table(rows2,styles,font_size=7.0)); story.append(spacer())
    rows3=[["App","Same candidates","Near evidence-only","Target-change before guard","Selected same","Demoted / blocked"]]
    for app in ctx.selected_apps:
        s=summary(ctx,app,4); c=dict_value(s.get('candidate_counts_before_guard')); guard=dict_value(s.get('conversion_guard'))
        blocked = safe_int(guard.get('demoted_keys')) + safe_int(s.get('target_change_blocked_by_min_alert_count')) + safe_int(s.get('target_change_blocked_by_unknown_size')) + safe_int(s.get('target_change_blocked_by_per_key_cap'))
        rows3.append([app.upper(),fmt_int(c.get('same_window_candidate_keys')),fmt_int(c.get('near_window_candidate_keys') or s.get('near_window_evidence_only_keys')),fmt_int(c.get('target_change_candidate_keys')),fmt_int(s.get('same_window_refined_keys')),fmt_int(blocked)])
    story.append(p("4.3 Candidate Screening",styles.subheading)); story.append(make_table(rows3,styles,font_size=7.0)); story.append(spacer())
    story.append(note_box("Interpretation: Target_alert is the original Suricata alert baseline. Target_refined is a secondary, conservative refinement. suspicious_probe_only remains evidence and must not be read as malicious.", styles, title="How to read this phase"))
    add_diagnostics(story,ctx,styles,4)
    return story
