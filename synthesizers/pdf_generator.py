from __future__ import annotations

import os
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from agent.logging_setup import get_logger
from agent.models import BrandDNA

logger = get_logger(__name__)

PAGE_W, PAGE_H = A4
MARGIN = 2.2 * cm
BODY_W = PAGE_W - 2 * MARGIN

PALETTE_DARK = colors.HexColor("#1A1A1A")
PALETTE_MID = colors.HexColor("#4A4A4A")
PALETTE_LIGHT = colors.HexColor("#8A8A8A")
PALETTE_RULE = colors.HexColor("#D4D0CB")
PALETTE_ACCENT = colors.HexColor("#C8A882")
PALETTE_BG = colors.HexColor("#FAF9F7")


def _build_styles() -> dict:
    base = getSampleStyleSheet()
    styles = {}

    styles["cover_brand"] = ParagraphStyle(
        "cover_brand",
        fontSize=36,
        leading=42,
        textColor=PALETTE_DARK,
        fontName="Helvetica-Bold",
        spaceAfter=8,
    )
    styles["cover_subtitle"] = ParagraphStyle(
        "cover_subtitle",
        fontSize=11,
        leading=16,
        textColor=PALETTE_LIGHT,
        fontName="Helvetica",
        spaceAfter=4,
        tracking=60,
    )
    styles["section_header"] = ParagraphStyle(
        "section_header",
        fontSize=9,
        leading=12,
        textColor=PALETTE_ACCENT,
        fontName="Helvetica-Bold",
        spaceBefore=18,
        spaceAfter=6,
        tracking=120,
    )
    styles["heading2"] = ParagraphStyle(
        "heading2",
        fontSize=16,
        leading=22,
        textColor=PALETTE_DARK,
        fontName="Helvetica-Bold",
        spaceBefore=4,
        spaceAfter=10,
    )
    styles["body"] = ParagraphStyle(
        "body",
        fontSize=10,
        leading=16,
        textColor=PALETTE_MID,
        fontName="Helvetica",
        spaceAfter=8,
    )
    styles["body_bold"] = ParagraphStyle(
        "body_bold",
        fontSize=10,
        leading=16,
        textColor=PALETTE_DARK,
        fontName="Helvetica-Bold",
        spaceAfter=4,
    )
    styles["caption"] = ParagraphStyle(
        "caption",
        fontSize=8,
        leading=11,
        textColor=PALETTE_LIGHT,
        fontName="Helvetica-Oblique",
        spaceAfter=4,
    )
    styles["tag"] = ParagraphStyle(
        "tag",
        fontSize=9,
        leading=13,
        textColor=PALETTE_DARK,
        fontName="Helvetica",
        spaceAfter=3,
        leftIndent=8,
    )
    styles["meta"] = ParagraphStyle(
        "meta",
        fontSize=8,
        leading=12,
        textColor=PALETTE_LIGHT,
        fontName="Helvetica",
        spaceAfter=2,
    )
    return styles


def _rule(width=BODY_W, color=PALETTE_RULE, thickness=0.5):
    return HRFlowable(width=width, thickness=thickness, color=color, spaceAfter=8, spaceBefore=4)


def _safe_image(path: str, max_w: float, max_h: float):
    try:
        with PILImage.open(path) as img:
            w, h = img.size
        ratio = min(max_w / w, max_h / h)
        return Image(path, width=w * ratio, height=h * ratio)
    except Exception:
        return None


