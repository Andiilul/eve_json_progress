from __future__ import annotations

"""
Modular PDF report orchestrator.

This file should stay stable. Add new phase sections by creating:
    src/scripts/generate_pdf/phases/genpdf_N.py
with a function:
    render(ctx, styles) -> list[Flowable]

The orchestrator will auto-discover and call available genpdf_N modules.
"""

from dataclasses import dataclass
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Any, Optional
import argparse
import sys

# Make direct VSCode/Code Runner execution reliable. When this file is run
# directly, genpdf modules are imported as phases.genpdf_N and their fallback
# imports need both generate_pdf/ and generate_pdf/phases/ on sys.path.
try:
    _THIS_DIR = Path(__file__).resolve().parent
    for _p in (_THIS_DIR, _THIS_DIR / "phases"):
        _s = str(_p)
        if _s not in sys.path:
            sys.path.insert(0, _s)
except Exception:
    pass

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

try:
    from .context import build_context, default_output_pdf, fmt_seconds, shorten
    from .style import (
        PAGE_SIZE,
        LEFT_MARGIN,
        RIGHT_MARGIN,
        TOP_MARGIN,
        BOTTOM_MARGIN,
        build_styles,
        p,
        spacer,
        kv_table,
        make_table,
    )
except Exception:  # direct single-click run from this folder
    from context import build_context, default_output_pdf, fmt_seconds, shorten
    from style import (
        PAGE_SIZE,
        LEFT_MARGIN,
        RIGHT_MARGIN,
        TOP_MARGIN,
        BOTTOM_MARGIN,
        build_styles,
        p,
        spacer,
        kv_table,
        make_table,
    )


# ============================================================
# VSCode single-click defaults
# ============================================================
# "Single-click" in this project means: open this file in VSCode and press Run,
# without typing CLI arguments. Keep these defaults here so the report generator
# can be executed directly as a normal Python script.
DEFAULT_ARTIFACTS_DIR = Path("outputs_test")
DEFAULT_METRICS_JSON_DIRNAME = "metrics_json"
DEFAULT_REPORTS_DIRNAME = "reports"
DEFAULT_OUTPUT_FILENAME = "pipeline_report_single_click.pdf"
DEFAULT_PHASES = tuple(range(1, 15))


@dataclass(frozen=True)
class GeneratePDFConfig:
    artifacts_dir: Optional[Path] = None
    metrics_dir: Optional[Path] = None
    output_pdf: Optional[Path] = None
    title: str = "Suricata EVE Feature Engineering Pipeline Report"
    subtitle: str = "Modular report generated from outputs_test/metrics_json"
    phases: tuple[int, ...] = DEFAULT_PHASES



def _find_project_root() -> Path:
    """
    Resolve the project root for both execution styles:
    1. VSCode/Code Runner direct run of this file.
    2. Terminal run from the project root.

    Expected project shape:
        <root>/src/scripts/generate_pdf/generate_pdf.py
        <root>/outputs_test/metrics_json
    """
    candidates: list[Path] = []
    try:
        candidates.append(Path.cwd().resolve())
    except Exception:
        pass

    try:
        here = Path(__file__).resolve()
        candidates.extend(here.parents)
    except Exception:
        pass

    for base in candidates:
        if (base / "src" / "scripts" / "generate_pdf").exists():
            return base
        if (base / "src").exists() and (base / "outputs_test").exists():
            return base

    # Fallback: when this file is in src/scripts/generate_pdf, parents[3]
    # is normally the project root.
    try:
        here = Path(__file__).resolve()
        if len(here.parents) >= 4:
            return here.parents[3]
    except Exception:
        pass

    return Path.cwd().resolve()


def _resolve_project_path(path: Optional[Path], *, project_root: Optional[Path] = None) -> Optional[Path]:
    if path is None:
        return None
    path = Path(path)
    if path.is_absolute():
        return path
    root = project_root or _find_project_root()
    return root / path


def _default_artifacts_dir(project_root: Optional[Path] = None) -> Path:
    return _resolve_project_path(DEFAULT_ARTIFACTS_DIR, project_root=project_root) or DEFAULT_ARTIFACTS_DIR


