"""Tests for GitHub PR comment poster."""

from probe import Explanation, Finding, ProbeResult, Receipt, Report
from probe.comment import COMMENT_MARKER, format_comment


def _make_report(severity="block", explanation=None):
    return Report(
        results=[
            ProbeResult(
                name="row_count",
                question="Did the row count change?",
                old_value=5,
                new_value=11,
                delta=6,
                status="changed",
                receipt=Receipt(
                    sql="SELECT COUNT(*) AS cnt FROM (SELECT 1) _t",
                    result={"old": 5, "new": 11},
                ),
            ),
            ProbeResult(
                name="grain",
                question="Is the grain (uniqueness on key) preserved?",
                old_value={"total": 5, "distinct": 5, "duplicates": 0},
                new_value={"total": 11, "distinct": 5, "duplicates": 6},
                delta=6,
                status="changed",
                receipt=Receipt(
                    sql="SELECT COUNT(*) AS total, COUNT(DISTINCT id) AS uniq FROM (SELECT 1) _t",
                    result={"old": {"total": 5, "uniq": 5}, "new": {"total": 11, "uniq": 5}},
                ),
            ),
            ProbeResult(
                name="column_presence",
                question="Were columns added or removed?",
                old_value=["id", "amount"],
                new_value=["id", "amount", "city"],
                delta={"added": ["city"], "removed": []},
                status="changed",
                receipt=Receipt(
                    sql="SELECT * FROM (...) _t LIMIT 0",
                    result={
                        "old_columns": ["id", "amount"],
                        "new_columns": ["id", "amount", "city"],
                    },
                ),
            ),
        ],
        severity=severity,
        scope=["city"],
        explanation=explanation,
    )


class TestFormatComment:
    def test_contains_marker(self):
        body = format_comment(_make_report())
        assert COMMENT_MARKER in body

    def test_contains_severity_header(self):
        body = format_comment(_make_report())
        assert "BLOCK" in body

    def test_contains_probe_report_markdown(self):
        body = format_comment(_make_report())
        assert "## Probe Report" in body

    def test_contains_receipts(self):
        body = format_comment(_make_report())
        assert "```sql" in body
        assert "COUNT(*)" in body

    def test_contains_all_findings(self):
        body = format_comment(_make_report())
        assert "row_count" in body
        assert "grain" in body
        assert "column_presence" in body

    def test_contains_scope(self):
        body = format_comment(_make_report())
        assert "city" in body

    def test_contains_footer(self):
        body = format_comment(_make_report())
        assert "Probe" in body
        assert "proof" in body

    def test_info_severity(self):
        body = format_comment(_make_report(severity="info"))
        assert "INFO" in body

    def test_warn_severity(self):
        body = format_comment(_make_report(severity="warn"))
        assert "WARN" in body

    def test_with_explanation(self):
        exp = Explanation(
            summary="Fan-out detected from a one-to-many join.",
            findings=[
                Finding("Row count doubled.", backed_by="row_count", confirmed=True),
                Finding("Grain is broken.", backed_by="grain", confirmed=True),
            ],
        )
        body = format_comment(_make_report(explanation=exp))
        assert "### Explanation" in body
        assert "Fan-out detected" in body
        assert "**[confirmed]**" in body
        assert "```sql" in body

    def test_without_explanation_still_has_receipts(self):
        body = format_comment(_make_report(explanation=None))
        assert "Explanation" not in body
        assert "Receipt" in body
        assert "```sql" in body

    def test_marker_enables_upsert(self):
        body = format_comment(_make_report())
        assert body.startswith(COMMENT_MARKER)

    def test_delta_values_present(self):
        body = format_comment(_make_report())
        assert "`6`" in body
        assert "duplicates" in body
