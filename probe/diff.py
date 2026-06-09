"""Run all available probes, collect results, assign severity, return a Report."""

from __future__ import annotations

from probe import Report
from probe.db import Adapter
from probe.probes import column_presence, grain, metric_sum, null_rate, row_count
from probe.severity import overall

ALL_PROBES = [row_count, grain, null_rate, column_presence, metric_sum]


def run_diff(
    adapter: Adapter,
    old_sql: str,
    new_sql: str,
    key: str | None = None,
    scope_columns: list[str] | None = None,
    metrics: list[str] | None = None,
) -> Report:
    results = [
        p(adapter, old_sql, new_sql, key=key, metrics=metrics)
        for p in ALL_PROBES
    ]

    if scope_columns is not None:
        results = _filter_by_scope(results, scope_columns)

    sev = overall(results)
    scope = scope_columns if scope_columns is not None else _impacted_columns(results)
    return Report(results=results, severity=sev, scope=scope)


def _filter_by_scope(results: list, scope_columns: list[str]) -> list:
    filtered = []
    for r in results:
        if r.name == "null_rate" and r.status != "unverified":
            scoped = {c: v for c, v in r.old_value.items() if c in scope_columns}
            if not scoped:
                filtered.append(r)
                continue
            from probe import ProbeResult, Receipt

            new_scoped = {c: v for c, v in r.new_value.items() if c in scope_columns}
            delta = {c: v for c, v in r.delta.items() if c in scope_columns}
            changed = any(d != 0 for d in delta.values())
            filtered.append(ProbeResult(
                name=r.name,
                question=r.question,
                old_value=scoped,
                new_value=new_scoped,
                delta=delta,
                status="ok" if not changed else "changed",
                receipt=Receipt(
                    sql=r.receipt.sql,
                    result={"old": scoped, "new": new_scoped},
                ),
            ))
        else:
            filtered.append(r)
    return filtered


def _impacted_columns(results: list) -> list[str]:
    for r in results:
        if r.name == "column_presence" and r.status == "changed":
            delta = r.delta
            return delta.get("added", []) + delta.get("removed", [])
    return []
