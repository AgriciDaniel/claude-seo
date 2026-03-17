#!/usr/bin/env python3
"""
Milestone Inc. — Branded SEO Report PDF Generator
==================================================
Reads a markdown SEO report and writes a professionally branded PDF.

Usage:
    python generate_pdf.py "<hotel_name>" "<report_type>" [input_file]

    hotel_name   : Property name (e.g. "Grand Hyatt Dubai")
    report_type  : Report slug  (e.g. "seo-report", "seo-audit")
    input_file   : Path to markdown file (omit to read from stdin)

Output:
    C:\\Users\\harrs\\reportsss\\<hotel_name>\\<hotel_name>_<report_type>.pdf

    The hotel sub-folder is created if it does not already exist.
    If the folder is already present it is reused — never duplicated.

Branding:
    - Milestone Inc. blue header bar (#0072e4) on every page
    - Cover page with company name, tagline, hotel name, date
    - Footer with company contact info and page numbers
    - PDF metadata author/creator/producer = "Milestone Inc."
    - No third-party tool attribution anywhere in the document

Requirements:
    pip install reportlab
"""

import sys
import os
import re
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable, PageBreak,
    )
except ImportError:
    print("ERROR: reportlab is not installed. Run: pip install reportlab",
          file=sys.stderr)
    sys.exit(1)

# ── Output root ────────────────────────────────────────────────────────────────
BASE_OUTPUT_DIR = Path(r"C:\Users\harrs\reportsss")

# ── Milestone Inc. brand tokens ────────────────────────────────────────────────
BRAND_BLUE       = "#0072e4"
BRAND_LIGHT_BLUE = "#e8f1fd"
BRAND_GRAY       = "#6b7280"
BRAND_LIGHT_GRAY = "#f3f4f6"
BRAND_BORDER     = "#d1d5db"
TEXT_DARK        = "#111827"
TEXT_MEDIUM      = "#374151"

COMPANY_NAME    = "Milestone Inc."
COMPANY_TAGLINE = "AI-native Digital Experience Platform"
COMPANY_PHONE   = "+1 (408) 200-2211"
COMPANY_EMAIL   = "sales@milestoneinternet.com"
COMPANY_WEBSITE = "www.milestoneinternet.com"
COMPANY_ADDRESS = "333 West San Carlos St, Suite 600, San Jose, CA 95110"

PAGE_W, PAGE_H = A4
MARGIN    = 0.75 * inch
CONTENT_W = PAGE_W - 2 * MARGIN


# ── Helpers ────────────────────────────────────────────────────────────────────

def _c(hex_color: str):
    return colors.HexColor(hex_color)


def _safe_name(name: str) -> str:
    """Sanitise a string for use as a Windows folder / filename component."""
    name = re.sub(r'[<>:"/\\|?*\r\n]', '', name)
    name = re.sub(r'\s+', '_', name.strip())
    return name or "Unknown_Property"


def get_output_path(hotel_name: str, report_type: str = "seo-report") -> Path:
    """
    Build and ensure the output path.
    Layout:  BASE_OUTPUT_DIR / <safe_hotel> / <safe_hotel>_<safe_type>.pdf
    The hotel sub-folder is created with exist_ok=True (idempotent).
    """
    safe_hotel = _safe_name(hotel_name)
    safe_type  = _safe_name(report_type)
    hotel_dir  = BASE_OUTPUT_DIR / safe_hotel
    hotel_dir.mkdir(parents=True, exist_ok=True)
    return hotel_dir / f"{safe_hotel}_{safe_type}.pdf"


# ── Page canvas: branded header bar + footer ──────────────────────────────────

def _draw_page(canvas_obj, doc):
    canvas_obj.saveState()
    bar_h = 0.42 * inch

    # Blue header bar
    canvas_obj.setFillColor(_c(BRAND_BLUE))
    canvas_obj.rect(0, PAGE_H - bar_h, PAGE_W, bar_h, fill=1, stroke=0)

    # Company name (left)
    canvas_obj.setFillColor(colors.white)
    canvas_obj.setFont("Helvetica-Bold", 10.5)
    canvas_obj.drawString(MARGIN, PAGE_H - bar_h + 0.13 * inch, COMPANY_NAME)

    # Website (right)
    canvas_obj.setFont("Helvetica", 8)
    site_w = canvas_obj.stringWidth(COMPANY_WEBSITE, "Helvetica", 8)
    canvas_obj.drawString(
        PAGE_W - MARGIN - site_w,
        PAGE_H - bar_h + 0.13 * inch,
        COMPANY_WEBSITE,
    )

    # Footer separator line
    footer_y = 0.36 * inch
    canvas_obj.setStrokeColor(_c(BRAND_BORDER))
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(MARGIN, footer_y + 0.16 * inch,
                    PAGE_W - MARGIN, footer_y + 0.16 * inch)

    # Footer left: contact info
    canvas_obj.setFillColor(_c(BRAND_GRAY))
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.drawString(
        MARGIN, footer_y,
        f"{COMPANY_NAME}  |  {COMPANY_PHONE}  |  {COMPANY_EMAIL}",
    )

    # Footer right: page number
    page_label = f"Page {doc.page}"
    pw = canvas_obj.stringWidth(page_label, "Helvetica", 7)
    canvas_obj.drawString(PAGE_W - MARGIN - pw, footer_y, page_label)

    canvas_obj.restoreState()


