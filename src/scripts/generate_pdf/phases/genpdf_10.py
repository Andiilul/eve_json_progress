
from __future__ import annotations
try:
    from ..context import counts_text, fmt_float, fmt_int, fmt_seconds, safe_int, shorten
    from ..style import p, spacer, make_table, image_grid, note_box
    from ._genpdf_common import summary, dict_value, list_value, add_diagnostics, feature_list_from_summary, feature_grid
except Exception:
    from context import counts_text, fmt_float, fmt_int, fmt_seconds, safe_int, shorten
    from style import p, spacer, make_table, image_grid, note_box
    from _genpdf_common import summary, dict_value, list_value, add_diagnostics, feature_list_from_summary, feature_grid

def _top_table(ctx,styles,key,title):
    rows=[["App","Rank","Feature","Corr","Abs Corr","N","Unique"]]
    for app in ctx.selected_apps:
        vals=list_value(summary(ctx,app,10).get(key))
        if not vals: rows.append([app.upper(),'-',f'No {title} data','-','-','-','-']); continue
        for i,rec in enumerate(vals[:15],1):
            if not isinstance(rec,dict): continue
            rows.append([app.upper(),i,shorten(rec.get('Feature') or rec.get('feature'),70),fmt_float(rec.get('Correlation') or rec.get('correlation'),4),fmt_float(rec.get('Abs_Corr') or rec.get('abs_correlation'),4),fmt_int(rec.get('N') or rec.get('n')),fmt_int(rec.get('Unique') or rec.get('unique'))])
    return make_table(rows,styles,col_widths=[0.5*72,0.38*72,3.4*72,0.65*72,0.7*72,0.8*72,0.75*72],font_size=6.4)

def render(ctx, styles):
    story=[]; story.append(p("10. Correlation and Leakage Analysis",styles.heading))
    story.append(p("Phase 10 reports target correlation twice: ALL numeric features for leakage diagnosis, then NO-LEAK features for modeling-safe interpretation.",styles.body))
    rows=[["App","Rows used","Target","ALL numeric","NO-LEAK numeric","Leakage removed","Target sample","Time"]]
    for app in ctx.selected_apps:
        s=summary(ctx,app,10); fc=dict_value(s.get('feature_counts'))
        rows.append([app.upper(),fmt_int(s.get('rows_used') or s.get('sample_rows')),s.get('target_column') or '-',fmt_int(s.get('all_features') or fc.get('numeric_features_all')),fmt_int(s.get('no_leak_features') or fc.get('numeric_features_noleak')),fmt_int(s.get('leakage_removed') or fc.get('drop_columns_count')),counts_text(s.get('target_counts_sample'),max_items=4),fmt_seconds(s.get('seconds') or ctx.app_phase(app,10).get('seconds'))])
    story.append(make_table(rows,styles,font_size=6.6)); story.append(spacer())
    story.append(p("10.1 Top 15 Correlations - ALL Features",styles.subheading)); story.append(_top_table(ctx,styles,'top_correlations_all','ALL')); story.append(spacer())
    story.append(p("10.2 Top 15 Correlations - NO-LEAK Features",styles.subheading)); story.append(_top_table(ctx,styles,'top_correlations_noleak','NO-LEAK')); story.append(spacer())
    imgs=[]
    for app in ctx.selected_apps:
        out=dict_value(summary(ctx,app,10).get('outputs'))
        imgs.append((f'{app.upper()} Top ALL Correlation', out.get('top_all_png')))
        imgs.append((f'{app.upper()} Top NO-LEAK Correlation', out.get('top_noleak_png')))
    grid=image_grid(imgs,styles,columns=2,max_height=2.4*72)
    if grid:
        story.append(p("10.3 Correlation Bar Charts",styles.subheading)); story.append(grid); story.append(spacer())
    rows2=[["App","Feature A","Feature B","Corr","Abs Corr"]]
    for app in ctx.selected_apps:
        vals=list_value(summary(ctx,app,10).get('redundant_pairs_top'))
        for rec in vals[:10]:
            if isinstance(rec,dict): rows2.append([app.upper(),shorten(rec.get('feature_a'),45),shorten(rec.get('feature_b'),45),fmt_float(rec.get('correlation'),4),fmt_float(rec.get('abs_correlation'),4)])
    if len(rows2)>1:
        story.append(p("10.4 Redundant NO-LEAK Feature Pairs",styles.subheading)); story.append(make_table(rows2,styles,col_widths=[0.5*72,3.1*72,3.1*72,0.7*72,0.7*72],font_size=6.4)); story.append(spacer())
    for app in ctx.selected_apps:
        feats=feature_list_from_summary(summary(ctx,app,10)) or feature_list_from_summary(summary(ctx,app,11)) or feature_list_from_summary(summary(ctx,app,7))
        if feats:
            story.append(p(f"10.5 Full Modeling Feature List - {app.upper()} ({len(feats)} features)",styles.subheading)); story.append(feature_grid(feats,styles,title='features',max_items=90)); story.append(spacer())
    add_diagnostics(story,ctx,styles,10)
    return story
