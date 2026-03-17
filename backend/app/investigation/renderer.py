from __future__ import annotations

from html import escape
from typing import Any


def render_investigation_html(report: dict[str, Any], *, canonical_url: str, version_number: int) -> str:
    summary = report.get("summary", {})
    metrics = report.get("metrics", {})
    confidence = report.get("confidence", {})
    methodology = report.get("methodology", {})
    timeline = report.get("timeline", [])
    anomalies = report.get("anomalies", [])
    evidence = report.get("evidence", [])
    rtr = report.get("right_to_respond", {})

    def _li(items: list[str]) -> str:
        return "".join(f"<li>{escape(item)}</li>" for item in items)

    timeline_rows = "".join(
        (
            "<li>"
            f"<strong>{escape(item.get('event_type', 'EVENT').replace('_', ' '))}</strong> "
            f"({escape(str(item.get('date', '')))}): {escape(str(item.get('title') or ''))}. "
            f"{escape(str(item.get('details') or ''))}"
            "</li>"
        )
        for item in timeline
    )

    anomaly_rows = "".join(
        (
            "<li>"
            f"<strong>{escape(str(item.get('title') or 'Pattern'))}</strong>: "
            f"{escape(str(item.get('details') or ''))}"
            "</li>"
        )
        for item in anomalies
    )

    evidence_rows = "".join(
        (
            "<li>"
            f"{escape(str(item.get('label') or 'Evidence'))}: "
            f"<a href=\"{escape(str(item.get('source_url') or '#'))}\">source</a>"
            "</li>"
        )
        for item in evidence
    )

    response_rows = ""
    for item in rtr.get("responses", []):
        response_rows += (
            "<article class=\"response-card\">"
            f"<h4>{escape(str(item.get('statement') or 'Official response'))}</h4>"
            f"<p>Status: {escape(str(item.get('verification_status') or 'pending'))}</p>"
            f"<p>{escape(str(item.get('content') or 'Response published in limited form.'))}</p>"
            "</article>"
        )

    return f"""<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>{escape(str(summary.get('headline') or 'Investigation report'))}</title>
<meta name=\"description\" content=\"{escape(str(summary.get('narrative') or 'Investigation report'))}\" />
<link rel=\"canonical\" href=\"{escape(canonical_url)}\" />
<style>
:root {{
  --bg: #f5f1ea;
  --ink: #1f2a37;
  --accent: #aa3a2a;
  --card: #fffdf8;
}}
body {{ margin: 0; background: radial-gradient(circle at top right, #efe3d0, var(--bg)); color: var(--ink); font-family: Georgia, 'Times New Roman', serif; line-height: 1.5; }}
main {{ max-width: 980px; margin: 0 auto; padding: 28px 16px 64px; }}
header {{ border-bottom: 2px solid #d9c3a4; margin-bottom: 20px; }}
h1 {{ margin: 0 0 6px; font-size: 2rem; }}
section {{ background: var(--card); border: 1px solid #e6d6be; border-radius: 12px; padding: 14px; margin-top: 14px; box-shadow: 0 2px 6px rgba(0,0,0,.04); }}
.metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
.metric {{ background: #fff7ea; border: 1px solid #efd8b4; border-radius: 10px; padding: 8px; }}
small, .muted {{ color: #5d6773; }}
.response-card {{ background: #fff7f2; border-left: 4px solid var(--accent); padding: 10px; margin-bottom: 10px; }}
a {{ color: #7b2e20; }}
</style>
</head>
<body>
<main>
<header>
  <h1>{escape(str(summary.get('headline') or 'Investigation report'))}</h1>
  <p>{escape(str(summary.get('narrative') or ''))}</p>
  <p class=\"muted\">Case UID: {escape(str(summary.get('case_uid') or ''))} | Version: {version_number}</p>
</header>
<section>
  <h2>Case Summary</h2>
  <p>Court: {escape(str(summary.get('court') or 'Unknown'))}, State: {escape(str(summary.get('state') or 'Unknown'))}, Status: {escape(str(summary.get('status') or 'Unknown'))}</p>
  <p>Last updated: {escape(str(report.get('last_updated') or 'unknown'))}</p>
</section>
<section>
  <h2>Key Metrics</h2>
  <div class=\"metrics\">
    <div class=\"metric\"><strong>Total Duration (years)</strong><div>{escape(str(metrics.get('total_duration_years')))}</div></div>
    <div class=\"metric\"><strong>Normalized Delay</strong><div>{escape(str(metrics.get('normalized_delay')))}</div></div>
    <div class=\"metric\"><strong>Percentile Rank</strong><div>{escape(str(metrics.get('percentile_ranking')))}</div></div>
    <div class=\"metric\"><strong>Strategic Delay Score</strong><div>{escape(str(metrics.get('strategic_delay_score')))}</div></div>
    <div class=\"metric\"><strong>Survival Probability</strong><div>{escape(str(metrics.get('survival_probability')))}</div></div>
  </div>
</section>
<section><h2>Timeline of Events</h2><ol>{timeline_rows}</ol></section>
<section><h2>Detected Anomalies and Patterns</h2><ul>{anomaly_rows or '<li>No active anomaly flags at this time.</li>'}</ul></section>
<section><h2>Evidence Sources</h2><ul>{evidence_rows}</ul></section>
<section>
  <h2>Methodology</h2>
  <h3>Data Sources</h3><ul>{_li([str(v) for v in methodology.get('data_sources', [])])}</ul>
  <h3>Algorithms Used</h3><ul>{_li([str(v) for v in methodology.get('algorithms', [])])}</ul>
  <h3>Limitations</h3><ul>{_li([str(v) for v in methodology.get('limitations', [])])}</ul>
  <p>Update frequency: {escape(str(methodology.get('update_frequency') or 'not specified'))}</p>
</section>
<section>
  <h2>Confidence Indicators</h2>
  <p>Confidence score: {escape(str(confidence.get('score')))}</p>
  <p>{escape(str(confidence.get('coverage_limitations') or ''))}</p>
  <p>{escape(str(confidence.get('non_accusatory_disclaimer') or ''))}</p>
</section>
<section>
  <h2>Right to Respond</h2>
  {response_rows if rtr.get('present') else '<p>No official response published yet.</p>'}
</section>
<section>
  <h2>Version History</h2>
  <p>This page is a versioned snapshot suitable for citation and archival reference.</p>
  <p>Canonical URL: <a href=\"{escape(canonical_url)}\">{escape(canonical_url)}</a></p>
</section>
<section>
  <h2>Disclaimer</h2>
  <small>{escape(str(report.get('disclaimer') or ''))}</small>
</section>
</main>
</body>
</html>
"""