# ── Style sheet ────────────────────────────────────────────────────────────────

def _styles() -> Dict[str, ParagraphStyle]:
    def ps(name, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, **kw)

    return {
        "h1":     ps("H1",     fontName="Helvetica-Bold",         fontSize=16,
                     textColor=_c(BRAND_BLUE),   spaceBefore=16, spaceAfter=6,  leading=21),
        "h2":     ps("H2",     fontName="Helvetica-Bold",         fontSize=13,
                     textColor=_c(TEXT_DARK),    spaceBefore=12, spaceAfter=4,  leading=17),
        "h3":     ps("H3",     fontName="Helvetica-BoldOblique",  fontSize=11,
                     textColor=_c(TEXT_MEDIUM),  spaceBefore=8,  spaceAfter=3,  leading=14),
        "body":   ps("Body",   fontName="Helvetica",              fontSize=9.5,
                     textColor=_c(TEXT_DARK),    leading=14, spaceAfter=3),
        "bullet": ps("Bullet", fontName="Helvetica",              fontSize=9.5,
                     textColor=_c(TEXT_DARK),    leading=13, spaceAfter=2,
                     leftIndent=14, firstLineIndent=0),
        "code":   ps("Code",   fontName="Courier",                fontSize=8.5,
                     textColor=_c(TEXT_MEDIUM),  leading=12, spaceAfter=4,
                     leftIndent=12),
        "small":  ps("Small",  fontName="Helvetica",              fontSize=8.5,
                     textColor=_c(TEXT_MEDIUM),  leading=12, spaceAfter=2),
        # Table cells
        "th":     ps("TH",     fontName="Helvetica-Bold",         fontSize=8.5,
                     textColor=colors.white,     leading=11, alignment=TA_CENTER),
        "td":     ps("TD",     fontName="Helvetica",              fontSize=8.5,
                     textColor=_c(TEXT_DARK),    leading=12),
        # Cover page
        "cover_co":    ps("CoverCo",    fontName="Helvetica-Bold",  fontSize=30,
                          textColor=_c(BRAND_BLUE),  spaceAfter=4,  leading=36),
        "cover_tag":   ps("CoverTag",   fontName="Helvetica",        fontSize=12,
                          textColor=_c(BRAND_GRAY),  spaceAfter=36, leading=16),
        "cover_rtype": ps("CoverRType", fontName="Helvetica-Bold",   fontSize=14,
                          textColor=_c(BRAND_GRAY),  spaceAfter=8,  leading=18),
        "cover_name":  ps("CoverName",  fontName="Helvetica-Bold",   fontSize=32,
                          textColor=_c(TEXT_DARK),   spaceAfter=28, leading=40),
        "cover_date":  ps("CoverDate",  fontName="Helvetica",         fontSize=11,
                          textColor=_c(BRAND_GRAY),  spaceAfter=6,  leading=16),
        "confid":      ps("Confid",     fontName="Helvetica-Oblique", fontSize=9,
                          textColor=_c(BRAND_GRAY),  leading=13),
    }


# ── Base table style — Paragraph-wrapped cells prevent all overlap ─────────────