def _default_metrics_dir(artifacts_dir: Path) -> Path:
    return artifacts_dir / DEFAULT_METRICS_JSON_DIRNAME


def _default_output_pdf(artifacts_dir: Path, run_id: Optional[str] = None) -> Path:
    reports_dir = artifacts_dir / DEFAULT_REPORTS_DIRNAME
    rid = str(run_id or "").strip()
    if rid:
        return reports_dir / f"pipeline_report_{rid}.pdf"
    return reports_dir / DEFAULT_OUTPUT_FILENAME

def _configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _safe_print(text: Any = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(str(text).encode("ascii", errors="replace").decode("ascii"))


def _import_phase_module(phase_num: int):
    module_name = f"genpdf_{int(phase_num)}"

    # Normal package execution: python -m src.scripts.generate_pdf.generate_pdf
    package = __package__
    if package:
        try:
            return import_module(f".{ 'phases' }.{module_name}", package=package)
        except ModuleNotFoundError:
            return None
        except Exception as exc:
            raise RuntimeError(f"Failed importing phases/{module_name}.py: {exc}") from exc

    # Direct execution from src/scripts/generate_pdf.
    try:
        return import_module(f"phases.{module_name}")
    except ModuleNotFoundError:
        return None
    except Exception as exc:
        raise RuntimeError(f"Failed importing phases/{module_name}.py: {exc}") from exc


def _build_cover(ctx, styles, cfg: GeneratePDFConfig) -> list[Any]:
    run = ctx.run_summary or {}
    story: list[Any] = []
    story.append(p(cfg.title, styles.title))
    story.append(p("Readable summary report focused on dataset counts, label refinement, visualization, feature quality, and model evaluation.", styles.subtitle))
    story.append(spacer(0.06))

    total_rows = 0
    total_attack = 0
    total_benign = 0
    try:
        from .phases._genpdf_common import app_label_counts
    except Exception:
        from phases._genpdf_common import app_label_counts
    for app in ctx.selected_apps:
        s1 = ctx.app_phase(app, 1).summary
        if isinstance(s1, dict):
            rows, benign, attack = app_label_counts(s1)
            total_rows += rows
            total_benign += benign
            total_attack += attack
    cards = [
        ("Selected Apps", ", ".join(ctx.selected_apps) if ctx.selected_apps else "-", None),
        ("Total Selected Rows", f"{total_rows:,}" if total_rows else "-", "from split summary / phase 1"),
        ("Initial Benign", f"{total_benign:,}" if total_benign else "-", "Target_alert=0 baseline"),
        ("Initial Attack", f"{total_attack:,}" if total_attack else "-", "Target_alert=1 baseline"),
    ]
    try:
        from .style import metric_cards
    except Exception:
        from style import metric_cards
    story.append(metric_cards(cards, styles, columns=4))
    story.append(spacer(0.08))

    rows = [
        ("Generated at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("Artifacts directory", str(ctx.artifacts_dir)),
        ("Metrics JSON directory", str(ctx.metrics_dir)),
        ("Run status", run.get("status") or ctx.pipeline_summary.get("status") or "-"),
        ("Run mode", run.get("run_mode") or ctx.pipeline_summary.get("run_mode") or "-"),
        ("Elapsed", fmt_seconds(run.get("elapsed_seconds") or ctx.pipeline_summary.get("elapsed_seconds"))),
    ]
    story.append(kv_table(rows, styles))
    story.append(spacer(0.08))
    story.append(p("Report layout note", styles.subheading))
    story.append(p("Phase 1 and Phase 2 are merged to reduce page waste. Artifact/path listings are intentionally hidden; the PDF focuses on results, counts, charts, feature lists, and audit diagnostics.", styles.body))
    story.append(PageBreak())
    return story

def build_story(cfg: GeneratePDFConfig) -> tuple[list[Any], Path]:
    ctx = build_context(
        artifacts_dir=cfg.artifacts_dir,
        metrics_dir=cfg.metrics_dir,
        output_pdf=cfg.output_pdf,
    )
    styles = build_styles()
    output_pdf = Path(cfg.output_pdf).resolve() if cfg.output_pdf else default_output_pdf(ctx)

    story: list[Any] = []
    story.extend(_build_cover(ctx, styles, cfg))

    rendered_any = False
    for phase_num in cfg.phases:
        module = _import_phase_module(phase_num)
        if module is None:
            continue
        render_fn = getattr(module, "render", None)
        if not callable(render_fn):
            raise AttributeError(f"phases/genpdf_{phase_num}.py exists but has no callable render(ctx, styles)")
        phase_story = render_fn(ctx, styles)
        if phase_story:
            if rendered_any:
                story.append(PageBreak())
            story.extend(phase_story)
            rendered_any = True

    if not rendered_any:
        story.append(p("No genpdf_N.py phase renderer was found.", styles.heading))
        story.append(p("Create src/scripts/generate_pdf/phases/genpdf_3.py or another phase renderer.", styles.body))

    return story, output_pdf


def generate_pdf(cfg: GeneratePDFConfig) -> Path:
    story, output_pdf = build_story(cfg)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_pdf),
        pagesize=PAGE_SIZE,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
        title=cfg.title,
        author="CBR / Suricata EVE Pipeline",
    )
    doc.build(story)
    return output_pdf


