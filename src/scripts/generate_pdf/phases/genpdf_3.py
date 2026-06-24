
from __future__ import annotations
from typing import Any
try:
    from ..context import counts_text, fmt_float, fmt_int, fmt_seconds, shorten, safe_int
    from ..style import p, spacer, make_table, metric_cards
    from ._genpdf_common import summary, dict_value, add_diagnostics
except Exception:
    from context import counts_text, fmt_float, fmt_int, fmt_seconds, shorten, safe_int
    from style import p, spacer, make_table, metric_cards
    from _genpdf_common import summary, dict_value, add_diagnostics


def render(ctx, styles) -> list[Any]:
    story=[]
    story.append(p("3. Probing Analysis", styles.heading))
    story.append(p("Phase 3 scans each selected application and aggregates source-IP behavior per 5-minute window. This phase produces evidence only; it does not change labels.", styles.body))
    rows=[["App","Rows scanned","Probe windows","Suspicious windows","Alert IP windows","Base alert rows","Time"]]
    total_windows=total_susp=0
    for app in ctx.selected_apps:
        s=summary(ctx,app,3); total_windows += safe_int(s.get('probe_windows')); total_susp += safe_int(s.get('suspicious_windows'))
        rows.append([app.upper(), fmt_int(s.get('rows_scanned') or s.get('decoded_events')), fmt_int(s.get('probe_windows')), fmt_int(s.get('suspicious_windows')), fmt_int(s.get('alert_ip_windows')), fmt_int(s.get('base_alert_positive_rows')), fmt_seconds(s.get('seconds') or ctx.app_phase(app,3).get('seconds'))])
    story.append(metric_cards([("Probe Windows", fmt_int(total_windows), "source-IP/time windows"), ("Suspicious Windows", fmt_int(total_susp), "evidence only"), ("Window Size", "5 min", "configured probing window"), ("Label Effect", "0 rows", "Phase 3 never changes labels")], styles, columns=4)); story.append(spacer())
    story.append(p("3.1 Execution Summary", styles.subheading)); story.append(make_table(rows,styles,font_size=7.1)); story.append(spacer())
    rows2=[["App","No-alert p90","No-alert p95","No-alert p99","With-alert p95","Max score"]]
    for app in ctx.selected_apps:
        no=dict_value(dict_value(summary(ctx,app,3).get('probe_score_stats')).get('probe_score_no_alert'))
        wa=dict_value(dict_value(summary(ctx,app,3).get('probe_score_stats')).get('probe_score_with_alert'))
        rows2.append([app.upper(),fmt_float(no.get('p90'),4),fmt_float(no.get('p95'),4),fmt_float(no.get('p99'),4),fmt_float(wa.get('p95'),4),fmt_float(max(no.get('max',0) or 0, wa.get('max',0) or 0),4)])
    story.append(p("3.2 Probe Score Percentiles", styles.subheading)); story.append(make_table(rows2,styles,font_size=7.0)); story.append(spacer())
    rows3=[["App","Top event types","Top app_proto","Top destination ports"]]
    for app in ctx.selected_apps:
        s=summary(ctx,app,3)
        rows3.append([app.upper(), counts_text(s.get('event_type_counts_top') or s.get('top_event_type') or s.get('event_type_counts'), max_items=6), counts_text(s.get('app_proto_counts_top') or s.get('top_app_proto') or s.get('app_proto_counts'), max_items=6), counts_text(s.get('dest_port_counts_top') or s.get('top_dest_port') or s.get('dest_port_counts'), max_items=8)])
    story.append(p("3.3 Dominant Traffic Distributions", styles.subheading)); story.append(make_table(rows3,styles,col_widths=[0.55*72,3.1*72,3.1*72,3.6*72],font_size=6.5))
    add_diagnostics(story,ctx,styles,3,checks=[('zero_windows', lambda s,i: 'No probe windows found.' if safe_int(s.get('probe_windows'))<=0 else None)])
    return story
