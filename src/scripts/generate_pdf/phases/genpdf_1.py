
from __future__ import annotations

"""Merged PDF section for Phase 1 + Phase 2."""

from typing import Any

try:
    from ..context import counts_text, fmt_bytes, fmt_int, fmt_pct, fmt_seconds, safe_int, safe_float, shorten
    from ..style import CONTENT_WIDTH, p, spacer, make_table, metric_cards, note_box
    from ._genpdf_common import summary, dict_value, app_label_counts, pct, add_diagnostics
except Exception:
    from context import counts_text, fmt_bytes, fmt_int, fmt_pct, fmt_seconds, safe_int, safe_float, shorten
    from style import CONTENT_WIDTH, p, spacer, make_table, metric_cards, note_box
    from _genpdf_common import summary, dict_value, app_label_counts, pct, add_diagnostics


def _app_rows(ctx, styles):
    rows = [["App", "Total Rows", "Benign", "Attack", "Attack %", "Input Size", "Ports / Match"]]
    for app in ctx.selected_apps:
        s1 = summary(ctx, app, 1)
        s2 = summary(ctx, app, 2)
        total, benign, attack = app_label_counts(s1)
        if total <= 0:
            total = safe_int(s2.get("rows") or s2.get("validated_rows"), 0)
        ports = s2.get("ports_used") or s2.get("ports") or s1.get("ports_used") or "-"
        rows.append([
            app.upper(), fmt_int(total), fmt_int(benign), fmt_int(attack), pct(attack, total),
            fmt_bytes(s1.get("input_size_bytes") or s1.get("input_file_size_bytes") or s2.get("input_size_bytes") or s2.get("input_file_size_bytes")),
            shorten(ports, 70),
        ])
    return make_table(rows, styles, col_widths=[0.55*72, 1.15*72, 1.15*72, 1.15*72, 0.75*72, 0.9*72, 2.9*72], font_size=7.2)


def _validation_rows(ctx, styles):
    rows = [["App", "Phase 2 status", "Validation", "Matched rows", "Match reasons", "Label mode"]]
    for app in ctx.selected_apps:
        s2 = summary(ctx, app, 2)
        s1 = summary(ctx, app, 1)
        rows.append([
            app.upper(), s2.get("status") or ctx.app_phase(app,2).status,
            s2.get("validation") or s2.get("validation_status") or "-",
            fmt_int(s2.get("rows") or s2.get("matched_rows") or s1.get("matched_rows") or s1.get("written_rows")),
            counts_text(s2.get("match_reason_counts") or s1.get("match_reason_counts"), max_items=4),
            shorten(dict_value(s1.get("label_policy")).get("label_mode") or s1.get("label_mode") or "event_type_or_valid_alert", 50),
        ])
    return make_table(rows, styles, col_widths=[0.55*72, 1.0*72, 1.0*72, 1.05*72, 3.1*72, 1.55*72], font_size=7.0)


def render(ctx, styles) -> list[Any]:
    story: list[Any] = []
    story.append(p("1. Dataset Loading and Application Split Summary", styles.heading))
    story.append(p("Phase 1 and Phase 2 are merged here. The report shows only the raw selected-app counts, initial benign/attack baseline, ports, and split validation. This avoids wasting separate pages for low-level validation details.", styles.body))

    total_rows = total_benign = total_attack = 0
    for app in ctx.selected_apps:
        total, benign, attack = app_label_counts(summary(ctx, app, 1))
        total_rows += total; total_benign += benign; total_attack += attack
    story.append(metric_cards([
        ("Total Selected Rows", fmt_int(total_rows), "HTTP + TLS selected data"),
        ("Initial Benign", fmt_int(total_benign), "before refinement"),
        ("Initial Attack", fmt_int(total_attack), "Suricata alert baseline"),
        ("Initial Attack Rate", pct(total_attack, total_rows), "Target_alert=1"),
    ], styles, columns=4))
    story.append(spacer(0.05))

    story.append(p("1.1 Application Counts", styles.subheading)); story.append(_app_rows(ctx, styles)); story.append(spacer(0.05))
    story.append(p("1.2 Split Validation", styles.subheading)); story.append(_validation_rows(ctx, styles)); story.append(spacer(0.05))
    story.append(note_box("Initial labels come from split_summary / Phase 1 and represent Target_alert. Label refinement is reviewed later using Target_refined; suspicious_probe_only is evidence only.", styles, title="Label note"))
    add_diagnostics(story, ctx, styles, 1)
    add_diagnostics(story, ctx, styles, 2)
    return story
