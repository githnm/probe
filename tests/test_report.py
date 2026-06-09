"""Tests for report assembly."""

from probe import ProbeResult, Receipt, Report
from probe.report import render_markdown, render_terminal


def _make_report():
    return Report(
        results=[
            ProbeResult(
                name="row_count",
                question="Did the row count change?",
                old_value=100,
                new_value=95,
                delta=-5,
                status="changed",
                receipt=Receipt(
                    sql="SELECT COUNT(*) AS cnt FROM (SELECT 1) _t",
                    result={"old": 100, "new": 95},
                ),
            ),
            ProbeResult(
                name="column_presence",
                question="Were columns added or removed?",
                old_value=["id", "name"],
                new_value=["id", "name", "email"],
                delta={"added": ["email"], "removed": []},
                status="changed",
                receipt=Receipt(
                    sql="SELECT * FROM (SELECT 1) _t LIMIT 0",
                    result={"old_columns": ["id", "name"], "new_columns": ["id", "name", "email"]},
                ),
            ),
        ],
        severity="warn",
        scope=["email"],
    )


class TestTerminal:
    def test_contains_severity(self):
        text = render_terminal(_make_report())
        assert "severity: warn" in text

    def test_contains_scope(self):
        text = render_terminal(_make_report())
        assert "email" in text

    def test_contains_receipt_sql(self):
        text = render_terminal(_make_report())
        assert "SELECT COUNT(*)" in text

    def test_contains_receipt_result(self):
        text = render_terminal(_make_report())
        assert "'old': 100" in text

    def test_contains_all_findings(self):
        text = render_terminal(_make_report())
        assert "row_count" in text
        assert "column_presence" in text


class TestMarkdown:
    def test_header_contains_severity(self):
        md = render_markdown(_make_report())
        assert "## Probe Report" in md
        assert "WARN" in md

    def test_contains_receipt_block(self):
        md = render_markdown(_make_report())
        assert "<details><summary>Receipt</summary>" in md
        assert "```sql" in md

    def test_contains_delta(self):
        md = render_markdown(_make_report())
        assert "-5" in md
