"""Bounded agent loop: pick probes, refine, fallback."""

from __future__ import annotations

import json
import os
from typing import Protocol

from probe import Explanation, Finding, Report


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str: ...


def explain_report(report: Report, client: LLMClient) -> Explanation:
    prompt = _build_prompt(report)
    raw = client.complete(prompt)
    return _parse_and_enforce(raw, report)


def _build_prompt(report: Report) -> str:
    lines = [
        "You are a SQL reviewer. Below are probe results comparing old vs new SQL.",
        "Write a plain-English summary and a list of findings.",
        "Respond in JSON: {\"summary\": \"...\", \"findings\": [{\"claim\": \"...\", "
        "\"backed_by\": \"<probe_name>\"}]}",
        "Only reference probe names that appear in the results below.",
        "",
    ]
    for r in report.results:
        lines.append(
            f"Probe: {r.name} | status: {r.status} | "
            f"old: {r.old_value} | new: {r.new_value} | delta: {r.delta}"
        )
    return "\n".join(lines)


def _parse_and_enforce(raw: str, report: Report) -> Explanation:
    probe_names = {r.name for r in report.results}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return Explanation(
            summary=raw,
            findings=[],
        )

    summary = data.get("summary", "")
    findings = []
    for f in data.get("findings", []):
        claim = f.get("claim", "")
        backed_by = f.get("backed_by", "")
        confirmed = backed_by in probe_names and backed_by != ""
        findings.append(Finding(
            claim=claim,
            backed_by=backed_by,
            confirmed=confirmed,
        ))
    return Explanation(summary=summary, findings=findings)


def get_llm_client() -> LLMClient | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    provider = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "openai"
    return _EnvLLMClient(api_key=api_key, provider=provider)


class _EnvLLMClient:
    def __init__(self, api_key: str, provider: str):
        self._api_key = api_key
        self._provider = provider

    def complete(self, prompt: str) -> str:
        if self._provider == "anthropic":
            return self._call_anthropic(prompt)
        return self._call_openai(prompt)

    def _call_anthropic(self, prompt: str) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=self._api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    def _call_openai(self, prompt: str) -> str:
        import openai

        client = openai.OpenAI(api_key=self._api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        return response.choices[0].message.content
