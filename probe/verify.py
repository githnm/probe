"""Lineage verifier: prove or kill claimed column-level edges against real data."""

from __future__ import annotations

from dataclasses import dataclass

from probe import Receipt
from probe.db import Adapter


@dataclass
class EdgeResult:
    downstream_col: str
    claimed_parent: str
    verdict: str  # "verified" | "killed" | "unverified"
    match_rate: float | None
    real_parent: str | None
    receipt: Receipt


def verify(
    adapter: Adapter,
    upstream_sql: str,
    downstream_sql: str,
    key: str,
    mappings: dict[str, str] | None = None,
) -> list[EdgeResult]:
    up_cols = {name for name, _ in adapter.columns(upstream_sql)}
    down_cols = {name for name, _ in adapter.columns(downstream_sql)}

    if mappings is None:
        shared = sorted(up_cols & down_cols - {key})
        mappings = {c: c for c in shared}

    results: list[EdgeResult] = []
    for down_col, up_col in mappings.items():
        results.append(
            _verify_edge(adapter, upstream_sql, downstream_sql, key,
                         down_col, up_col, up_cols, down_cols)
        )
    return results


def _verify_edge(
    adapter: Adapter,
    upstream_sql: str,
    downstream_sql: str,
    key: str,
    down_col: str,
    up_col: str,
    up_cols: set[str],
    down_cols: set[str],
) -> EdgeResult:
    if key not in up_cols or key not in down_cols:
        return EdgeResult(
            downstream_col=down_col,
            claimed_parent=up_col,
            verdict="unverified",
            match_rate=None,
            real_parent=None,
            receipt=Receipt(sql="", result=f"key '{key}' missing from one or both sides"),
        )
    if down_col not in down_cols:
        return EdgeResult(
            downstream_col=down_col,
            claimed_parent=up_col,
            verdict="unverified",
            match_rate=None,
            real_parent=None,
            receipt=Receipt(sql="", result=f"column '{down_col}' not in downstream"),
        )
    if up_col not in up_cols:
        return EdgeResult(
            downstream_col=down_col,
            claimed_parent=up_col,
            verdict="unverified",
            match_rate=None,
            real_parent=None,
            receipt=Receipt(sql="", result=f"column '{up_col}' not in upstream"),
        )

    rate, sql = _match_rate(adapter, upstream_sql, downstream_sql, key, down_col, up_col)

    if rate >= 99.0:
        return EdgeResult(
            downstream_col=down_col,
            claimed_parent=up_col,
            verdict="verified",
            match_rate=rate,
            real_parent=None,
            receipt=Receipt(sql=sql, result={"match_rate": rate}),
        )

    real_parent, hunt_result = _hunt(
        adapter, upstream_sql, downstream_sql, key, down_col, up_col, up_cols
    )
    return EdgeResult(
        downstream_col=down_col,
        claimed_parent=up_col,
        verdict="killed",
        match_rate=rate,
        real_parent=real_parent,
        receipt=Receipt(sql=sql, result={
            "match_rate": rate,
            "hunt": hunt_result,
        }),
    )


def _match_rate(
    adapter: Adapter,
    upstream_sql: str,
    downstream_sql: str,
    key: str,
    down_col: str,
    up_col: str,
) -> tuple[float, str]:
    sql = (
        f"SELECT ROUND("
        f"SUM(CASE WHEN CAST(d.{down_col} AS VARCHAR)"
        f" IS NOT DISTINCT FROM CAST(u.{up_col} AS VARCHAR)"
        f" THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 2"
        f") AS match_rate"
        f" FROM ({downstream_sql}) d"
        f" JOIN ({upstream_sql}) u ON d.{key} = u.{key}"
    )
    row = adapter.run(sql)[0]
    rate = float(row["match_rate"]) if row["match_rate"] is not None else 0.0
    return rate, sql


def _hunt(
    adapter: Adapter,
    upstream_sql: str,
    downstream_sql: str,
    key: str,
    down_col: str,
    claimed: str,
    up_cols: set[str],
) -> tuple[str | None, dict]:
    candidates = sorted(up_cols - {key, claimed})
    best_col: str | None = None
    best_rate = 0.0
    checked: dict[str, float] = {}

    for candidate in candidates:
        rate, _ = _match_rate(
            adapter, upstream_sql, downstream_sql, key, down_col, candidate
        )
        checked[candidate] = rate
        if rate >= 99.0 and rate > best_rate:
            best_col = candidate
            best_rate = rate

    return best_col, {"candidates": checked, "real_parent": best_col}
