"""Run all available probes, collect results, assign severity, return a Report."""

from __future__ import annotations

from probe import Report
from probe.db import Adapter
from probe.probes import column_presence, row_count
from probe.severity import overall

ALL_PROBES = [row_count, column_presence]


def run_diff(adapter: Adapter, old_sql: str, new_sql: str) -> Report:
    results = [probe(adapter, old_sql, new_sql) for probe in ALL_PROBES]
    sev = overall(results)
    scope = _impacted_columns(results)
    return Report(results=results, severity=sev, scope=scope)


def _impacted_columns(results: list) -> list[str]:
    for r in results:
        if r.name == "column_presence" and r.status == "changed":
            delta = r.delta
            return delta.get("added", []) + delta.get("removed", [])
    return []
