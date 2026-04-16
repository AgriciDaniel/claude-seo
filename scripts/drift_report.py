#!/usr/bin/env python3
"""
Generate an HTML report for SEO drift comparison results.

Uses the claude-seo color palette for severity-coded cards.

Usage:
    python drift_report.py <comparison_json_file> [--output report.html]
    echo '{"status":"ok",...}' | python drift_report.py --stdin [--output report.html]

Output: Self-contained HTML file with severity-coded diff cards.
"""

import argparse
import html
import json
import os
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Claude-SEO color palette
# ---------------------------------------------------------------------------
COLORS = {
    "navy": "#1e3a5f",
    "gold": "#b8860b",
    "green": "#2d6a4f",
    "amber": "#d4740e",
    "red": "#c53030",
    "cream": "#faf9f7",
    "white": "#ffffff",
    "light_gray": "#f3f4f6",
    "mid_gray": "#6b7280",
    "dark_gray": "#374151",
}

SEVERITY_COLORS = {
    "CRITICAL": COLORS["red"],
    "WARNING": COLORS["amber"],
    "INFO": COLORS["navy"],
}

SEVERITY_BG = {
    "CRITICAL": "#fef2f2",
    "WARNING": "#fffbeb",
    "INFO": "#eff6ff",
}


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def _escape(text) -> str:
    """HTML-escape a value, handling None."""
    if text is None:
        return "<em>none</em>"
    return html.escape(str(text))