def _parse_phases(text: str | None) -> tuple[int, ...]:
    if not text:
        return tuple(range(1, 15))
    out: list[int] = []
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return tuple(dict.fromkeys(x for x in out if 1 <= x <= 14))


def parse_args(argv: Optional[list[str]] = None) -> GeneratePDFConfig:
    parser = argparse.ArgumentParser(
        description=(
            "Generate modular PDF report from metrics_json. "
            "Can be run directly from VSCode without CLI arguments."
        )
    )
    parser.add_argument("--artifacts", type=Path, default=None, help="Output/archive root, e.g. outputs_test")
    parser.add_argument("--metrics-json", type=Path, default=None, help="Central metrics dir, e.g. outputs_test/metrics_json")
    parser.add_argument("--output", "--out", dest="output", type=Path, default=None, help="Output PDF path")
    parser.add_argument("--run-id", type=str, default=None, help="Run ID used for default output filename")
    parser.add_argument("--phases", type=str, default=None, help="Phase list, e.g. 3 or 3,8,13 or 3-14")

    # parse_known_args keeps VSCode / pipeline wrappers from failing when they
    # pass harmless extra arguments. Known arguments still behave normally.
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        _safe_print(f"[generate_pdf] Ignoring unknown arguments: {' '.join(unknown)}")

    project_root = _find_project_root()

    artifacts_dir = _resolve_project_path(args.artifacts, project_root=project_root) if args.artifacts else _default_artifacts_dir(project_root)
    metrics_dir = _resolve_project_path(args.metrics_json, project_root=project_root) if args.metrics_json else _default_metrics_dir(artifacts_dir)

    if args.output:
        output_pdf = _resolve_project_path(args.output, project_root=project_root)
    else:
        output_pdf = _default_output_pdf(artifacts_dir, run_id=args.run_id)

    return GeneratePDFConfig(
        artifacts_dir=artifacts_dir,
        metrics_dir=metrics_dir,
        output_pdf=output_pdf,
        phases=_parse_phases(args.phases),
    )


def main(argv: Optional[list[str]] = None) -> int:
    _configure_console_encoding()
    cfg = parse_args(argv)
    _safe_print("=" * 72)
    _safe_print("Generate PDF Report")
    _safe_print("=" * 72)
    _safe_print(f"Artifacts : {cfg.artifacts_dir}")
    _safe_print(f"Metrics   : {cfg.metrics_dir}")
    _safe_print(f"Output    : {cfg.output_pdf}")
    _safe_print(f"Phases    : {','.join(str(x) for x in cfg.phases)}")
    _safe_print("=" * 72)
    out = generate_pdf(cfg)
    _safe_print(f"PDF generated: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