_BASE_TABLE_STYLE = [
    ("BACKGROUND",     (0, 0), (-1,  0), _c(BRAND_BLUE)),
    ("TEXTCOLOR",      (0, 0), (-1,  0), colors.white),
    ("FONTNAME",       (0, 0), (-1,  0), "Helvetica-Bold"),
    ("FONTSIZE",       (0, 0), (-1,  0), 8.5),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _c(BRAND_LIGHT_GRAY)]),
    ("FONTNAME",       (0, 1), (-1, -1), "Helvetica"),
    ("FONTSIZE",       (0, 1), (-1, -1), 8.5),
    ("VALIGN",         (0, 0), (-1, -1), "TOP"),
    ("WORDWRAP",       (0, 0), (-1, -1), True),
    ("GRID",           (0, 0), (-1, -1), 0.4, _c(BRAND_BORDER)),
    ("BOX",            (0, 0), (-1, -1), 0.8, _c(BRAND_BLUE)),
    ("TOPPADDING",     (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
    ("LEFTPADDING",    (0, 0), (-1, -1), 6),
    ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
]


def _make_table(rows: List[List[str]], col_fractions: List[float],
                st: Dict, header: bool = True) -> Table:
    """
    Every cell is a word-wrapped Paragraph — this is what prevents text overflow
    and content overlapping in tables, regardless of cell length.
    col_fractions must sum to 1.0.
    """
    col_widths = [CONTENT_W * f for f in col_fractions]
    styled_rows = []
    for r_i, row in enumerate(rows):
        styled_row = []
        for cell in row:
            text = str(cell) if cell is not None else ""
            style = st["th"] if (r_i == 0 and header) else st["td"]
            styled_row.append(Paragraph(text, style))
        styled_rows.append(styled_row)
    tbl = Table(styled_rows, colWidths=col_widths, repeatRows=1 if header else 0)
    tbl.setStyle(TableStyle(_BASE_TABLE_STYLE))
    return tbl


# ── Cover page ─────────────────────────────────────────────────────────────────

def _cover_page(hotel_name: str, report_type: str, st: Dict) -> list:
    f = []
    f.append(Spacer(1, 1.6 * inch))
    f.append(HRFlowable(width="100%", thickness=3,
                        color=_c(BRAND_BLUE), spaceAfter=18))
    f.append(Paragraph(COMPANY_NAME, st["cover_co"]))
    f.append(Paragraph(COMPANY_TAGLINE, st["cover_tag"]))
    label = report_type.replace("-", " ").replace("_", " ").title()
    f.append(Paragraph(label, st["cover_rtype"]))
    f.append(Paragraph(hotel_name, st["cover_name"]))
    f.append(HRFlowable(width="55%", thickness=1.5,
                        color=_c(BRAND_BLUE), spaceAfter=18))
    today = datetime.now().strftime("%B %d, %Y")
    f.append(Paragraph(f"Report Generated: {today}", st["cover_date"]))
    f.append(Spacer(1, 0.4 * inch))
    f.append(Paragraph(
        "CONFIDENTIAL — Prepared exclusively for the above property.",
        st["confid"],
    ))
    f.append(Spacer(1, 0.35 * inch))

    # Contact box
    ct_data = [
        [Paragraph(f"<b>{COMPANY_NAME}</b>", st["td"]),
         Paragraph("<b>Contact Us</b>", st["td"])],
        [Paragraph(COMPANY_ADDRESS, st["small"]),
         Paragraph(
             f"{COMPANY_PHONE}<br/>{COMPANY_EMAIL}<br/>{COMPANY_WEBSITE}",
             st["small"],
         )],
    ]
    ct = Table(ct_data, colWidths=[CONTENT_W * 0.55, CONTENT_W * 0.45])
    ct.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), _c(BRAND_LIGHT_BLUE)),
        ("BOX",           (0, 0), (-1,-1), 0.5, _c(BRAND_BORDER)),
        ("GRID",          (0, 0), (-1,-1), 0.4, _c(BRAND_BORDER)),
        ("TOPPADDING",    (0, 0), (-1,-1), 7),
        ("BOTTOMPADDING", (0, 0), (-1,-1), 7),
        ("LEFTPADDING",   (0, 0), (-1,-1), 10),
        ("RIGHTPADDING",  (0, 0), (-1,-1), 10),
        ("VALIGN",        (0, 0), (-1,-1), "TOP"),
    ]))
    f.append(ct)
    f.append(PageBreak())
    return f


# ── Markdown parser → ReportLab flowables ─────────────────────────────────────