def _color_swatch_table(palette) -> Table | None:
    if not palette:
        return None

    cells = []
    top_row = []
    bot_row = []
    for sw in palette[:7]:
        r, g, b = sw.rgb
        cell_color = colors.Color(r / 255, g / 255, b / 255)
        top_row.append("")
        bot_row.append(Paragraph(f"{sw.hex}\n{sw.name}", ParagraphStyle("sw", fontSize=7, leading=10, fontName="Helvetica", textColor=PALETTE_MID)))

    col_w = BODY_W / max(len(palette[:7]), 1)
    t = Table([top_row, bot_row], colWidths=[col_w] * len(palette[:7]))

    style_cmds = [
        ("ROWHEIGHT", (0, 0), (-1, 0), 28),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
        ("TOPPADDING", (0, 0), (-1, 0), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 1), (-1, 1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 1), (-1, 1), "CENTER"),
    ]
    for i, sw in enumerate(palette[:7]):
        r, g, b = sw.rgb
        cell_color = colors.Color(r / 255, g / 255, b / 255)
        style_cmds.append(("BACKGROUND", (i, 0), (i, 0), cell_color))

    t.setStyle(TableStyle(style_cmds))
    return t


def _image_grid(image_paths: list[str], cols: int = 3) -> Table | None:
    valid = [p for p in image_paths if Path(p).exists()]
    if not valid:
        return None

    cell_w = (BODY_W - (cols - 1) * 4) / cols
    cell_h = cell_w * 0.75

    rows = []
    row = []
    for i, path in enumerate(valid):
        img = _safe_image(path, cell_w, cell_h)
        row.append(img if img else "")
        if len(row) == cols:
            rows.append(row)
            row = []
    if row:
        while len(row) < cols:
            row.append("")
        rows.append(row)

    if not rows:
        return None

    t = Table(rows, colWidths=[cell_w] * cols, rowHeights=[cell_h] * len(rows))
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    return t


def _on_page(canvas, doc, brand_name: str, generated_at: str):
    canvas.saveState()
    if doc.page > 1:
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(PALETTE_LIGHT)
        canvas.drawString(MARGIN, 15 * mm, brand_name.upper() + " — BRAND DNA")
        canvas.drawRightString(PAGE_W - MARGIN, 15 * mm, str(doc.page))
        canvas.setStrokeColor(PALETTE_RULE)
        canvas.setLineWidth(0.3)
        canvas.line(MARGIN, 17 * mm, PAGE_W - MARGIN, 17 * mm)
    canvas.restoreState()


