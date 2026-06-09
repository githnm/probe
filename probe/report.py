"""Report assembly and formatting (markdown, JSON)."""

from __future__ import annotations

from probe import Explanation, ProbeResult, Report  # noqa: I001

_SEVERITY_SYMBOL = {"info": "i", "warn": "!", "block": "X"}
_STATUS_SYMBOL = {"ok": ".", "changed": "~", "unverified": "?"}


def render_terminal(report: Report) -> str:
    lines: list[str] = []
    sym = _SEVERITY_SYMBOL.get(report.severity, "?")
    lines.append(f"[{sym}] Probe Report  (severity: {report.severity})")
    if report.scope:
        lines.append(f"    scope: {', '.join(report.scope)}")
    lines.append("")
    if report.explanation:
        lines.append(_render_explanation_terminal(report.explanation))
        lines.append("")
    for r in report.results:
        lines.append(_render_finding_terminal(r))
    return "\n".join(lines)


def _render_explanation_terminal(exp: Explanation) -> str:
    lines = [
        "  Explanation:",
        f"    {exp.summary}",
    ]
    for f in exp.findings:
        tag = "confirmed" if f.confirmed else "unconfirmed"
        backed = f" (backed by: {f.backed_by})" if f.backed_by else ""
        lines.append(f"    - [{tag}] {f.claim}{backed}")
    return "\n".join(lines)


def _render_finding_terminal(r: ProbeResult) -> str:
    sym = _STATUS_SYMBOL.get(r.status, "?")
    lines = [
        f"  [{sym}] {r.name}: {r.question}",
        f"      old: {r.old_value}",
        f"      new: {r.new_value}",
        f"      delta: {r.delta}  (status: {r.status})",
        "      receipt:",
        f"        sql: {r.receipt.sql}",
        f"        result: {r.receipt.result}",
    ]
    return "\n".join(lines)


def render_markdown(report: Report) -> str:
    lines: list[str] = []
    lines.append(f"## Probe Report — {report.severity.upper()}")
    if report.scope:
        lines.append(f"**Scope:** {', '.join(report.scope)}")
    lines.append("")
    if report.explanation:
        lines.append(_render_explanation_markdown(report.explanation))
        lines.append("")
    for r in report.results:
        lines.append(_render_finding_markdown(r))
        lines.append("")
    return "\n".join(lines)


def _render_explanation_markdown(exp: Explanation) -> str:
    lines = [
        "### Explanation",
        "",
        exp.summary,
        "",
    ]
    for f in exp.findings:
        tag = "confirmed" if f.confirmed else "unconfirmed"
        backed = f" (backed by: {f.backed_by})" if f.backed_by else ""
        lines.append(f"- **[{tag}]** {f.claim}{backed}")
    return "\n".join(lines)


def _render_finding_markdown(r: ProbeResult) -> str:
    status_emoji = {"ok": "pass", "changed": "CHANGED", "unverified": "UNVERIFIED"}
    label = status_emoji.get(r.status, r.status)
    lines = [
        f"### {r.name} — {label}",
        f"**{r.question}**",
        f"- Old: `{r.old_value}`",
        f"- New: `{r.new_value}`",
        f"- Delta: `{r.delta}`",
        "",
        "<details><summary>Receipt</summary>",
        "",
        "```sql",
        r.receipt.sql,
        "```",
        f"Result: `{r.receipt.result}`",
        "</details>",
    ]
    return "\n".join(lines)
