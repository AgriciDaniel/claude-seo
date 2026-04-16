#!/usr/bin/env python3
"""
release_report.py — Claude SEO v1.9.0 Pro Hub Challenge Release Report

Usage:
    python scripts/release_report.py --output ~/Desktop/
    python scripts/release_report.py --output ~/Desktop/ --screenshots /path/

Dependencies: matplotlib>=3.8.0, weasyprint>=61.0
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


# --- Brand ---

BRAND = {
    "bg":        "#0A0A0A",
    "card":      "#111111",
    "card_inner":"#1A1A1A",
    "border":    "#2D2D2D",
    "text":      "#F5F5F0",
    "text_sec":  "#888888",
    "accent":    "#E07850",
    "green":     "#4ADE80",
    "amber":     "#f59e0b",
    "blue":      "#60A5FA",
    "muted":     "#888888",
}

SCREENSHOTS_DIR = str(Path.home() / "Downloads" / "pro-hub-challenge-march-screenshots")


def _setup_matplotlib():
    plt.rcParams.update({
        "font.family":       "sans-serif",
        "font.sans-serif":   ["Space Grotesk", "DejaVu Sans", "Arial", "Helvetica"],
        "font.size":         11,
        "axes.titlesize":    14,
        "axes.titleweight":  "bold",
        "axes.facecolor":    BRAND["card"],
        "figure.facecolor":  BRAND["bg"],
        "text.color":        BRAND["text"],
        "axes.labelcolor":   BRAND["text"],
        "axes.titlecolor":   BRAND["text"],
        "xtick.color":       BRAND["text_sec"],
        "ytick.color":       BRAND["text_sec"],
        "axes.edgecolor":    BRAND["border"],
        "axes.grid":         True,
        "axes.spines.top":   False,
        "axes.spines.right": False,
    })


_setup_matplotlib()


# --- Chart Functions ---

def chart_contribution_flow(charts_dir: Path) -> str:
    entries = [
        ("Lutfiya Miller",   "/seo cluster",   "new",      "New Skill"),
        ("Florian Schmitz",  "/seo sxo",       "new",      "New Skill"),
        ("Dan Colta",        "/seo drift",     "new",      "New Skill"),
        ("Matej Marjanovic", "/seo ecommerce", "new",      "New Skill"),
        ("Chris Muller",     "/seo hreflang",  "enhanced", "Enhancement"),
        ("Benjamin",         "claude-blog",    "deferred", "Out of Scope"),
    ]
    status_colors = {
        "new":      BRAND["green"],
        "enhanced": BRAND["accent"],
        "deferred": BRAND["muted"],
    }

    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_facecolor(BRAND["card"])
    fig.patch.set_facecolor(BRAND["bg"])
    ax.set_xlim(-0.2, 10.5)
    ax.set_ylim(-0.8, len(entries) - 0.2)
    ax.axis("off")
    ax.set_title("Pro Hub Challenge: Contribution Pipeline", fontsize=14,
                 fontweight="bold", color=BRAND["text"], pad=12)

    for i, (name, skill, status, label) in enumerate(entries):
        y = len(entries) - 1 - i
        color = status_colors[status]

        left = mpatches.FancyBboxPatch(
            (0.05, y - 0.33), 2.9, 0.66,
            boxstyle="round,pad=0.04",
            linewidth=1.2, edgecolor=BRAND["border"], facecolor=BRAND["card_inner"]
        )
        ax.add_patch(left)
        ax.text(1.5, y, name, ha="center", va="center", fontsize=9.5,
                color=BRAND["text"], fontweight="bold")

        ax.annotate("", xy=(3.15, y), xytext=(2.95, y),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=2.0, mutation_scale=14))

        right = mpatches.FancyBboxPatch(
            (3.2, y - 0.33), 5.6, 0.66,
            boxstyle="round,pad=0.04",
            linewidth=1.2, edgecolor=BRAND["border"], facecolor=BRAND["card_inner"]
        )
        ax.add_patch(right)
        ax.text(3.45, y, skill, ha="left", va="center", fontsize=9, color=BRAND["text"])

        badge = mpatches.FancyBboxPatch(
            (7.2, y - 0.23), 1.85, 0.46,
            boxstyle="round,pad=0.03",
            linewidth=0, facecolor=color
        )
        ax.add_patch(badge)
        txt_color = BRAND["bg"] if color != BRAND["muted"] else BRAND["text"]
        ax.text(8.12, y, label, ha="center", va="center", fontsize=8,
                color=txt_color, fontweight="bold")

    legend_elements = [
        mpatches.Patch(facecolor=BRAND["green"],  label="New Skill"),
        mpatches.Patch(facecolor=BRAND["accent"], label="Enhancement"),
        mpatches.Patch(facecolor=BRAND["muted"],  label="Out of Scope"),
    ]
    legend = ax.legend(handles=legend_elements, loc="lower right", fontsize=9,
                       framealpha=0.9, edgecolor=BRAND["border"])
    legend.get_frame().set_facecolor(BRAND["card"])
    for t in legend.get_texts():
        t.set_color(BRAND["text"])

    plt.tight_layout()
    path = charts_dir / "contribution_flow.png"
    plt.savefig(path, dpi=200, bbox_inches="tight", facecolor=BRAND["bg"])
    plt.close()
    return str(path)


def chart_skill_architecture(charts_dir: Path) -> str:
    categories = [
        "Orchestrator",
        "Technical Audit",
        "Content & Schema",
        "Local & Maps",
        "Planning & Strategy",
        "Intelligence (v1.9.0)",
        "E-commerce (v1.9.0)",
        "International",
        "Extensions",
    ]
    existing = [1, 4, 4, 2, 5, 0, 0, 2, 2]
    new_v190  = [0, 0, 0, 0, 0, 3, 1, 0, 0]

    y = np.arange(len(categories))
    h = 0.32

    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.set_facecolor(BRAND["card"])
    fig.patch.set_facecolor(BRAND["bg"])

    bars_e = ax.barh(y + h / 2, existing, h, label="Existing (v1.8.x)",
                     color=BRAND["blue"], alpha=0.85)
    bars_n = ax.barh(y - h / 2, new_v190, h, label="New in v1.9.0",
                     color=BRAND["accent"], alpha=0.95)

    ax.set_yticks(y)
    ax.set_yticklabels(categories, fontsize=10, color=BRAND["text"])
    ax.set_xlabel("Number of Skills", fontsize=10)
    ax.set_title("Claude SEO Skill Architecture: v1.9.0 (23 Total Skills)",
                 fontsize=14, fontweight="bold", color=BRAND["text"], pad=12)
    ax.set_xlim(0, 7.5)
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.tick_params(colors=BRAND["text_sec"])
    ax.spines["left"].set_color(BRAND["border"])
    ax.spines["bottom"].set_color(BRAND["border"])
    ax.set_axisbelow(True)
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=BRAND["border"], linewidth=0.5)

    for bar in list(bars_e) + list(bars_n):
        w = bar.get_width()
        if w > 0:
            c = BRAND["blue"] if bar in bars_e else BRAND["accent"]
            ax.text(w + 0.08, bar.get_y() + bar.get_height() / 2,
                    str(int(w)), va="center", fontsize=9, color=c)

    legend = ax.legend(fontsize=10, framealpha=0.9, edgecolor=BRAND["border"])
    legend.get_frame().set_facecolor(BRAND["card"])
    for t in legend.get_texts():
        t.set_color(BRAND["text"])

    plt.tight_layout()
    path = charts_dir / "skill_architecture.png"
    plt.savefig(path, dpi=200, bbox_inches="tight", facecolor=BRAND["bg"])
    plt.close()
    return str(path)


def chart_review_scores(charts_dir: Path) -> str:
    labels = ["Round 1\nCode Review", "Round 2\nRe-Review",
              "Round 3\nMax-Effort", "Round 4\nSecurity Audit"]
    scores = [87, 93, 97, 85]
    dot_colors = [BRAND["amber"], BRAND["amber"], BRAND["green"], BRAND["amber"]]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_facecolor(BRAND["card"])
    fig.patch.set_facecolor(BRAND["bg"])

    x = np.arange(len(labels))
    ax.plot(x, scores, color=BRAND["accent"], linewidth=2.5, zorder=2)
    for xi, (yi, ci) in enumerate(zip(scores, dot_colors)):
        ax.scatter([xi], [yi], color=ci, s=130, zorder=3,
                   edgecolors=BRAND["accent"], linewidth=1.5)
        ax.annotate(f"{yi}/100", (xi, yi),
                    textcoords="offset points", xytext=(0, 13),
                    ha="center", fontsize=11, fontweight="bold", color=BRAND["text"])

    ax.axhline(y=90, color=BRAND["green"], linestyle="--", alpha=0.4, linewidth=1)
    ax.axhline(y=80, color=BRAND["amber"], linestyle="--", alpha=0.4, linewidth=1)
    ax.text(3.55, 90.8, "Excellent (90+)", fontsize=8, color=BRAND["green"], alpha=0.8)
    ax.text(3.55, 80.8, "Good (80+)",      fontsize=8, color=BRAND["amber"], alpha=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9.5, color=BRAND["text"])
    ax.set_xlim(-0.4, 3.8)
    ax.set_ylim(76, 107)
    ax.set_ylabel("Score / 100", fontsize=10)
    ax.set_title("v1.9.0 Review Score Progression: 4 Rounds",
                 fontsize=14, fontweight="bold", color=BRAND["text"], pad=12)
    ax.tick_params(colors=BRAND["text_sec"])
    ax.spines["left"].set_color(BRAND["border"])
    ax.spines["bottom"].set_color(BRAND["border"])
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=BRAND["border"], linewidth=0.5)

    plt.tight_layout()
    path = charts_dir / "review_scores.png"
    plt.savefig(path, dpi=200, bbox_inches="tight", facecolor=BRAND["bg"])
    plt.close()
    return str(path)


def chart_security_matrix(charts_dir: Path) -> str:
    severities = ["HIGH", "MEDIUM", "LOW"]
    fixed    = [2, 2, 0]
    deferred = [2, 4, 5]

    x = np.arange(len(severities))
    w = 0.35

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_facecolor(BRAND["card"])
    fig.patch.set_facecolor(BRAND["bg"])

    b1 = ax.bar(x - w / 2, fixed,    w, label="Fixed in v1.9.0",
                color=BRAND["green"], alpha=0.9, edgecolor=BRAND["bg"])
    b2 = ax.bar(x + w / 2, deferred, w, label="Deferred to v1.9.1",
                color=BRAND["amber"], alpha=0.9, edgecolor=BRAND["bg"])

    for bar in list(b1) + list(b2):
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.1,
                    str(int(h)), ha="center", va="bottom",
                    fontsize=11, fontweight="bold", color=BRAND["text"])

    ax.set_xticks(x)
    ax.set_xticklabels(severities, fontsize=12, color=BRAND["text"])
    ax.set_ylabel("Number of Findings", fontsize=10)
    ax.set_title("Security Audit: 15 Findings, Score 85/100",
                 fontsize=14, fontweight="bold", color=BRAND["text"], pad=12)
    ax.set_ylim(0, 8.5)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.tick_params(colors=BRAND["text_sec"])
    legend = ax.legend(fontsize=10, framealpha=0.9, edgecolor=BRAND["border"])
    legend.get_frame().set_facecolor(BRAND["card"])
    for t in legend.get_texts():
        t.set_color(BRAND["text"])
    ax.spines["left"].set_color(BRAND["border"])
    ax.spines["bottom"].set_color(BRAND["border"])
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=BRAND["border"], linewidth=0.5)
    ax.text(0.98, 0.96, "0 CRITICAL  |  4 Fixed  |  11 Deferred",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=9, color=BRAND["text_sec"], style="italic")

    plt.tight_layout()
    path = charts_dir / "security_matrix.png"
    plt.savefig(path, dpi=200, bbox_inches="tight", facecolor=BRAND["bg"])
    plt.close()
    return str(path)


# --- CSS ---

def _build_css() -> str:
    return """<style>
  @page {
    size: A4;
    background: #0A0A0A;
    margin: 20mm 16mm 22mm 16mm;
    @bottom-center {
      content: "Page " counter(page) " of " counter(pages);
      font-size: 9pt; color: #888888;
      font-family: 'Space Grotesk', 'DejaVu Sans', system-ui, sans-serif;
    }
    @bottom-right {
      content: "Claude SEO v1.9.0";
      font-size: 8pt; color: #2D2D2D;
      font-family: 'Space Grotesk', 'DejaVu Sans', system-ui, sans-serif;
    }
  }

  @page :first {
    margin: 0;
    background: #0A0A0A;
    @bottom-left   { content: none; }
    @bottom-center { content: none; }
    @bottom-right  { content: none; }
  }

  @page toc {
    background: #0A0A0A;
    @bottom-center { content: counter(page); font-size: 9pt; color: #888888; }
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Space Grotesk', 'Inter', 'DejaVu Sans', system-ui, sans-serif;
    font-size: 10pt; line-height: 1.55;
    color: #F5F5F0; background: #0A0A0A;
  }

  /* Title Page */
  .title-page {
    page: first;
    width: 210mm;
    background: #0A0A0A;
    text-align: center; color: #F5F5F0;
    padding: 32mm 28mm 28mm 28mm;
    border-top: 5mm solid #E07850;
  }

  .title-page .badge {
    background: #111111; border: 1px solid #2D2D2D;
    border-radius: 20px; padding: 4px 16px;
    font-size: 8.5pt; letter-spacing: 2px;
    text-transform: uppercase; margin-bottom: 8mm;
    display: inline-block; color: #888888;
  }

  .title-page h1 {
    font-size: 28pt; font-weight: 700;
    margin-bottom: 4mm; line-height: 1.15; color: #F5F5F0;
  }

  .title-page .subtitle {
    font-size: 12pt; color: #888888;
    margin-bottom: 10mm; font-weight: 400;
  }

  .title-metrics { display: table; width: 100%; table-layout: fixed; margin: 8mm auto; }
  .title-metrics .mc {
    display: table-cell; text-align: center; padding: 4mm 2mm;
    border: 1px solid #2D2D2D; background: #111111;
  }
  .title-metrics .mc:first-child { border-radius: 6px 0 0 6px; }
  .title-metrics .mc:last-child  { border-radius: 0 6px 6px 0; }
  .title-metrics .big { font-size: 22pt; font-weight: 700; color: #E07850; line-height: 1; }
  .title-metrics .small { font-size: 7pt; color: #888888; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 1mm; }

  .title-page .meta {
    font-size: 8.5pt; color: #888888;
    margin-top: 10mm; padding-top: 4mm;
    border-top: 1px solid #2D2D2D;
  }

  /* TOC */
  .toc-page { page: toc; page-break-before: always; padding: 16mm; }
  .toc-page h2 {
    font-size: 17pt; color: #F5F5F0;
    margin-bottom: 6mm; padding-bottom: 3mm;
    border-bottom: 2px solid #E07850;
  }
  .toc-list { list-style: none; padding: 0; }
  .toc-list li {
    padding: 2.5mm 0; border-bottom: 1px solid #1A1A1A;
    overflow: hidden; font-size: 10.5pt; color: #F5F5F0;
  }
  .toc-badge {
    float: right; padding: 1px 7px; border-radius: 10px;
    font-size: 8pt; font-weight: bold;
    color: #0A0A0A; background: #E07850;
  }
  .toc-badge.green { background: #4ADE80; color: #0A0A0A; }
  .toc-badge.muted { background: #2D2D2D; color: #888888; }

  /* Sections */
  div.section { page-break-before: always; }

  .section-header {
    background: #111111; border-left: 4px solid #E07850;
    padding: 4mm 5mm; margin-bottom: 5mm;
    page-break-after: avoid;
  }
  .section-header h2 { font-size: 15pt; color: #F5F5F0; margin-bottom: 1mm; }
  .section-header .smeta { font-size: 8.5pt; color: #888888; }

  h3 {
    font-size: 11.5pt; color: #E07850;
    margin-top: 5mm; margin-bottom: 3mm;
    padding-bottom: 1mm; border-bottom: 1px solid #2D2D2D;
    page-break-after: avoid;
  }

  h4 {
    font-size: 10.5pt; color: #F5F5F0;
    margin-top: 3mm; margin-bottom: 2mm;
    page-break-after: avoid;
  }

  p { margin-bottom: 2.5mm; color: #D0CFC8; }

  /* Boxes */
  .highlight   { background: #1A1200; border-left: 3px solid #E07850; padding: 3mm 4mm; margin: 3mm 0; font-size: 9.5pt; color: #D0CFC8; }
  .success-box { background: #0D1F0D; border-left: 3px solid #4ADE80; padding: 3mm 4mm; margin: 3mm 0; font-size: 9.5pt; color: #D0CFC8; }
  .info-box    { background: #0D1020; border-left: 3px solid #60A5FA; padding: 3mm 4mm; margin: 3mm 0; font-size: 9.5pt; color: #D0CFC8; }

  /* Tables */
  table { width: 100%; border-collapse: collapse; margin: 3mm 0 5mm 0; font-size: 9pt; }
  thead th {
    background: #1A1A1A; color: #F5F5F0;
    font-weight: 600; padding: 3mm 4mm;
    text-align: left; border-bottom: 1px solid #2D2D2D;
  }
  tbody td { padding: 2mm 3mm; border-bottom: 1px solid #1A1A1A; vertical-align: top; color: #D0CFC8; }
  tbody tr:nth-child(even) { background: #0F0F0F; }

  .st-fixed    { color: #4ADE80; font-weight: bold; }
  .st-deferred { color: #f59e0b; font-weight: bold; }
  .st-new      { color: #60A5FA; font-weight: bold; }
  .sev-high    { color: #f59e0b; font-weight: bold; }
  .sev-medium  { color: #60A5FA; }
  .sev-low     { color: #888888; }

  /* Charts */
  .chart-container { text-align: center; margin: 4mm 0; }
  .chart-container img { max-width: 100%; max-height: 165mm; height: auto; }
  .chart-caption { font-size: 8pt; color: #888888; font-style: italic; margin-top: 2mm; text-align: center; }

  /* Two-column */
  .two-col { display: table; width: 100%; table-layout: fixed; margin: 3mm 0; }
  .two-col .col { display: table-cell; vertical-align: top; padding: 0 2mm; }

  /* Four metric cards */
  .four-col { display: table; width: 100%; table-layout: fixed; margin: 3mm 0; }
  .four-col .col { display: table-cell; vertical-align: top; padding: 0 1.5mm; }

  .metric-card { background: #111111; border: 1px solid #2D2D2D; border-radius: 6px; padding: 3mm; text-align: center; margin: 2mm 0; }
  .metric-card .value { font-size: 16pt; font-weight: 700; line-height: 1.2; color: #E07850; }
  .metric-card .label { font-size: 7pt; color: #888888; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 1mm; }
  .metric-card .delta { font-size: 8pt; color: #4ADE80; margin-top: 0.5mm; }

  /* Contributor Cards */
  .ccard { background: #111111; border: 1px solid #2D2D2D; border-radius: 6px; padding: 3mm 4mm; margin: 4mm 0; border-left: 4px solid #E07850; }
  .ccard h4 { margin-top: 0; border-bottom: none; padding-bottom: 0; color: #F5F5F0; }
  .ccard .cmeta { font-size: 8.5pt; color: #888888; margin-bottom: 2mm; font-style: italic; }

  /* Screenshots */
  .sshot { text-align: center; margin: 3mm 0; border: 1px solid #2D2D2D; border-radius: 4px; padding: 2mm; background: #111111; }
  .sshot img { max-width: 100%; height: auto; }
  .sshot-cap { font-size: 8pt; color: #888888; font-style: italic; margin-top: 1.5mm; }

  /* Code blocks */
  .code-block {
    background: #111111; color: #E07850;
    padding: 3mm 4mm; border-radius: 4px; border: 1px solid #2D2D2D;
    font-family: 'DejaVu Sans Mono', 'Courier New', monospace;
    font-size: 8pt; line-height: 1.6; margin: 3mm 0;
    white-space: pre-wrap; word-break: break-all;
  }

  /* Roadmap items */
  .ritem { background: #111111; border-radius: 4px; padding: 3mm 4mm; margin: 3mm 0; border-left: 3px solid #2D2D2D; }
  .ritem.high   { border-left-color: #f59e0b; background: #1A1000; }
  .ritem.medium { border-left-color: #60A5FA; background: #0D1020; }

  /* Misc */
  ul { margin-left: 5mm; margin-bottom: 3mm; }
  li { margin-bottom: 1.5mm; color: #D0CFC8; }
  hr.divider { border: none; border-top: 1px solid #2D2D2D; margin: 5mm 0; }
  ol { margin-left: 5mm; margin-bottom: 3mm; }
  code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.5pt; color: #E07850; background: #1A1A1A; padding: 0 2px; border-radius: 2px; }
</style>
"""


# --- HTML Helpers ---

def _chart_html(path: str, caption: str, fig_num: int) -> str:
    if not path:
        return ""
    return (
        f'<div class="chart-container">\n'
        f'  <img src="{_file_url(path)}" style="width:90%;" alt="{caption}">\n'
        f'  <div class="chart-caption">Figure {fig_num}: {caption}</div>\n'
        f'</div>\n'
    )


def _mc(value: str, label: str, delta: str = "") -> str:
    delta_html = f'<div class="delta">{delta}</div>' if delta else ""
    return (
        f'<div class="metric-card">'
        f'<div class="value">{value}</div>'
        f'<div class="label">{label}</div>'
        f'{delta_html}'
        f'</div>'
    )


def _file_url(path: str) -> str:
    """Return a properly URL-encoded file:// URI (handles spaces in paths)."""
    return "file://" + quote(str(path), safe="/:@")


def _screenshot_html(abs_path: str, caption: str, max_h: str = "72mm") -> str:
    if not abs_path or not Path(abs_path).exists():
        return ""
    return (
        f'<div class="sshot">\n'
        f'  <img src="{_file_url(abs_path)}" style="max-height:{max_h}; max-width:100%; height:auto;" alt="{caption}">\n'
        f'  <div class="sshot-cap">{caption}</div>\n'
        f'</div>\n'
    )


# --- Section Builders ---

def _build_title_page(logo_path: str = "") -> str:
    date = datetime.now().strftime("%B %Y")
    logo_html = ""
    if logo_path and Path(logo_path).exists():
        logo_html = (
            f'<div style="margin-bottom:8mm;">'
            f'<img src="{_file_url(logo_path)}" style="max-height:28mm; max-width:160mm;" alt="AI Marketing Hub Pro">'
            f'</div>\n'
        )
    return f"""
<div class="title-page">
  {logo_html}<div class="badge">Claude Code &nbsp;&#183;&nbsp; Agent Skills Standard</div>
  <h1>Claude SEO v1.9.0<br>Release Report</h1>
  <div class="subtitle">Pro Hub Challenge: Community-Driven Extension</div>
  <div class="title-metrics">
    <div class="mc"><div class="big">4</div><div class="small">New Skills</div></div>
    <div class="mc"><div class="big">5</div><div class="small">Contributors</div></div>
    <div class="mc"><div class="big">61</div><div class="small">Files Changed</div></div>
    <div class="mc"><div class="big">85</div><div class="small">Security Score</div></div>
  </div>
  <div class="meta">
    Version 1.9.0 &nbsp;&#183;&nbsp; {date} &nbsp;&#183;&nbsp; github.com/AgriciDaniel/claude-seo
  </div>

  <div style="margin-top:14mm; padding:5mm 6mm; background:#111111; border:1px solid #2D2D2D; border-radius:6px; text-align:left;">
    <div style="font-size:8pt; color:#888888; text-transform:uppercase; letter-spacing:1px; margin-bottom:3mm;">In This Report</div>
    <div style="display:table; width:100%;">
      <div style="display:table-cell; width:50%; padding-right:3mm; vertical-align:top;">
        <ul style="list-style:none; padding:0; margin:0; font-size:9pt; color:#D0CFC8;">
          <li style="margin-bottom:2mm;">5 community submissions, 4 new skills shipped</li>
          <li style="margin-bottom:2mm;">$600 Claude Credits prize pool distributed</li>
          <li style="margin-bottom:2mm;">4 review rounds, peak score 97/100</li>
          <li style="margin-bottom:2mm;">85/100 cybersecurity audit (8 specialist agents)</li>
        </ul>
      </div>
      <div style="display:table-cell; width:50%; vertical-align:top;">
        <ul style="list-style:none; padding:0; margin:0; font-size:9pt; color:#D0CFC8;">
          <li style="margin-bottom:2mm;">XSS vulnerability in cluster-map.html fixed</li>
          <li style="margin-bottom:2mm;">DataForSEO cost guardrail bypass closed</li>
          <li style="margin-bottom:2mm;">fcntl locking added for concurrent agents</li>
          <li style="margin-bottom:2mm;">CI coverage expanded from 21 to 28 scripts</li>
        </ul>
      </div>
    </div>
  </div>
</div>
"""


def _build_toc() -> str:
    rows = [
        ("1", "Executive Summary",          "",                                  ""),
        ("2", "Pro Hub Challenge",           "Community, $600 Prize Pool",        ""),
        ("3", "Community Contributions",     "5 Integrations, 4 New Skills",      ""),
        ("4", "Architecture Evolution",      "19 to 23 Skills",                   ""),
        ("5", "Review Process",              "4 Rounds, Peak 97/100",             "green"),
        ("6", "Security Audit",              "85/100, 4 Fixes Applied",           ""),
        ("7", "DataForSEO Cost Guardrails",  "Technical Deep-Dive",               "muted"),
        ("8", "What's Next",                 "v1.9.1 Priorities",                 "muted"),
    ]
    items = ""
    for num, title, desc, badge_cls in rows:
        badge = f'<span class="toc-badge {badge_cls}">{num}</span>'
        sub = f'<span style="color:#888888; font-size:8.5pt;"> &ndash; {desc}</span>' if desc else ""
        items += f'<li>{badge} <strong>{title}</strong>{sub}</li>\n'

    return f"""
<div class="toc-page">
  <h2>Table of Contents</h2>
  <ul class="toc-list">
{items}  </ul>
  <div style="margin-top:10mm; padding:4mm 5mm; background:#111111; border-left:3px solid #E07850; border-radius:0 4px 4px 0; font-size:9pt; color:#D0CFC8;">
    v1.9.0 is the first community-driven Claude SEO release. Six members submitted skills for the inaugural Pro Hub Challenge. Five shipped. This report covers the contributions, architecture changes, review process, and security findings in full.
  </div>
</div>"""


def _build_executive_summary() -> str:
    return f"""
<div class="section">
  <div class="section-header">
    <h2>1. Executive Summary</h2>
    <div class="smeta">Claude SEO v1.9.0, April 2026</div>
  </div>

  <p>v1.9.0 is the first community-driven release. Six members submitted skills for the inaugural Pro Hub Challenge. Five shipped. Four are entirely new Tier-4 skills. The release also adds DataForSEO cost guardrails and passed a four-round quality review including a dedicated cybersecurity audit.</p>

  <div class="four-col">
    <div class="col">{_mc("23", "Total Skills", "+4 new")}</div>
    <div class="col">{_mc("17", "Subagents", "+4 new")}</div>
    <div class="col">{_mc("30", "Scripts", "+7 new")}</div>
    <div class="col">{_mc("61", "Files Changed", "31 mod, 30 new")}</div>
  </div>

  <div class="four-col">
    <div class="col">{_mc("6", "Submissions", "Pro Hub Challenge")}</div>
    <div class="col">{_mc("5", "Integrated", "4 new, 1 enhanced")}</div>
    <div class="col">{_mc("85/100", "Security", "4 fixes applied")}</div>
    <div class="col">{_mc("4", "Review Rounds", "Peak: 97/100")}</div>
  </div>

  <div class="two-col" style="margin-top:4mm;">
    <div class="col">
      <div class="success-box">
        <h4 style="margin-top:0; border:none; padding:0; color:#4ADE80;">Community</h4>
        <ul>
          <li>First Pro Hub Challenge, $600 Claude Credits prize pool</li>
          <li>5 of 6 submissions integrated into the official release</li>
          <li>4 new skills added to the ecosystem</li>
          <li>All contributors credited in CONTRIBUTORS.md and skill frontmatter</li>
        </ul>
      </div>
    </div>
    <div class="col">
      <div class="info-box">
        <h4 style="margin-top:0; border:none; padding:0; color:#60A5FA;">Technical</h4>
        <ul>
          <li>XSS in cluster-map.html fixed with escapeHtml() wrapping</li>
          <li>Cost guardrail bypass chain discovered and closed</li>
          <li>fcntl file locking for concurrent agent safety</li>
          <li>CI expanded from 21 to 28 tracked scripts</li>
        </ul>
      </div>
    </div>
  </div>
</div>
"""


def _build_challenge_section(chart_path: str, fig_num: int, ss: Path = None) -> tuple:
    chart = _chart_html(chart_path,
                        "Pro Hub Challenge: 6 submissions through review to integration outcomes",
                        fig_num)
    ss = ss or Path(SCREENSHOTS_DIR)
    post_img   = _screenshot_html(str(ss / "Pro hub challenge post.png"),
                                  "Original challenge announcement post", max_h="62mm")
    winner_img = _screenshot_html(str(ss / "Pro hub challenge post winner.png"),
                                  "Winner announcement in AI Marketing Hub Pro", max_h="62mm")
    html = f"""
<div class="section">
  <div class="section-header">
    <h2>2. Pro Hub Challenge</h2>
    <div class="smeta">Community, $600 Claude Credits Prize Pool, 6 Submissions</div>
  </div>

  <p>The Pro Hub Challenge is a community extension program in AI Marketing Hub Pro. Members submit Claude Code skills for claude-seo or related tools. Winning submissions get integrated into the official release. The inaugural challenge offered $600 in Claude Credits across prize tiers.</p>

  {chart}

  <h3>Timeline</h3>
  <table>
    <thead><tr><th>Stage</th><th>Outcome</th></tr></thead>
    <tbody>
      <tr><td>Challenge announced</td><td>$600 prize pool declared</td></tr>
      <tr><td>Submissions closed</td><td>6 entries received</td></tr>
      <tr><td>Round 1: code review</td><td>87/100</td></tr>
      <tr><td>Round 2: re-review</td><td>93/100</td></tr>
      <tr><td>Round 3: max-effort plan</td><td>97/100</td></tr>
      <tr><td>Round 4: cybersecurity audit</td><td>85/100</td></tr>
      <tr><td>Security fixes applied</td><td>4 vulnerabilities resolved</td></tr>
      <tr><td>v1.9.0 shipped</td><td>5 of 6 integrated</td></tr>
    </tbody>
  </table>

  <h3>Announcement &amp; Winners</h3>
  {post_img}
  {winner_img}
</div>
"""
    return html, fig_num + 1


def _build_contributions_section(ss: Path = None) -> str:
    ss = ss or Path(SCREENSHOTS_DIR)
    contributors = [
        {
            "name":  "Lutfiya Miller",
            "skill": "/seo cluster",
            "type":  "New Skill",
            "img":   str(ss / "Lutfiya.png"),
            "desc":  "SERP-based semantic topic clustering. Groups keywords by Google result overlap: 7-10 shared results is the same post, 4-6 is a hub cluster, 2-3 are interlink candidates.",
            "points": [
                "Interactive SVG cluster-map.html visualization (hub-spoke layout)",
                "No paid API required: uses SERP overlap algorithm",
                "XSS in SVG rendering fixed during integration (escapeHtml wrapping)",
                "De-branded from original submission",
            ],
        },
        {
            "name":  "Florian Schmitz",
            "skill": "/seo sxo",
            "type":  "New Skill",
            "img":   str(ss / "florian.png"),
            "desc":  "Search Experience Optimization. Analyzes page-type mismatch between what Google serves and what the page delivers. Surfaces intent gaps that kill rankings despite strong technical SEO.",
            "points": [
                "Page-type taxonomy: informational, transactional, navigational, commercial",
                "Persona scoring: visitor intent vs. page intent alignment",
                "Consolidated from four original SKILL.md files that each exceeded 500 lines",
            ],
        },
        {
            "name":  "Dan Colta",
            "skill": "/seo drift",
            "type":  "New Skill",
            "img":   str(ss / "dan.png"),
            "desc":  "Git for SEO. Captures baselines of SEO-critical page elements, then diffs against current state to catch regressions before they impact rankings.",
            "points": [
                "17 comparison rules across 3 severity levels (CRITICAL, WARNING, INFO)",
                "SQLite persistence at ~/.cache/claude-seo/drift/baselines.db",
                "Parameterized SQL throughout, html.escape() on all report output",
            ],
        },
        {
            "name":  "Matej Marjanovic",
            "skill": "/seo ecommerce",
            "type":  "New Skill",
            "img":   str(ss / "Matej.png"),
            "desc":  "E-commerce SEO covering product schema, marketplace intelligence via DataForSEO Merchant API (Google Shopping and Amazon), and category page optimization.",
            "points": [
                "Product and ItemList schema templates added to schema/templates.json",
                "DataForSEO Merchant API integration for live competitive pricing",
                "Category hierarchy and breadcrumb analysis",
            ],
        },
        {
            "name":  "Chris Muller",
            "skill": "/seo hreflang",
            "type":  "Enhancement",
            "img":   str(ss / "chris.png"),
            "desc":  "Extended seo-hreflang with Cultural Adaptation Profiles for DACH, French, Spanish, and Japanese markets. Covers number formats, date conventions, currency display, and content parity.",
            "points": [
                "4 cultural profiles: DACH (de-AT/CH/DE), fr-FR, es-ES/MX, ja-JP",
                "Locale format reference: number, date, currency conventions per region",
                "3 new reference files in skills/seo-hreflang/references/",
            ],
        },
    ]

    cards = ""
    for c in contributors:
        points = "".join(f"<li>{p}</li>" for p in c["points"])
        type_color = "#E07850" if c["type"] == "New Skill" else "#4ADE80"
        sshot = _screenshot_html(c["img"], f"{c['name']}'s submission post", max_h="52mm")
        cards += f"""<div class="ccard">
  <h4>{c["name"]} &ndash; <span style="color:#60A5FA;">{c["skill"]}</span>
    <span style="float:right; font-size:8pt; color:{type_color}; font-weight:bold;">{c["type"]}</span>
  </h4>
  <div class="cmeta">Pro Hub Challenge submission, integrated in v1.9.0</div>
  <p>{c["desc"]}</p>
  <ul>{points}</ul>
  {sshot}
</div>
"""

    return f"""
<div class="section">
  <div class="section-header">
    <h2>3. Community Contributions</h2>
    <div class="smeta">5 Integrations, 4 New Skills, 1 Enhancement</div>
  </div>

  <p>Each submission passed code review, security audit, de-branding check, and line-limit check (SKILL.md at 500 lines max, reference files at 200 lines max). Security fixes were applied to three submissions during integration.</p>

{cards}
</div>
"""


def _build_architecture_section(chart_path: str, fig_num: int) -> tuple:
    chart = _chart_html(chart_path,
                        "Claude SEO skill architecture: 23 skills by category (orange = v1.9.0 additions)",
                        fig_num)
    html = f"""
<div class="section">
  <div class="section-header">
    <h2>4. Architecture Evolution</h2>
    <div class="smeta">Skills 19 to 23, Agents 13 to 17, Scripts 23 to 30</div>
  </div>

  <h3>Skill Architecture Map</h3>
  {chart}

  <h3>Before / After</h3>
  <table>
    <thead><tr><th>Component</th><th>v1.8.2</th><th>v1.9.0</th><th>Delta</th></tr></thead>
    <tbody>
      <tr><td>Skills (SKILL.md directories)</td><td>19</td><td>23</td><td class="st-new">+4</td></tr>
      <tr><td>Subagents (agents/*.md)</td><td>13</td><td>17</td><td class="st-new">+4</td></tr>
      <tr><td>Python scripts (CI-tracked)</td><td>23</td><td>30</td><td class="st-new">+7</td></tr>
      <tr><td>Reference files</td><td>~25</td><td>~38</td><td class="st-new">+13</td></tr>
      <tr><td>Schema templates</td><td>8</td><td>10</td><td class="st-new">+2</td></tr>
      <tr><td>Orchestrator routing commands</td><td>18</td><td>23</td><td class="st-new">+5</td></tr>
    </tbody>
  </table>

  <h3>New Scripts (7)</h3>
  <p>Seven new Python scripts shipped with v1.9.0. DataForSEO additions: <code>dataforseo_costs.py</code> (cost estimation, approval workflow, fcntl budget locking), <code>dataforseo_merchant.py</code> (Google Shopping + Amazon via Merchant API), <code>dataforseo_normalize.py</code> (shared response normalization). SEO drift additions: <code>drift_baseline.py</code> (SQLite baseline capture, SSRF-protected), <code>drift_compare.py</code> (17-rule comparison engine, parameterized SQL), <code>drift_report.py</code> (HTML reporting with html.escape() throughout), <code>drift_history.py</code> (read-only timeline query).</p>
</div>
"""
    return html, fig_num + 1


def _build_review_section(chart_path: str, fig_num: int) -> tuple:
    chart = _chart_html(chart_path,
                        "Review score progression across 4 rounds: peak 97/100, security audit 85/100",
                        fig_num)
    html = f"""
<div class="section">
  <div class="section-header">
    <h2>5. Review Process</h2>
    <div class="smeta">4 Rounds, Peak 97/100, 8+ Issues Caught</div>
  </div>

  <h3>Score Progression</h3>
  {chart}

  <h3>What Each Round Caught</h3>
  <table>
    <thead>
      <tr><th>Round</th><th>Score</th><th>Key Findings</th></tr>
    </thead>
    <tbody>
      <tr>
        <td>1: Code Review</td><td>87/100</td>
        <td>Step numbering collision in orchestrator. Agent count wrong in seo-audit skill.</td>
      </tr>
      <tr>
        <td>2: Re-Review</td><td>93/100</td>
        <td>install.ps1 version not bumped. AGENTS.md count off by one. Dead import in dataforseo_merchant.py.</td>
      </tr>
      <tr>
        <td>3: Max-Effort Plan</td><td>97/100</td>
        <td>CONTRIBUTING.md insertion at line 25 would have orphaned subsections. New commands placed in wrong location in README.</td>
      </tr>
      <tr>
        <td>4: Security Audit</td><td>85/100</td>
        <td>XSS in SVG rendering. Cost guardrail bypass chain. CI coverage gap. Concurrent write race condition in cost ledger.</td>
      </tr>
    </tbody>
  </table>
</div>
"""
    return html, fig_num + 1


def _build_security_section(chart_path: str, fig_num: int) -> tuple:
    chart = _chart_html(chart_path,
                        "Security findings by severity: 4 fixed in v1.9.0, 11 deferred to v1.9.1",
                        fig_num)
    html = f"""
<div class="section">
  <div class="section-header">
    <h2>6. Security Audit</h2>
    <div class="smeta">85/100, OWASP Top 10:2025, STRIDE, MITRE ATT&amp;CK, 8 Specialist Agents</div>
  </div>

  <p>The /cybersecurity skill ran an 8-agent parallel audit: vulnerability scanning, authentication, secrets detection, dependency analysis, infrastructure-as-code, threat intelligence, AI-generated code patterns, and business logic. 15 findings total across 3 severity tiers. 10 of the 11 deferred findings were already present in v1.8.x. The audit formally documented them for the first time. All deferred items target v1.9.1.</p>

  <h3>Findings Distribution</h3>
  {chart}

  <h3>Fixes Applied in v1.9.0</h3>
  <table>
    <thead><tr><th>Finding</th><th>Severity</th><th>Resolution</th></tr></thead>
    <tbody>
      <tr>
        <td>XSS in cluster-map.html: truncate() output inserted raw into SVG DOM</td>
        <td class="sev-high">HIGH</td>
        <td class="st-fixed">Fixed: escapeHtml() added at render points</td>
      </tr>
      <tr>
        <td>Cost guardrail bypass: unknown endpoint defaulted to $0.05, reset cleared spend without confirmation</td>
        <td class="sev-high">HIGH</td>
        <td class="st-fixed">Fixed: unknown endpoint returns needs_approval, reset requires --confirm with audit trail</td>
      </tr>
      <tr>
        <td>CI coverage gap: 7 new scripts absent from compile check</td>
        <td class="sev-medium">MEDIUM</td>
        <td class="st-fixed">Fixed: ci.yml expanded from 21 to 28 tracked scripts</td>
      </tr>
      <tr>
        <td>Concurrent write race condition in cost ledger</td>
        <td class="sev-medium">MEDIUM</td>
        <td class="st-fixed">Fixed: fcntl shared lock for reads, exclusive for writes</td>
      </tr>
    </tbody>
  </table>
</div>
"""
    return html, fig_num + 1


def _build_guardrails_section() -> str:
    return """
<div class="section">
  <div class="section-header">
    <h2>7. DataForSEO Cost Guardrails</h2>
    <div class="smeta">Technical Deep-Dive, Approval Workflow, fcntl Locking</div>
  </div>

  <p>DataForSEO calls accumulate cost fast when multiple subagents run in parallel. v1.9.0 adds a cost estimation and approval workflow in <code>scripts/dataforseo_costs.py</code>.</p>

  <h3>The Bypass Chain (Closed)</h3>
  <ol>
    <li>Unknown endpoints defaulted to $0.05 per call, bypassing the approval gate by using an undocumented endpoint name.</li>
    <li>The reset command cleared cumulative spend with no confirmation, letting a misconfigured agent wipe the budget ledger and restart a spending cycle.</li>
  </ol>

  <div class="code-block"># Unknown endpoint: explicit approval required
unit_cost = COST_TABLE.get(endpoint)
if unit_cost is None:
    return {"status": "needs_approval", "approval_reason": "unknown_endpoint", ...}

# Reset requires --confirm and logs a tamper-evident audit entry
def cmd_reset(args):
    if not args.confirm:
        return {"status": "blocked", "message": "Reset requires --confirm flag."}</div>

  <h3>Concurrent Safety</h3>
  <p>The cost ledger is a JSON file read and written by multiple parallel subagents. v1.9.0 adds <code>fcntl.flock()</code>: shared lock for reads, exclusive lock for writes. Windows falls back to an unguarded write with a warning.</p>
</div>
"""


def _build_next_section() -> str:
    return """
<div class="section">
  <div class="section-header">
    <h2>8. What's Next</h2>
    <div class="smeta">v1.9.1 Security Priorities, Community Growth</div>
  </div>

  <div class="ritem high">
    <h4>H1: validate_url() DNS Rebinding Gap
      <span style="float:right; color:#f59e0b; font-size:8.5pt;">HIGH, Deferred</span>
    </h4>
    <p>validate_url() checks IPs at parse time but not at request time. A DNS rebinding attack can serve a public IP at validation, then switch to a private address at request. Fix: re-validate resolved IPs at the socket layer.</p>
  </div>

  <div class="ritem high">
    <h4>H2: Install Script Shell Injection
      <span style="float:right; color:#f59e0b; font-size:8.5pt;">HIGH, Deferred</span>
    </h4>
    <p>install.sh and install.ps1 use unquoted variables. A path with spaces or shell metacharacters could inject commands. Fix: quote all variable expansions.</p>
  </div>

  <div class="ritem medium">
    <h4>M1: OAuth Token File Permissions (0644)
      <span style="float:right; color:#60A5FA; font-size:8.5pt;">MEDIUM, Deferred</span>
    </h4>
    <p>OAuth token files are written with default permissions, making them world-readable on systems with permissive umask. Fix: chmod 600 immediately after writing.</p>
  </div>

  <div class="success-box" style="margin-top:5mm;">
    <h4 style="margin-top:0; border:none; padding:0; color:#4ADE80;">April Challenge. $600. One Word.</h4>
    <p>Challenge v2 is live in AI Marketing Hub Pro. The keyword is <strong style="color:#4ADE80;">LEADS</strong>. Build anything that touches lead generation: Claude Code skills, n8n workflows, MCP servers, dashboards, scrapers, pipelines. If it helps someone capture, qualify, nurture, or convert leads, it counts.</p>
    <div style="display:table; width:100%; margin-top:3mm;">
      <div style="display:table-cell; width:50%; vertical-align:top;">
        <p style="margin-bottom:1mm;"><strong>Prizes</strong></p>
        <ul style="margin-bottom:0;">
          <li>1st Place: $400 in Claude Credits</li>
          <li>2nd Place: $200 in Claude Credits</li>
        </ul>
      </div>
      <div style="display:table-cell; width:50%; vertical-align:top;">
        <p style="margin-bottom:1mm;"><strong>Rules</strong></p>
        <ul style="margin-bottom:0;">
          <li>GitHub repo or .zip + 1-2 min demo video</li>
          <li>Must be functional, solo or team welcome</li>
          <li>Deadline: April 28</li>
        </ul>
      </div>
    </div>
  </div>

  <hr class="divider">
  <p style="font-size:8.5pt; color:#888888; text-align:center; margin-top:4mm;">
    Claude SEO is open-source (Agent Skills standard) &nbsp;&#183;&nbsp;
    github.com/AgriciDaniel/claude-seo &nbsp;&#183;&nbsp;
    AI Marketing Hub: skool.com/ai-marketing-hub-pro
  </p>
</div>
"""


# --- PDF Review ---

def _review_pdf(pdf_path: Path, html_content: str) -> dict:
    issues = []
    result: dict = {"status": "PASS", "issues": []}

    if not pdf_path.exists():
        return {"status": "FAIL", "issues": ["PDF not created"]}

    size_kb = pdf_path.stat().st_size / 1024
    result["file_size_kb"] = round(size_kb, 1)

    if size_kb < 30:
        issues.append(f"PDF suspiciously small: {size_kb:.1f} KB")

    section_count = html_content.count('class="section"')
    if section_count < 6:
        issues.append(f"Only {section_count} sections (expected >= 6)")

    chart_count = html_content.count("chart-container")
    if chart_count < 4:
        issues.append(f"Only {chart_count} charts (expected 4)")

    from urllib.parse import unquote
    for img_path_raw in re.findall(r'src="file://([^"]+)"', html_content):
        img_path = unquote(img_path_raw)
        if not Path(img_path).exists():
            issues.append(f"Missing image: {img_path}")

    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        result["page_count"] = len(reader.pages)
        if len(reader.pages) < 10:
            issues.append(f"Only {len(reader.pages)} pages (expected >= 10)")
    except ImportError:
        result["page_count"] = "unknown (install pypdf)"

    if issues:
        result["status"] = f"WARN ({len(issues)} issues)"
        result["issues"] = issues
    return result


# --- Report Generation ---

def generate_report(output_dir: str, screenshots_dir: str = SCREENSHOTS_DIR) -> str:
    out = Path(output_dir).expanduser().resolve()
    charts_dir = out / "claude-seo-v190-charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    ss = Path(screenshots_dir)
    # Use white-text logo for dark background (note: double space in filename)
    logo_path = str(ss / "AI MArketing hub  pro logo with white text.png")
    if not Path(logo_path).exists():
        logo_path = str(ss / "AI MArketing hub  pro logo with black text.png")

    pdf_path = out / "Claude-SEO-v1.9.0-Release-Report.pdf"

    print("Generating charts...")
    flow_path   = chart_contribution_flow(charts_dir)
    arch_path   = chart_skill_architecture(charts_dir)
    review_path = chart_review_scores(charts_dir)
    sec_path    = chart_security_matrix(charts_dir)
    print(f"  4 charts saved to {charts_dir}")

    fig_n = [1]

    def nf() -> int:
        n = fig_n[0]; fig_n[0] += 1; return n

    print("Building HTML sections...")
    challenge_html, _ = _build_challenge_section(flow_path, nf(), ss)
    arch_html, _      = _build_architecture_section(arch_path, nf())
    review_html, _    = _build_review_section(review_path, nf())
    sec_html, _       = _build_security_section(sec_path, nf())

    sections = [
        _build_title_page(logo_path),
        _build_toc(),
        _build_executive_summary(),
        challenge_html,
        _build_contributions_section(ss),
        arch_html,
        review_html,
        sec_html,
        _build_guardrails_section(),
        _build_next_section(),
    ]

    full_html = _build_css() + "\n".join(sections)

    print("Rendering PDF via WeasyPrint...")
    try:
        from weasyprint import HTML
        HTML(string=full_html).write_pdf(str(pdf_path))
    except ImportError:
        html_out = out / "Claude-SEO-v1.9.0-Release-Report.html"
        html_out.write_text(full_html, encoding="utf-8")
        print(f"WeasyPrint not installed. HTML saved: {html_out}")
        return str(html_out)

    print("Running quality check...")
    review = _review_pdf(pdf_path, full_html)
    print(f"  Status  : {review['status']}")
    print(f"  Pages   : {review.get('page_count', '?')}")
    print(f"  Size    : {review.get('file_size_kb', '?')} KB")
    for issue in review.get("issues", []):
        print(f"  WARNING : {issue}")

    print(f"\nReport saved: {pdf_path}")
    return str(pdf_path)


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(
        description="Generate Claude SEO v1.9.0 Pro Hub Challenge Release Report"
    )
    parser.add_argument("--output", "-o", default="~/Desktop",
                        help="Output directory (default: ~/Desktop)")
    parser.add_argument("--screenshots", default=SCREENSHOTS_DIR,
                        help=f"Screenshots directory (default: {SCREENSHOTS_DIR})")
    args = parser.parse_args()

    try:
        path = generate_report(args.output, args.screenshots)
        print(json.dumps({"status": "success", "path": path}, indent=2))
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2),
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