def generate_html(comparison: dict) -> str:
    """Generate a self-contained HTML report from comparison data."""
    url = comparison.get("url", "Unknown URL")
    baseline_ts = comparison.get("baseline_timestamp", "")
    compare_ts = comparison.get("comparison_timestamp", "")
    summary = comparison.get("summary", {})
    triggered = comparison.get("triggered_findings", [])
    untriggered = comparison.get("untriggered_findings", [])

    critical = summary.get("critical", 0)
    warning = summary.get("warning", 0)
    info = summary.get("info", 0)
    total_triggered = summary.get("triggered", 0)

    # Overall status badge
    if critical > 0:
        status_text = "DRIFT DETECTED"
        status_color = COLORS["red"]
    elif warning > 0:
        status_text = "CHANGES DETECTED"
        status_color = COLORS["amber"]
    elif info > 0:
        status_text = "MINOR CHANGES"
        status_color = COLORS["navy"]
    else:
        status_text = "NO DRIFT"
        status_color = COLORS["green"]

    # Build finding cards
    finding_cards = ""
    for finding in triggered:
        sev = finding.get("severity", "INFO")
        color = SEVERITY_COLORS.get(sev, COLORS["navy"])
        bg = SEVERITY_BG.get(sev, COLORS["light_gray"])
        finding_cards += f"""
        <div class="finding-card" style="border-left: 4px solid {color}; background: {bg};">
            <div class="finding-header">
                <span class="severity-badge" style="background: {color}; color: {COLORS['white']};">{sev}</span>
                <span class="rule-name">{_escape(finding.get('rule', ''))}</span>
            </div>
            <p class="finding-message">{_escape(finding.get('message', ''))}</p>
            <div class="finding-diff">
                <div class="diff-old">
                    <strong>Before:</strong> {_escape(finding.get('old_value'))}
                </div>
                <div class="diff-new">
                    <strong>After:</strong> {_escape(finding.get('new_value'))}
                </div>
            </div>
        </div>
        """

    # Passed rules summary
    passed_list = ""
    for finding in untriggered:
        passed_list += f"<li>{_escape(finding.get('rule', ''))}: {_escape(finding.get('message', ''))}</li>\n"

    report_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO Drift Report - {_escape(url)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Times New Roman', Georgia, serif;
            background: {COLORS['cream']};
            color: {COLORS['dark_gray']};
            line-height: 1.6;
            padding: 2rem;
            max-width: 900px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            padding: 2rem;
            background: {COLORS['navy']};
            color: {COLORS['white']};
            border-radius: 8px;
            margin-bottom: 2rem;
        }}
        .header h1 {{
            font-size: 1.8rem;
            margin-bottom: 0.5rem;
        }}
        .header .url {{
            font-family: monospace;
            font-size: 0.95rem;
            opacity: 0.9;
            word-break: break-all;
        }}
        .header .timestamps {{
            font-size: 0.85rem;
            opacity: 0.7;
            margin-top: 0.5rem;
        }}
        .status-banner {{
            text-align: center;
            padding: 1rem;
            border-radius: 8px;
            font-size: 1.4rem;
            font-weight: bold;
            margin-bottom: 2rem;
            color: {COLORS['white']};
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .summary-card {{
            text-align: center;
            padding: 1rem;
            border-radius: 8px;
            background: {COLORS['white']};
            border: 1px solid #e5e7eb;
        }}
        .summary-card .count {{
            font-size: 2rem;
            font-weight: bold;
        }}
        .summary-card .label {{
            font-size: 0.85rem;
            color: {COLORS['mid_gray']};
        }}
        .section-title {{
            font-size: 1.3rem;
            color: {COLORS['navy']};
            border-bottom: 2px solid {COLORS['gold']};
            padding-bottom: 0.5rem;
            margin: 2rem 0 1rem;
        }}
        .finding-card {{
            padding: 1rem;
            border-radius: 6px;
            margin-bottom: 1rem;
        }}
        .finding-header {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 0.5rem;
        }}
        .severity-badge {{
            display: inline-block;
            padding: 0.15rem 0.6rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: bold;
            font-family: sans-serif;
            letter-spacing: 0.05em;
        }}
        .rule-name {{
            font-family: monospace;
            font-size: 0.9rem;
            color: {COLORS['mid_gray']};
        }}
        .finding-message {{
            margin-bottom: 0.75rem;
        }}
        .finding-diff {{
            font-family: monospace;
            font-size: 0.85rem;
            background: {COLORS['white']};
            padding: 0.75rem;
            border-radius: 4px;
            border: 1px solid #e5e7eb;
        }}
        .diff-old {{
            color: {COLORS['red']};
            margin-bottom: 0.3rem;
        }}
        .diff-new {{
            color: {COLORS['green']};
        }}
        .passed-section {{
            background: {COLORS['white']};
            padding: 1rem;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
        }}
        .passed-section ul {{
            list-style: none;
            padding: 0;
        }}
        .passed-section li {{
            padding: 0.3rem 0;
            font-size: 0.9rem;
            color: {COLORS['mid_gray']};
        }}
        .passed-section li::before {{
            content: "\\2713 ";
            color: {COLORS['green']};
            font-weight: bold;
        }}
        .footer {{
            text-align: center;
            margin-top: 2rem;
            padding: 1rem;
            font-size: 0.8rem;
            color: {COLORS['mid_gray']};
            border-top: 1px solid #e5e7eb;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>SEO Drift Report</h1>
        <div class="url">{_escape(url)}</div>
        <div class="timestamps">
            Baseline: {_escape(baseline_ts)} | Compared: {_escape(compare_ts)}
        </div>
    </div>

    <div class="status-banner" style="background: {status_color};">
        {status_text}
    </div>

    <div class="summary-grid">
        <div class="summary-card">
            <div class="count" style="color: {COLORS['red']};">{critical}</div>
            <div class="label">Critical</div>
        </div>
        <div class="summary-card">
            <div class="count" style="color: {COLORS['amber']};">{warning}</div>
            <div class="label">Warning</div>
        </div>
        <div class="summary-card">
            <div class="count" style="color: {COLORS['navy']};">{info}</div>
            <div class="label">Info</div>
        </div>
    </div>

    {"<h2 class='section-title'>Findings (" + str(total_triggered) + " triggered)</h2>" + finding_cards if total_triggered > 0 else ""}

    <h2 class="section-title">Passed Checks ({len(untriggered)})</h2>
    <div class="passed-section">
        <ul>
            {passed_list}
        </ul>
    </div>

    <div class="footer">
        Generated by Claude SEO Drift Monitor | {report_time}
    </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate an HTML report from SEO drift comparison results"
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to comparison JSON file (or use --stdin)",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read comparison JSON from stdin",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output HTML file path (default: stdout)",
    )

    args = parser.parse_args()

    # Load comparison data
    if args.stdin:
        raw = sys.stdin.read()
    elif args.file:
        real_path = os.path.realpath(args.file)
        if not os.path.isfile(real_path):
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(real_path, "r", encoding="utf-8") as f:
            raw = f.read()
    else:
        print("Error: Provide a JSON file path or use --stdin", file=sys.stderr)
        sys.exit(1)

    try:
        comparison = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if comparison.get("error"):
        print(f"Error: Comparison has error: {comparison['error']}", file=sys.stderr)
        sys.exit(1)

    html_content = generate_html(comparison)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Report saved to {args.output}", file=sys.stderr)
    else:
        print(html_content)


if __name__ == "__main__":
    main()