def _escape(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text


def _inline(text: str) -> str:
    """Convert markdown inline markup to ReportLab XML tags."""
    text = _escape(text)
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', text)
    text = re.sub(r'\*\*(.+?)\*\*',     r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__',         r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*',         r'<i>\1</i>', text)
    text = re.sub(r'_(.+?)_',           r'<i>\1</i>', text)
    text = re.sub(r'`(.+?)`',           r'<font name="Courier">\1</font>', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # strip links, keep text
    return text


def _md_to_flowables(md: str, st: Dict) -> list:
    """
    Parse a markdown string and return a list of ReportLab flowables.
    Handles: headings (#/##/###), bullet lists, numbered lists,
    pipe tables, code blocks (```), horizontal rules (---), paragraphs.
    Tables use word-wrapped Paragraphs in every cell — no overlap possible.
    """
    flowables = []
    lines = md.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Code block
        if stripped.startswith("```"):
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(_escape(lines[i]))
                i += 1
            i += 1
            if code_lines:
                flowables.append(Paragraph(
                    "<br/>".join(code_lines), st["code"]
                ))
            continue

        # Horizontal rule
        if re.match(r'^[-*_]{3,}$', stripped):
            flowables.append(HRFlowable(
                width="100%", thickness=0.5,
                color=_c(BRAND_BORDER), spaceAfter=6,
            ))
            i += 1
            continue

        # Headings
        if stripped.startswith("### "):
            flowables.append(Paragraph(_inline(stripped[4:]), st["h3"]))
            i += 1
            continue
        if stripped.startswith("## "):
            flowables.append(Paragraph(_inline(stripped[3:]), st["h2"]))
            i += 1
            continue
        if stripped.startswith("# "):
            flowables.append(Paragraph(_inline(stripped[2:]), st["h1"]))
            i += 1
            continue

        # Pipe table
        if stripped.startswith("|") and "|" in stripped:
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            # Drop separator rows (---|--- style)
            data_rows = [
                r for r in table_lines
                if not re.match(r'^\|[\s\-:|]+\|$', r)
            ]
            if data_rows:
                raw = [
                    [c.strip() for c in r.split("|") if c.strip()]
                    for r in data_rows
                ]
                num_cols = max(len(r) for r in raw)
                for r in raw:
                    while len(r) < num_cols:
                        r.append("")
                fractions = [1.0 / num_cols] * num_cols
                flowables.append(_make_table(raw, fractions, st))
                flowables.append(Spacer(1, 6))
            continue

        # Bullet / numbered list — collect consecutive items
        if re.match(r'^[-*+]\s', stripped) or re.match(r'^\d+\.\s', stripped):
            while i < len(lines):
                ls = lines[i].strip()
                m_ul = re.match(r'^[-*+]\s+(.*)', ls)
                m_ol = re.match(r'^\d+\.\s+(.*)', ls)
                if m_ul:
                    flowables.append(
                        Paragraph(f"• {_inline(m_ul.group(1))}", st["bullet"])
                    )
                    i += 1
                elif m_ol:
                    num = re.match(r'^(\d+)\.', ls).group(1)
                    flowables.append(
                        Paragraph(f"{num}. {_inline(m_ol.group(1))}", st["bullet"])
                    )
                    i += 1
                else:
                    break
            continue

        # Regular paragraph
        flowables.append(Paragraph(_inline(stripped), st["body"]))
        i += 1

    return flowables


# ── Main PDF builder ───────────────────────────────────────────────────────────

def generate_pdf(hotel_name: str, report_type: str, md_content: str) -> str:
    """
    Build and save the branded PDF.
    Returns the absolute path to the saved file.
    """
    output_path = get_output_path(hotel_name, report_type)
    st = _styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=0.85 * inch,    # space for header bar
        bottomMargin=0.65 * inch,  # space for footer
        # PDF metadata — Milestone Inc. only, no third-party tool mentioned
        title=f"{hotel_name} — {report_type.replace('-', ' ').title()}",
        author=COMPANY_NAME,
        subject=f"SEO Report — {hotel_name}",
        creator=COMPANY_NAME,
        producer=COMPANY_NAME,
    )

    story: list = []
    story += _cover_page(hotel_name, report_type, st)
    story += _md_to_flowables(md_content, st)

    doc.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return str(output_path)


# ── CLI entry point ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Milestone Inc. — Branded SEO Report PDF Generator",
        epilog="Reads markdown from input_file (or stdin) and writes a branded PDF.",
    )
    parser.add_argument("hotel_name",   help='Property name, e.g. "Grand Hyatt Dubai"')
    parser.add_argument("report_type",  help='Report slug, e.g. "seo-report" or "seo-audit"')
    parser.add_argument(
        "input_file", nargs="?", default="-",
        help="Path to markdown report file (default: read from stdin)",
    )
    args = parser.parse_args()

    # Read content
    if args.input_file == "-":
        md_content = sys.stdin.read()
    else:
        p = Path(args.input_file)
        if not p.exists():
            print(f"ERROR: File not found: {p}", file=sys.stderr)
            sys.exit(1)
        md_content = p.read_text(encoding="utf-8")

    try:
        out = generate_pdf(args.hotel_name, args.report_type, md_content)
        print(f"[PDF] Saved: {out}")
        # Structured output for agent consumption
        import json
        print(json.dumps({"status": "success", "pdf_path": out}))
    except Exception as exc:
        import traceback
        print(f"ERROR: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