def generate_pdf(dna: BrandDNA, output_path: str) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    styles = _build_styles()

    def on_page(canvas, doc):
        _on_page(canvas, doc, dna.brand_name, dna.generated_at[:10])

    frame_cover = Frame(MARGIN, MARGIN, BODY_W, PAGE_H - 2 * MARGIN, id="cover")
    frame_body = Frame(MARGIN, 2.2 * cm, BODY_W, PAGE_H - 4.4 * cm, id="body")

    cover_tpl = PageTemplate(id="Cover", frames=[frame_cover])
    body_tpl = PageTemplate(id="Body", frames=[frame_body], onPage=on_page)

    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        pageTemplates=[cover_tpl, body_tpl],
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    story = []

    story.append(Spacer(1, 3 * cm))
    story.append(Paragraph("BRAND DNA DOSSIER", styles["cover_subtitle"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(dna.brand_name, styles["cover_brand"]))
    story.append(_rule(color=PALETTE_ACCENT, thickness=1.5))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(dna.website_url, styles["meta"]))
    story.append(Paragraph(f"Generated {dna.generated_at[:10]}", styles["meta"]))
    story.append(Spacer(1, 1.5 * cm))

    stats = [
        ["Images analysed", str(dna.total_images_after_filter)],
        ["Pages crawled", str(dna.pages_crawled)],
        ["Instagram posts", str(dna.instagram_posts_scraped) if dna.instagram_posts_scraped else "—"],
        ["Visual clusters", str(len(dna.visual_clusters))],
    ]
    stat_table = Table(stats, colWidths=[5 * cm, 4 * cm])
    stat_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), PALETTE_LIGHT),
        ("TEXTCOLOR", (1, 0), (1, -1), PALETTE_DARK),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(stat_table)

    story.append(NextPageTemplate("Body"))
    story.append(PageBreak())

    story.append(Paragraph("01 — VISUAL IDENTITY", styles["section_header"]))
    story.append(Paragraph("Color Palette", styles["heading2"]))
    story.append(_rule())

    if dna.color_palette:
        swatch_table = _color_swatch_table(dna.color_palette)
        if swatch_table:
            story.append(swatch_table)
            story.append(Spacer(1, 0.5 * cm))
        dominant = ", ".join(f"{s.name} ({s.hex})" for s in dna.color_palette[:5])
        story.append(Paragraph(f"Dominant tones: {dominant}.", styles["body"]))
    else:
        story.append(Paragraph("Color data unavailable.", styles["body"]))

    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Garment Category Mix", styles["heading2"]))
    story.append(_rule())

    if dna.garment_categories:
        total = sum(dna.garment_categories.values())
        for cat, cnt in sorted(dna.garment_categories.items(), key=lambda x: -x[1])[:8]:
            pct = round(cnt / total * 100) if total else 0
            story.append(Paragraph(f"· {cat.title()}  —  {pct}%", styles["tag"]))
        story.append(Spacer(1, 0.3 * cm))
    else:
        story.append(Paragraph("Category data unavailable.", styles["body"]))

    if dna.silhouette_notes:
        story.append(Paragraph("Silhouettes & Proportions", styles["heading2"]))
        story.append(_rule())
        story.append(Paragraph(dna.silhouette_notes, styles["body"]))

    if dna.styling_cues:
        story.append(Paragraph("Styling Cues", styles["heading2"]))
        story.append(_rule())
        story.append(Paragraph(dna.styling_cues, styles["body"]))

    story.append(PageBreak())
    story.append(Paragraph("02 — TEXTUAL IDENTITY", styles["section_header"]))
    story.append(Paragraph("Brand Voice", styles["heading2"]))
    story.append(_rule())
    story.append(Paragraph(dna.brand_voice or "Not determined.", styles["body"]))
    story.append(Spacer(1, 0.3 * cm))

    if dna.recurring_vocabulary:
        story.append(Paragraph("Recurring Vocabulary", styles["heading2"]))
        story.append(_rule())
        vocab_str = "  ·  ".join(dna.recurring_vocabulary)
        story.append(Paragraph(vocab_str, styles["body"]))
        story.append(Spacer(1, 0.3 * cm))

    if dna.stated_values:
        story.append(Paragraph("Stated Values", styles["heading2"]))
        story.append(_rule())
        for val in dna.stated_values:
            story.append(Paragraph(f"· {val}", styles["tag"]))
        story.append(Spacer(1, 0.3 * cm))

    if dna.positioning_statement:
        story.append(Paragraph("Positioning", styles["heading2"]))
        story.append(_rule())
        story.append(Paragraph(dna.positioning_statement, styles["body"]))

    story.append(PageBreak())
    story.append(Paragraph("03 — AUDIENCE SIGNALS", styles["section_header"]))
    story.append(Paragraph("Demographics", styles["heading2"]))
    story.append(_rule())
    story.append(Paragraph(dna.audience_demographics or "Not determined.", styles["body"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Psychographics", styles["heading2"]))
    story.append(_rule())
    story.append(Paragraph(dna.audience_psychographics or "Not determined.", styles["body"]))

    story.append(PageBreak())
    story.append(Paragraph("04 — AESTHETIC CLUSTERS", styles["section_header"]))
    story.append(Spacer(1, 0.2 * cm))

    if dna.visual_clusters:
        for cluster in dna.visual_clusters:
            story.append(Paragraph(cluster.label, styles["heading2"]))
            story.append(_rule())
            story.append(Paragraph(cluster.description, styles["body"]))
            story.append(Paragraph(f"{cluster.size} images in this group.", styles["caption"]))

            grid = _image_grid(cluster.representative_images, cols=min(4, len(cluster.representative_images)))
            if grid:
                story.append(grid)
            story.append(Spacer(1, 0.8 * cm))
    else:
        story.append(Paragraph("Visual clustering data unavailable.", styles["body"]))

    doc.build(story)
    logger.info("pdf_generated", path=output_path)
    return output_path
