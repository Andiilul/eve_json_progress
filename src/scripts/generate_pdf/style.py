
from __future__ import annotations

"""ReportLab style and flowable helpers for the redesigned modular report."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, KeepTogether, Paragraph, Spacer, Table, TableStyle


PAGE_SIZE = landscape(A4)
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE
LEFT_MARGIN = 0.42 * inch
RIGHT_MARGIN = 0.42 * inch
TOP_MARGIN = 0.38 * inch
BOTTOM_MARGIN = 0.38 * inch
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN


@dataclass(frozen=True)
class StyleTheme:
    navy: str = "#183247"
    blue: str = "#2563eb"
    cyan: str = "#0891b2"
    teal: str = "#0f9f8f"
    green: str = "#16a34a"
    orange: str = "#f59e0b"
    purple: str = "#7c3aed"
    red: str = "#dc2626"
    title_color: str = "#183247"
    heading_color: str = "#183247"
    subheading_color: str = "#1f4e79"
    text_color: str = "#16202a"
    muted_color: str = "#64748b"
    header_bg: str = "#183247"
    header_fg: str = "#ffffff"
    grid_color: str = "#d6dde5"
    soft_bg: str = "#f5f8fb"
    soft_blue: str = "#eaf2ff"
    soft_green: str = "#eaf7ef"
    soft_orange: str = "#fff5df"
    soft_purple: str = "#f3edff"
    warning_bg: str = "#fff8e8"
    warning_border: str = "#d97706"


class ReportStyles:
    def __init__(self, theme: Optional[StyleTheme] = None):
        self.theme = theme or StyleTheme()
        base = getSampleStyleSheet()
        self.title = ParagraphStyle(
            "CBRTitle", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=23, leading=27, textColor=colors.HexColor(self.theme.title_color),
            alignment=TA_CENTER, spaceAfter=8,
        )
        self.subtitle = ParagraphStyle(
            "CBRSubtitle", parent=base["BodyText"], fontName="Helvetica",
            fontSize=10.8, leading=13, textColor=colors.HexColor(self.theme.muted_color),
            alignment=TA_CENTER, spaceAfter=10,
        )
        self.heading = ParagraphStyle(
            "CBRHeading", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=15.5, leading=18.5, textColor=colors.HexColor(self.theme.heading_color),
            spaceBefore=4, spaceAfter=7,
        )
        self.subheading = ParagraphStyle(
            "CBRSubheading", parent=base["Heading3"], fontName="Helvetica-Bold",
            fontSize=11.4, leading=13.5, textColor=colors.HexColor(self.theme.subheading_color),
            spaceBefore=6, spaceAfter=4,
        )
        self.body = ParagraphStyle(
            "CBRBody", parent=base["BodyText"], fontName="Helvetica",
            fontSize=9.5, leading=12.2, textColor=colors.HexColor(self.theme.text_color),
            alignment=TA_LEFT, spaceAfter=5,
        )
        self.small = ParagraphStyle(
            "CBRSmall", parent=base["BodyText"], fontName="Helvetica",
            fontSize=8.0, leading=9.8, textColor=colors.HexColor(self.theme.text_color),
            spaceAfter=2,
        )
        self.tiny = ParagraphStyle(
            "CBRTiny", parent=base["BodyText"], fontName="Helvetica",
            fontSize=6.7, leading=8.0, textColor=colors.HexColor(self.theme.text_color),
            spaceAfter=1,
        )
        self.card_label = ParagraphStyle(
            "CBRCardLabel", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=7.2, leading=8.4, textColor=colors.HexColor(self.theme.muted_color),
            alignment=TA_CENTER,
        )
        self.card_value = ParagraphStyle(
            "CBRCardValue", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=13.2, leading=15.2, textColor=colors.HexColor(self.theme.navy),
            alignment=TA_CENTER,
        )
        self.caption = ParagraphStyle(
            "CBRCaption", parent=base["BodyText"], fontName="Helvetica-Oblique",
            fontSize=7.8, leading=9.2, textColor=colors.HexColor(self.theme.muted_color),
            alignment=TA_CENTER, spaceAfter=4,
        )


def build_styles() -> ReportStyles:
    return ReportStyles()


def escape(text: Any) -> str:
    s = str(text if text is not None else "-")
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def p(text: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def spacer(height: float = 0.055) -> Spacer:
    return Spacer(1, float(height) * inch)


def _is_flowable(value: Any) -> bool:
    return hasattr(value, "wrap") and hasattr(value, "drawOn")


def _theme_color(name: str) -> str:
    theme = StyleTheme()
    return getattr(theme, name, name)


def table_style(*, font_size: float = 7.0, header_bg: str | None = None, zebra: bool = True) -> TableStyle:
    theme = StyleTheme()
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg or theme.header_bg)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(theme.header_fg)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), float(font_size)),
        ("LEADING", (0, 0), (-1, -1), float(font_size) + 1.9),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor(theme.grid_color)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if zebra:
        commands.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(theme.soft_bg)]))
    return TableStyle(commands)


def plain_table_style(*, font_size: float = 7.0) -> TableStyle:
    theme = StyleTheme()
    return TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), float(font_size)),
        ("LEADING", (0, 0), (-1, -1), float(font_size) + 1.8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor(theme.grid_color)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])


def make_table(
    rows: list[list[Any]],
    styles: ReportStyles,
    *,
    col_widths: Optional[list[float]] = None,
    font_size: float = 7.0,
    repeat_rows: int = 1,
    plain: bool = False,
    header_bg: str | None = None,
) -> Table:
    if not rows:
        rows = [["No data"]]
    converted: list[list[Any]] = []
    for r, row in enumerate(rows):
        out: list[Any] = []
        for cell in row:
            if _is_flowable(cell):
                out.append(cell)
            elif r == 0 and repeat_rows:
                out.append(str(cell if cell is not None else "-"))
            else:
                out.append(p(cell, styles.small if font_size >= 7.4 else styles.tiny))
        converted.append(out)
    tbl = Table(converted, colWidths=col_widths, repeatRows=repeat_rows, hAlign="LEFT")
    tbl.setStyle(plain_table_style(font_size=font_size) if plain else table_style(font_size=font_size, header_bg=header_bg))
    return tbl


def kv_table(rows: list[tuple[str, Any]], styles: ReportStyles, *, w1: float = 2.2 * inch, w2: float | None = None) -> Table:
    if w2 is None:
        w2 = CONTENT_WIDTH - w1
    return make_table([["Field", "Value"], *[[k, v] for k, v in rows]], styles, col_widths=[w1, w2], font_size=7.4)


def warning_table(warnings: list[tuple[str, Any]], styles: ReportStyles) -> Table:
    theme = StyleTheme()
    rows = [["Scope", "Warning"], *[[scope, text] for scope, text in warnings]]
    tbl = make_table(rows, styles, col_widths=[1.20 * inch, CONTENT_WIDTH - 1.20 * inch], font_size=7.0, header_bg=theme.warning_border)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor(theme.warning_bg)),
    ]))
    return tbl


def section_banner(title: str, subtitle: str | None, styles: ReportStyles, *, color: str = "#183247") -> Table:
    body = [p(title, styles.heading)]
    if subtitle:
        body.append(p(subtitle, styles.body))
    tbl = Table([[body]], colWidths=[CONTENT_WIDTH], hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f6fc")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(color)),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tbl


def metric_cards(cards: list[tuple[str, Any, str | None]], styles: ReportStyles, *, columns: int = 4) -> Table:
    theme = StyleTheme()
    bg_cycle = [theme.soft_blue, theme.soft_green, theme.soft_orange, theme.soft_purple]
    cells: list[Any] = []
    for idx, (label, value, note) in enumerate(cards):
        content = [p(value, styles.card_value), p(label, styles.card_label)]
        if note:
            content.append(p(note, styles.tiny))
        box = Table([[content]], colWidths=[(CONTENT_WIDTH / columns) - 8])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg_cycle[idx % len(bg_cycle)])),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(theme.grid_color)),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        cells.append(box)
    rows: list[list[Any]] = []
    for i in range(0, len(cells), columns):
        row = cells[i:i+columns]
        while len(row) < columns:
            row.append("")
        rows.append(row)
    tbl = Table(rows, colWidths=[CONTENT_WIDTH / columns] * columns, hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tbl


def note_box(text: str, styles: ReportStyles, *, title: str = "Note", color: str = "#2563eb") -> Table:
    body = [p(title, styles.subheading), p(text, styles.body)]
    tbl = Table([[body]], colWidths=[CONTENT_WIDTH], hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fbff")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(color)),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return tbl


def image_from_path(path: Any, *, max_width: float = CONTENT_WIDTH, max_height: float = 4.4 * inch) -> Image | None:
    if not path:
        return None
    pth = Path(str(path))
    try:
        if not pth.exists() or not pth.is_file():
            return None
        img = Image(str(pth))
        iw, ih = float(img.imageWidth or 1), float(img.imageHeight or 1)
        scale = min(max_width / iw, max_height / ih, 1.0)
        img.drawWidth = iw * scale
        img.drawHeight = ih * scale
        return img
    except Exception:
        return None


def image_grid(images: list[tuple[str, Any]], styles: ReportStyles, *, columns: int = 2, max_height: float = 2.6 * inch) -> Table | None:
    cells = []
    cell_w = CONTENT_WIDTH / columns - 8
    for title, path in images:
        img = image_from_path(path, max_width=cell_w, max_height=max_height)
        if img is None:
            continue
        cells.append([p(title, styles.caption), img])
    if not cells:
        return None
    box_cells: list[Any] = []
    for title_flow, img in cells:
        inner = Table([[title_flow], [img]], colWidths=[cell_w], hAlign="CENTER")
        inner.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.25, colors.HexColor(StyleTheme().grid_color)),
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        box_cells.append(inner)
    rows = []
    for i in range(0, len(box_cells), columns):
        row = box_cells[i:i+columns]
        while len(row) < columns:
            row.append("")
        rows.append(row)
    tbl = Table(rows, colWidths=[CONTENT_WIDTH / columns] * columns, hAlign="CENTER")
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl
