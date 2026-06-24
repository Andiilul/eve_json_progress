
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
    'summary_overview','initial_vs_refined_labels','train_test_split','label_source',
    'event_type_initial','app_proto_initial','dest_port_initial','feature_group',
    'feature_availability','numeric_overview_sample','correlation_heatmap_sample'
]

def _figures(s):
    figs = s.get('figures') if isinstance(s.get('figures'),dict) else {}
    out=[]
    for name in PREFERRED:
        info=figs.get(name)
        if isinstance(info,dict):
            out.append((name.replace('_',' ').title(), info.get('path')))
        elif info:
            out.append((name.replace('_',' ').title(), info))
    for name,info in figs.items():
        if name in PREFERRED: continue
        if isinstance(info,dict): out.append((str(name).replace('_',' ').title(), info.get('path')))
        else: out.append((str(name).replace('_',' ').title(), info))
    return out

def render(ctx, styles):
    story=[]; story.append(p("9. Visualization",styles.heading))
    story.append(p("Phase 9 should be read visually. It uses Phase 8 aggregate counts and bounded samples, not raw JSONL or full train/test rereads.",styles.body))
    rows=[["App","Mode","Initial labels","Refined labels","Split counts","Label sources"]]
    for app in ctx.selected_apps:
        s=summary(ctx,app,9); rows.append([app.upper(),shorten(s.get('mode') or s.get('visualization_mode') or 'summary-driven',40),counts_text(s.get('initial_counts'),max_items=3),counts_text(s.get('refined_counts'),max_items=3),counts_text(s.get('split_counts'),max_items=4),counts_text(s.get('label_source_counts'),max_items=5)])
    story.append(make_table(rows,styles,col_widths=[0.55*72,1.1*72,1.7*72,1.7*72,1.7*72,2.7*72],font_size=6.3)); story.append(spacer())
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
