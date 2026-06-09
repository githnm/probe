"""Tests for the bounded agent loop and explanation."""

import json

from probe import Explanation, Finding, ProbeResult, Receipt, Report
from probe.orchestrate import _parse_and_enforce, _strip_fences, explain_report


def _make_report():
    return Report(
        results=[
            ProbeResult(
                name="row_count",
                question="Did the row count change?",
                old_value=100,
                new_value=120,
                delta=20,
                status="changed",
                receipt=Receipt(sql="SELECT COUNT(*)", result={"old": 100, "new": 120}),
            ),
            ProbeResult(
                name="column_presence",
                question="Were columns added or removed?",
                old_value=["id", "name"],
                new_value=["id", "name"],
                delta={"added": [], "removed": []},
                status="ok",
                receipt=Receipt(sql="SELECT * LIMIT 0", result={}),
            ),
        ],
        severity="block",
        scope=[],
    )


class FakeLLM:
    def __init__(self, response: str):
        self._response = response

    def complete(self, prompt: str) -> str:
        return self._response


class TestExplainReport:
    def test_valid_json_response(self):
        llm_response = json.dumps({
            "summary": "Row count increased by 20, likely a fan-out.",
            "findings": [
                {"claim": "Row count jumped from 100 to 120.", "backed_by": "row_count"},
                {"claim": "No columns were added or removed.", "backed_by": "column_presence"},
            ],
        })
        report = _make_report()
        explanation = explain_report(report, FakeLLM(llm_response))
        assert explanation.summary == "Row count increased by 20, likely a fan-out."
        assert len(explanation.findings) == 2
        assert explanation.findings[0].confirmed is True
        assert explanation.findings[0].backed_by == "row_count"

    def test_finding_with_unknown_probe_is_not_confirmed(self):
        llm_response = json.dumps({
            "summary": "Something changed.",
            "findings": [
                {"claim": "Data quality degraded.", "backed_by": "quality_score"},
            ],
        })
        report = _make_report()
        explanation = explain_report(report, FakeLLM(llm_response))
        assert explanation.findings[0].confirmed is False
        assert explanation.findings[0].backed_by == "quality_score"

    def test_finding_with_empty_backed_by_is_not_confirmed(self):
        llm_response = json.dumps({
            "summary": "Looks fine.",
            "findings": [
                {"claim": "Probably safe.", "backed_by": ""},
            ],
        })
        report = _make_report()
        explanation = explain_report(report, FakeLLM(llm_response))
        assert explanation.findings[0].confirmed is False

    def test_finding_with_missing_backed_by_is_not_confirmed(self):
        llm_response = json.dumps({
            "summary": "Something.",
            "findings": [
                {"claim": "Trust me."},
            ],
        })
        report = _make_report()
        explanation = explain_report(report, FakeLLM(llm_response))
        assert explanation.findings[0].confirmed is False
        assert explanation.findings[0].backed_by == ""

    def test_non_json_response_becomes_summary(self):
        report = _make_report()
        explanation = explain_report(report, FakeLLM("This is plain text."))
        assert explanation.summary == "This is plain text."
        assert explanation.findings == []

    def test_prompt_contains_probe_results(self):
        prompts = []

        class CaptureLLM:
            def complete(self, prompt):
                prompts.append(prompt)
                return json.dumps({"summary": "ok", "findings": []})

        report = _make_report()
        explain_report(report, CaptureLLM())
        assert "row_count" in prompts[0]
        assert "column_presence" in prompts[0]
        assert "100" in prompts[0]
        assert "120" in prompts[0]


class TestParseAndEnforce:
    def test_mixed_backed_and_unbacked(self):
        raw = json.dumps({
            "summary": "Mixed.",
            "findings": [
                {"claim": "Rows changed.", "backed_by": "row_count"},
                {"claim": "Vibes are off.", "backed_by": "vibes"},
                {"claim": "Ungrounded claim.", "backed_by": ""},
            ],
        })
        report = _make_report()
        exp = _parse_and_enforce(raw, report)
        assert exp.findings[0].confirmed is True
        assert exp.findings[1].confirmed is False
        assert exp.findings[2].confirmed is False

    def test_no_findings_in_response(self):
        raw = json.dumps({"summary": "All good."})
        report = _make_report()
        exp = _parse_and_enforce(raw, report)
        assert exp.summary == "All good."
        assert exp.findings == []


