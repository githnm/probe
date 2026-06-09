"""Severity gating: map probe results to info/warn/block."""

from __future__ import annotations

from probe import ProbeResult

SEVERITY_ORDER = {"info": 0, "warn": 1, "block": 2}


def classify(result: ProbeResult) -> str:
    if result.status in ("ok", "unverified"):
        return "info"

    if result.name == "row_count":
        delta = result.delta
        if isinstance(delta, (int, float)) and delta < 0:
            return "warn"
        if isinstance(delta, (int, float)) and delta > 0:
            return "block"
        return "info"

    if result.name == "grain":
        return "block"

    if result.name == "null_rate":
        if isinstance(result.delta, dict):
            for col_delta in result.delta.values():
                if isinstance(col_delta, (int, float)) and col_delta > 0:
                    return "warn"
        return "info"

    if result.name == "metric_sum":
        return "warn"

    if result.name == "column_presence":
        delta = result.delta
        if isinstance(delta, dict) and delta.get("removed"):
            return "block"
        return "info"

    return "info"


def overall(results: list[ProbeResult]) -> str:
    if not results:
        return "info"
    severities = [classify(r) for r in results]
    return max(severities, key=lambda s: SEVERITY_ORDER.get(s, 0))
