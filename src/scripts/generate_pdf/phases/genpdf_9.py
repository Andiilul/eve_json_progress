
from __future__ import annotations
try:
    from ..context import counts_text, fmt_int, shorten
    from ..style import p, spacer, make_table, image_grid, note_box
    from ._genpdf_common import summary, dict_value, add_diagnostics
except Exception:
    from context import counts_text, fmt_int, shorten
    from style import p, spacer, make_table, image_grid, note_box
    from _genpdf_common import summary, dict_value, add_diagnostics

PREFERRED = [
    'summary_overview',
    'initial_vs_refined_labels',
    'train_test_split',
    'label_source',
    'match_reason',
    'feature_group',
    'feature_availability',
    'numeric_overview_sample',
    'correlation_heatmap_sample',
]

def _figure_is_usable(info):
    if isinstance(info, dict):
        status = str(info.get('status') or '').strip().lower()
        if status in {'empty', 'skipped', 'unavailable', 'missing'}:
            return False
        return bool(info.get('path'))
    return bool(info)


def _figure_path(info):
    if isinstance(info, dict):
        return info.get('path')
    return info


def _figures(s):
    figs = s.get('figures') if isinstance(s.get('figures'),dict) else {}
    out=[]
    for name in PREFERRED:
        info=figs.get(name)
        if _figure_is_usable(info):
            out.append((name.replace('_',' ').title(), _figure_path(info)))
    for name,info in figs.items():
        if name in PREFERRED:
            continue
        if _figure_is_usable(info):
            out.append((str(name).replace('_',' ').title(), _figure_path(info)))
    return out

def render(ctx, styles):
    story=[]; story.append(p("9. Visualization",styles.heading))
    story.append(p("Phase 9 should be read visually. It uses Phase 8 aggregate counts and bounded samples, not raw JSONL or full train/test rereads. Charts that require verbose counters omitted from compact split_summary are intentionally skipped, not forced as empty figures.",styles.body))
    rows=[["App","Mode","Initial labels","Refined labels","Split counts","Label sources"]]
    for app in ctx.selected_apps:
        s=summary(ctx,app,9); rows.append([app.upper(),shorten(s.get('mode') or s.get('visualization_mode') or 'summary-driven',40),counts_text(s.get('initial_counts'),max_items=3),counts_text(s.get('refined_counts'),max_items=3),counts_text(s.get('split_counts'),max_items=4),counts_text(s.get('label_source_counts'),max_items=5)])
    story.append(make_table(rows,styles,col_widths=[0.55*72,1.1*72,1.7*72,1.7*72,1.7*72,2.7*72],font_size=6.3)); story.append(spacer())
    skipped = []
    for app in ctx.selected_apps:
        sf = summary(ctx, app, 9).get('skipped_figures')
        if isinstance(sf, dict):
            for name, info in sf.items():
                reason = info.get('reason') if isinstance(info, dict) else str(info)
                skipped.append((app.upper(), name.replace('_',' '), str(reason)))
    if skipped:
        story.append(note_box("Some optional Phase 9 charts were skipped because the compact split_summary intentionally does not store verbose event_type/app_proto/port histograms. This is expected and keeps split_summary small.", styles, title="Skipped optional charts")); story.append(spacer(0.04))
    any_img=False
    for app in ctx.selected_apps:
        figs=_figures(summary(ctx,app,9))
        grid=image_grid(figs[:8],styles,columns=2,max_height=2.35*72)
        if grid:
            story.append(p(f"9.{1 if not any_img else 2} {app.upper()} Visualization Figures",styles.subheading)); story.append(grid); story.append(spacer()); any_img=True
    if not any_img:
        story.append(note_box("No existing Phase 9 PNG files were found on this machine. The metrics include figure metadata, but the files must exist at the recorded paths for embedding. If the charts look weak, patch phase9_visualization.py next; otherwise genpdf_9.py is enough.",styles,title="Figure embedding note"))
    add_diagnostics(story,ctx,styles,9)
    return story