class TestStripFences:
    def test_strips_json_fence(self):
        raw = '```json\n{"summary": "hi"}\n```'
        assert _strip_fences(raw) == '{"summary": "hi"}'

    def test_strips_plain_fence(self):
        raw = '```\n{"summary": "hi"}\n```'
        assert _strip_fences(raw) == '{"summary": "hi"}'

    def test_no_fence_passthrough(self):
        raw = '{"summary": "hi"}'
        assert _strip_fences(raw) == '{"summary": "hi"}'

    def test_strips_whitespace_around_fences(self):
        raw = '  \n```json\n{"a": 1}\n```\n  '
        assert _strip_fences(raw) == '{"a": 1}'


class TestFencedLLMResponse:
    def test_fenced_json_is_parsed(self):
        fenced = '```json\n' + json.dumps({
            "summary": "Fan-out detected.",
            "findings": [
                {"claim": "Row count doubled.", "backed_by": "row_count"},
            ],
        }) + '\n```'
        report = _make_report()
        exp = explain_report(report, FakeLLM(fenced))
        assert exp.summary == "Fan-out detected."
        assert len(exp.findings) == 1
        assert exp.findings[0].confirmed is True

    def test_fenced_with_fake_probe_is_unconfirmed(self):
        fenced = '```json\n' + json.dumps({
            "summary": "Something happened.",
            "findings": [
                {"claim": "Bad vibes.", "backed_by": "vibes_probe"},
            ],
        }) + '\n```'
        report = _make_report()
        exp = explain_report(report, FakeLLM(fenced))
        assert exp.findings[0].confirmed is False
        assert exp.findings[0].backed_by == "vibes_probe"


class TestPromptContent:
    def test_prompt_says_no_fences(self):
        prompts = []

        class CaptureLLM:
            def complete(self, prompt):
                prompts.append(prompt)
                return json.dumps({"summary": "ok", "findings": []})

        report = _make_report()
        explain_report(report, CaptureLLM())
        assert "no markdown fences" in prompts[0].lower() or "No markdown fences" in prompts[0]
        assert "raw JSON" in prompts[0] or "raw json" in prompts[0].lower()


class TestNoApiKey:
    """Without an API key, --explain warns but the report still renders with receipts."""

    def test_cli_without_key_still_prints_report(self):
        from click.testing import CliRunner

        from probe.cli import main

        runner = CliRunner(env={"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": ""})
        setup = "CREATE TABLE t (id INT); INSERT INTO t VALUES (1), (2)"
        result = runner.invoke(main, [
            "diff",
            "--setup", setup,
            "--old", "SELECT * FROM t",
            "--new", "SELECT * FROM t",
            "--explain",
        ])
        assert result.exit_code == 0
        assert "receipt:" in result.output
        assert "row_count" in result.output
        assert "Explanation:" not in result.output

    def test_cli_without_key_emits_warning(self):
        from click.testing import CliRunner

        from probe.cli import main

        runner = CliRunner(env={"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": ""})
        setup = "CREATE TABLE t (id INT); INSERT INTO t VALUES (1)"
        result = runner.invoke(main, [
            "diff",
            "--setup", setup,
            "--old", "SELECT * FROM t",
            "--new", "SELECT * FROM t",
            "--explain",
        ])
        assert "Warning" in (result.output + (result.stderr or ""))


class TestWithExplanation:
    """With a mocked LLM, the explanation renders alongside receipts."""

    def test_report_renders_explanation_and_receipts(self):
        from probe.report import render_terminal

        report = _make_report()
        report.explanation = Explanation(
            summary="Row count increased significantly.",
            findings=[
                Finding(claim="20 new rows appeared.", backed_by="row_count", confirmed=True),
                Finding(claim="Might be a join issue.", backed_by="", confirmed=False),
            ],
        )
        text = render_terminal(report)
        assert "Explanation:" in text
        assert "Row count increased significantly." in text
        assert "[confirmed] 20 new rows appeared." in text
        assert "(backed by: row_count)" in text
        assert "[unconfirmed] Might be a join issue." in text
        assert "receipt:" in text
        assert "SELECT COUNT(*)" in text

    def test_markdown_renders_explanation(self):
        from probe.report import render_markdown

        report = _make_report()
        report.explanation = Explanation(
            summary="Summary here.",
            findings=[
                Finding(claim="A claim.", backed_by="row_count", confirmed=True),
            ],
        )
        md = render_markdown(report)
        assert "### Explanation" in md
        assert "Summary here." in md
        assert "**[confirmed]**" in md
        assert "Receipt" in md
